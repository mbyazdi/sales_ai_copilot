"""Disposable-only round-trip parity and zero-query/source-preservation evidence.

The capture helper is a test fixture, not a live strategy integration service.
"""
import json
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.customers.models import Customer, CustomerGrade
from apps.inventory.models import Inventory
from apps.products.eligibility import product_eligibility
from apps.products.models import Brand, Category, Product, ProductDemoPrice
from apps.products.pricing import DemoPriceProvider
from apps.promotions.models import Promotion, PromotionProduct
from apps.recommendations.models import CustomerRecommendation
from apps.targets.models import SalesTarget
from apps.visits.models import Salesperson
from .strategy_evaluator import (
    CommercialFacts, ProductFacts, PromotionFacts, SavedRecommendation, StrategyRules,
    StrategySnapshot, TargetFacts, evaluate_strategy,
)
from .tests_strategy_evaluator import DAY, config, priority, promotion, snapshot, target


class StrategyEvaluatorDatabaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grade = CustomerGrade.objects.create(pk=1, code="A", name="گروه الف")
        CustomerGrade.objects.create(pk=2, code="B", name="گروه ب")
        cls.customer = Customer.objects.create(pk=1, customer_code="OVERLAY-C", name="مشتری آزمایشی", grade=cls.grade)
        cls.rep = Salesperson.objects.create(pk=7, employee_code="OVERLAY-SP", first_name="فروشنده", last_name="آزمایشی")
        for row, facts in zip(snapshot().recommendations, snapshot().products):
            brand = Brand.objects.create(pk=facts.brand_id, code=f"OVERLAY-B{facts.brand_id}", name=f"برند {facts.brand_id}")
            category = Category.objects.create(pk=facts.category_id, code=f"OVERLAY-C{facts.category_id}", name=f"دسته {facts.category_id}")
            product = Product.objects.create(pk=facts.product_id, product_code=facts.product_code, name="محصول آزمایشی",
                                             brand=brand, category=category, product_group=facts.product_group)
            Inventory.objects.create(product=product, available_quantity=12, reserved_quantity=2)
            ProductDemoPrice.objects.create(product=product, base_price=Decimal(100), currency="TOMAN", source="ISOLATED_ONLY", source_version="M_C2_V1")
            CustomerRecommendation.objects.create(pk=row.recommendation_id, customer=cls.customer, product=product,
                                                 rank=row.saved_rank, score=row.base_score, reason=row.stored_reason,
                                                 recommendation_type="CATEGORY", score_breakdown={"promotion_score": 20.0},
                                                 explanation_snapshot={"synthetic": True})
        SalesTarget.objects.create(pk=1, salesperson=cls.rep, product_id=3, scope_type="PRODUCT", target_unit="QUANTITY",
                                   period_start=DAY, period_end=DAY, target_value=100, actual_value=50)
        offer = Promotion.objects.create(pk=1, code="OVERLAY-PROMO", name="ترویج آزمایشی", promotion_type="PERCENTAGE",
                                         start_date=DAY, end_date=DAY, minimum_quantity=1)
        offer.customer_grades.add(cls.grade)
        PromotionProduct.objects.create(promotion=offer, product_id=3)

    def captured(self):
        strategy = config(priority_rules=[priority("PRODUCT", 3, 20)], target_weight=5,
                          promotion_rules=[{"promotion_id": 1, "points": 5}])
        products = list(Product.objects.order_by("pk").select_related("inventory"))
        by_id = {row.pk: row for row in products}
        quotes = DemoPriceProvider().quote_many(self.customer.pk, {row.pk: 1 for row in products})
        recommendations = []
        for row in CustomerRecommendation.objects.filter(customer=self.customer).order_by("rank", "pk"):
            eligibility = product_eligibility(by_id[row.product_id])
            price = quotes[row.product_id]
            reason = eligibility["non_addable_reason"]
            if reason is None and price.state != "AVAILABLE":
                reason = "PRICE_UNAVAILABLE" if price.state == "UNAVAILABLE" else "PRICE_CONFIGURATION_ERROR"
            recommendations.append(SavedRecommendation(
                row.pk, row.product_id, row.rank, row.score, row.reason,
                CommercialFacts(eligibility["inventory_state"], eligibility["available_quantity"], str(price.state),
                                reason is None, reason, price.reason_code),
                json.dumps({**row.score_breakdown, **row.explanation_snapshot}, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            ))
        targets = tuple(TargetFacts(row.pk, row.salesperson_id, row.scope_type, row.product_id,
                                    row.target_unit, row.target_value, row.actual_value, row.period_start, row.period_end, row.is_active)
                        for row in SalesTarget.objects.order_by("pk"))
        promotions = tuple(PromotionFacts(row.pk, tuple(row.products.order_by("pk").values_list("pk", flat=True)),
                                          tuple(row.customer_grades.order_by("pk").values_list("pk", flat=True)), row.start_date,
                                          row.end_date, row.minimum_quantity, row.maximum_quantity, row.is_active)
                           for row in Promotion.objects.order_by("pk"))
        return StrategySnapshot(self.customer.pk, self.rep.pk, self.customer.grade_id, DAY, tuple(recommendations),
                                tuple(ProductFacts(row.pk, row.product_code, row.brand_id, row.category_id, row.product_group, row.is_active) for row in products),
                                tuple(Brand.objects.order_by("pk").values_list("pk", flat=True)),
                                tuple(Category.objects.order_by("pk").values_list("pk", flat=True)),
                                tuple(CustomerGrade.objects.order_by("pk").values_list("pk", flat=True)),
                                targets, promotions, StrategyRules.from_config(strategy))

    def business_rows(self):
        return {model._meta.label_lower: list(model.objects.order_by("pk").values()) for model in (
            CustomerRecommendation, Product, Brand, Category, Customer, CustomerGrade, Salesperson,
            Inventory, ProductDemoPrice, SalesTarget, Promotion, PromotionProduct,
        )}

    def test_database_snapshot_matches_pure_result_with_zero_queries_and_no_writes(self):
        frozen = self.captured()
        expected = snapshot(config(priority_rules=[priority("PRODUCT", 3, 20)], target_weight=5,
                                   promotion_rules=[{"promotion_id": 1, "points": 5}]),
                            targets=(target(actual_value=Decimal("50.00")),), promotions=(promotion(),))
        self.assertEqual(frozen, expected)
        before = self.business_rows()
        with CaptureQueriesContext(connection) as queries:
            result = evaluate_strategy(frozen)
            self.assertEqual(result.as_dict(), evaluate_strategy(expected).as_dict())
        self.assertEqual(len(queries), 0)
        self.assertEqual(self.business_rows(), before)
        self.assertEqual(result.after_ids, (103, 101, 102, 104))
        print(f"M-C2 {connection.vendor} parity digest: {result.result_digest}; evaluator queries: 0")

    def test_current_missing_price_zero_unknown_stock_and_inactive_are_not_overridden(self):
        ProductDemoPrice.objects.filter(product_id=1).delete()
        Inventory.objects.filter(product_id=2).update(available_quantity=2, reserved_quantity=2)
        Inventory.objects.filter(product_id=3).delete()
        Product.objects.filter(pk=4).update(is_active=False)
        frozen = self.captured()
        before = self.business_rows()
        with self.assertNumQueries(0):
            result = evaluate_strategy(frozen)
        facts = {row.source.product_id: row for row in result.rows}
        self.assertEqual(facts[1].source.commercial.pricing_reason, "MISSING_PRICE")
        self.assertEqual(facts[2].source.commercial.sellable_quantity, 0)
        self.assertIsNone(facts[3].source.commercial.sellable_quantity)
        self.assertFalse(facts[4].product.is_active)
        self.assertTrue(all(not row.source.commercial.can_add for row in result.rows))
        self.assertEqual(self.business_rows(), before)
