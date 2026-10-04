"""Characterize V3.0.10.9 behavior; expected values are baseline facts."""

from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.core.commercial_context import build_product_commercial_context
from apps.customers.models import Customer, Customer360, CustomerGrade
from apps.products.models import Brand, Category, Product
from apps.promotions.models import Promotion, PromotionProduct
from apps.sales.models import Sale, SaleItem

from .models import CustomerRecommendation
from .services import generate_customer_recommendations


class RecommendationBaselineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.grade = CustomerGrade.objects.create(code="A", name="Grade A")
        cls.customer = Customer.objects.create(
            customer_code="TEST-CUSTOMER", name="Test customer", grade=cls.grade,
        )
        Customer360.objects.create(customer=cls.customer, total_orders=1)
        brand = Brand.objects.create(code="TEST-BRAND", name="Test brand")
        category = Category.objects.create(code="TEST-CATEGORY", name="Test category")
        cls.repeat = Product.objects.create(
            product_code="REPEAT", name="A repeat", brand=brand, category=category,
            is_consumable=True, repurchase_cycle_days=30,
        )
        cls.similar = Product.objects.create(
            product_code="SIMILAR", name="B similar", brand=brand, category=category,
        )
        cls.unranked = Product.objects.create(
            product_code="UNRANKED", name="C unranked", brand=brand,
            category=Category.objects.create(code="OTHER", name="Other category"),
        )
        cls.inactive = Product.objects.create(
            product_code="INACTIVE", name="D inactive", brand=brand,
            category=category, is_active=False,
        )
        sale = Sale.objects.create(
            customer=cls.customer, invoice_number="TEST-INVOICE",
            sale_date=cls.today - timedelta(days=40), total_amount=Decimal("100"),
        )
        SaleItem.objects.create(
            sale=sale, product=cls.repeat, quantity=1, unit_price=Decimal("100"),
        )

    def generate(self):
        return generate_customer_recommendations(self.customer.customer_code)["recommendations"]

    def test_generation_persists_baseline_ranking_scores_and_explanations(self):
        recommendations = self.generate()
        self.assertEqual(
            [(row.product_id, row.rank, row.score, row.recommendation_type)
             for row in recommendations],
            [(self.repeat.pk, 1, Decimal("80"), "REPEAT_PURCHASE"),
             (self.similar.pk, 2, Decimal("60"), "SIMILAR_PRODUCT")],
        )
        expected_breakdowns = [
            {"group_score": 30.0, "purchase_score": 35.0, "association_score": 0.0,
             "upsell_score": 0.0, "grade_score": 15.0, "promotion_score": 0.0,
             "similar_score": 0.0, "rule_score": 80.0, "feedback_score": 0.0,
             "final_score": 80.0},
            {"group_score": 30.0, "purchase_score": 0.0, "association_score": 0.0,
             "upsell_score": 0.0, "grade_score": 15.0, "promotion_score": 0.0,
             "similar_score": 15.0, "rule_score": 60.0, "feedback_score": 0.0,
             "final_score": 60.0},
        ]
        for row, breakdown in zip(recommendations, expected_breakdowns):
            with self.subTest(product=row.product_id):
                row.refresh_from_db()
                self.assertTrue(row.is_active)
                self.assertTrue(row.reason)
                self.assertEqual(row.score_breakdown, breakdown)
                self.assertEqual(row.confidence_score, Decimal("80"))
                self.assertEqual(row.evidence_quality, "MEDIUM")
                explanation = row.explanation_snapshot
                self.assertEqual(explanation["final_score"], float(row.score))
                self.assertEqual(explanation["rule_score"], float(row.score))
                self.assertEqual(explanation["feedback_score"], 0.0)
                self.assertEqual(explanation["active_signal_count"], 3)
                self.assertEqual(explanation["confidence_score"], 80.0)
                self.assertEqual(explanation["evidence_quality"], "MEDIUM")
                self.assertEqual(
                    {signal["name"]: signal["score"] for signal in explanation["signals"]},
                    {"group_affinity": breakdown["group_score"],
                     "repurchase": breakdown["purchase_score"], "association": 0.0,
                     "upsell": 0.0, "customer_grade": 15.0, "promotion": 0.0,
                     "similar_product": breakdown["similar_score"],
                     "historical_feedback": 0.0},
                )
        self.assertEqual(CustomerRecommendation.objects.count(), 2)

    def test_regeneration_retires_old_rows_and_preserves_deterministic_results(self):
        first = self.generate()
        original = list(CustomerRecommendation.objects.order_by("rank").values(
            "id", "product_id", "rank", "score", "reason", "score_breakdown",
            "explanation_snapshot",
        ))
        second = self.generate()
        self.assertEqual(CustomerRecommendation.objects.count(), 4)
        self.assertFalse(CustomerRecommendation.objects.filter(
            pk__in=[row.pk for row in first], is_active=True,
        ).exists())
        active = list(CustomerRecommendation.objects.filter(is_active=True).order_by("rank").values(
            "id", "product_id", "rank", "score", "reason", "score_breakdown",
            "explanation_snapshot",
        ))
        self.assertEqual(len(active), 2)
        self.assertEqual(len({row["product_id"] for row in active}), 2)
        self.assertTrue({row.pk for row in first}.isdisjoint(row.pk for row in second))
        self.assertEqual(
            [{key: value for key, value in row.items() if key != "id"} for row in original],
            [{key: value for key, value in row.items() if key != "id"} for row in active],
        )

    def test_customer_without_360_generates_no_rows(self):
        customer = Customer.objects.create(customer_code="NO-360", name="No snapshot")
        result = generate_customer_recommendations(customer.customer_code)
        self.assertEqual(result["recommendations"], [])
        self.assertFalse(CustomerRecommendation.objects.exists())

    def test_active_expired_grade_ineligible_promotion_still_adds_engine_score(self):
        # Deliberately preserve the existing scoring/eligibility discrepancy.
        promotion = Promotion.objects.create(
            code="EXPIRED", name="Expired offer", promotion_type="PERCENTAGE",
            start_date=self.today - timedelta(days=10),
            end_date=self.today - timedelta(days=1), is_active=True,
        )
        promotion.customer_grades.add(CustomerGrade.objects.create(code="B", name="Grade B"))
        PromotionProduct.objects.create(promotion=promotion, product=self.similar)
        recommendations = self.generate()
        similar = next(row for row in recommendations if row.product_id == self.similar.pk)
        self.assertEqual(similar.score, Decimal("80"))
        self.assertEqual(similar.score_breakdown["promotion_score"], 20.0)
        # Equal scores retain candidate order (Product's name ordering).
        self.assertEqual([row.product_id for row in recommendations], [self.repeat.pk, self.similar.pk])
        context = build_product_commercial_context(self.similar, self.customer, self.today)
        self.assertEqual(context["promotions"], [])
        self.assertFalse(context["has_eligible_promotion"])
