"""Pure calculations and read-only provider tests; fixtures use test DB only."""
from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal, Inexact, ROUND_DOWN, localcontext
from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from apps.customers.models import Customer, CustomerGrade
from apps.inventory.models import Inventory
from apps.promotions.models import Promotion, PromotionProduct
from apps.recommendations.models import RecommendationFeedbackEvent
from apps.sales.models import Sale, SaleItem
from apps.sales_requests.models import SalesRequest, SalesRequestLine, SalesRequestMutationReceipt
from apps.visits.models import Visit
from .models import Brand, Category, Product, ProductDemoPrice
from .pricing import (
    CALCULATION_POLICY_VERSION, MAX_WHOLE_AMOUNT, DemoPriceProvider, PriceState,
    PricingConfigurationError, PricingInputError, calculate_demo_quote,
)


class PricingCalculationTests(SimpleTestCase):
    def quote(self, **changes):
        values = {
            "customer_id": 1, "product_id": 2, "grade_code": "A", "quantity": 3,
            "base_price": Decimal("105"), "currency": "TOMAN",
            "price_source": "controlled-demo", "price_source_version": "v1",
        }
        values.update(changes)
        return calculate_demo_quote(**values)

    def test_grades_have_only_approved_discounts(self):
        for grade, percentage, final in (("A", 10, 90), ("B", 5, 95), ("C", 0, 100),
                                         (None, 0, 100), ("", 0, 100), ("a", 0, 100)):
            with self.subTest(grade=grade):
                quote = self.quote(grade_code=grade, base_price=Decimal("100"))
                self.assertEqual(quote.discount_percentage, Decimal(percentage))
                self.assertEqual(quote.final_unit_price, Decimal(final))

    def test_round_half_up_ties_at_unit_level(self):
        for grade, base, final in (("A", "105", "95"), ("A", "115", "104"),
                                   ("B", "110", "105"), ("B", "130", "124")):
            with self.subTest(grade=grade, base=base):
                quote = self.quote(grade_code=grade, base_price=Decimal(base))
                self.assertEqual(quote.final_unit_price, Decimal(final))
                self.assertEqual(quote.line_total, Decimal(final) * 3)

    def test_line_arithmetic_uses_rounded_units_without_second_discount(self):
        quote = self.quote()
        self.assertEqual((quote.base_unit_price, quote.unit_discount, quote.final_unit_price),
                         (Decimal("105"), Decimal("10"), Decimal("95")))
        self.assertEqual((quote.line_base, quote.line_discount, quote.line_total),
                         (Decimal("315"), Decimal("30"), Decimal("285")))
        self.assertEqual(quote.line_base - quote.line_discount, quote.line_total)

    def test_sum_of_quotes_reconciles_without_rounding_or_discounting_totals_again(self):
        quotes = [self.quote(), self.quote(product_id=3, grade_code="A", base_price=Decimal("115"), quantity=2)]
        base = sum((quote.line_base for quote in quotes), Decimal("0"))
        discount = sum((quote.line_discount for quote in quotes), Decimal("0"))
        total = sum((quote.line_total for quote in quotes), Decimal("0"))
        self.assertEqual((base, discount, total), (Decimal("545"), Decimal("52"), Decimal("493")))
        self.assertEqual(base - discount, total)

    def test_low_price_discount_may_round_to_zero_without_fabricating_a_discount(self):
        quote = self.quote(base_price=Decimal("5"))
        self.assertEqual(quote.discount_percentage, Decimal("10"))
        self.assertEqual(quote.unit_discount, Decimal("0"))
        self.assertEqual(quote.line_total, Decimal("15"))

    def test_zero_price_is_valid_explicit_configuration(self):
        quote = self.quote(base_price=Decimal("0"))
        self.assertEqual(quote.base_unit_price, Decimal("0"))
        self.assertEqual(quote.line_total, Decimal("0"))

    def test_fractional_and_invalid_base_prices_raise_configuration_errors(self):
        for base in (Decimal("1.01"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity"),
                     Decimal("-Infinity"), MAX_WHOLE_AMOUNT + 1, None, 105.0, "105", 105):
            with self.subTest(base=base), self.assertRaises(PricingConfigurationError):
                self.quote(base_price=base)
        with self.assertRaises(PricingConfigurationError) as failure:
            self.quote(base_price=Decimal("105.50"))
        self.assertEqual(failure.exception.code, "FRACTIONAL_BASE_PRICE")

    def test_currency_and_source_are_explicit(self):
        for changes in ({"currency": "RIAL"}, {"currency": None}, {"price_source": ""},
                        {"price_source_version": "  "}, {"price_source": None}, {"price_source": "x" * 101}):
            with self.subTest(changes=changes), self.assertRaises(PricingConfigurationError):
                self.quote(**changes)

    def test_quantity_is_positive_integer_without_coercion(self):
        for quantity in (0, -1, True, False, 1.5, Decimal("2"), "2", None):
            with self.subTest(quantity=quantity), self.assertRaises(PricingInputError) as failure:
                self.quote(quantity=quantity)
            self.assertEqual(failure.exception.code, "INVALID_QUANTITY")

    def test_identity_and_grade_input_validation(self):
        for changes in ({"customer_id": 0}, {"customer_id": True}, {"product_id": "2"}, {"grade_code": 1}):
            with self.subTest(changes=changes), self.assertRaises(PricingInputError):
                self.quote(**changes)

    def test_amounts_fit_existing_snapshot_fields(self):
        quote = self.quote(base_price=MAX_WHOLE_AMOUNT, quantity=1)
        self.assertEqual(quote.line_base, MAX_WHOLE_AMOUNT)
        with self.assertRaises(PricingInputError) as failure:
            self.quote(base_price=MAX_WHOLE_AMOUNT, quantity=2)
        self.assertEqual(failure.exception.code, "LINE_AMOUNT_OUT_OF_RANGE")

    def test_arithmetic_is_independent_of_callers_decimal_context(self):
        expected = self.quote()
        with localcontext() as context:
            context.prec = 2
            context.rounding = ROUND_DOWN
            context.traps[Inexact] = True
            self.assertEqual(self.quote(), expected)

    def test_quote_preserves_source_and_policy_version(self):
        quote = self.quote()
        self.assertEqual(quote.currency, "TOMAN")
        self.assertEqual(quote.price_source, "controlled-demo")
        self.assertEqual(quote.price_source_version, "v1")
        self.assertEqual(quote.calculation_policy_version, CALCULATION_POLICY_VERSION)

    def test_quote_is_immutable_and_wire_money_is_whole_decimal_strings(self):
        quote = self.quote()
        with self.assertRaises(FrozenInstanceError):
            quote.line_total = Decimal("1")
        data = quote.as_dict()
        for field in ("base_unit_price", "discount_percentage", "unit_discount", "final_unit_price", "line_base", "line_discount", "line_total"):
            self.assertIsInstance(getattr(quote, field), Decimal)
            self.assertIsInstance(data[field], str)
            self.assertNotIn(".", data[field])
        self.assertEqual(data["line_total"], "285")
        self.assertEqual(data["quantity"], 3)

    def test_fingerprint_is_stable_across_equivalent_decimal_representations(self):
        self.assertEqual(self.quote(), self.quote())
        self.assertEqual(self.quote(base_price=Decimal("105.00")).quote_fingerprint, self.quote().quote_fingerprint)
        self.assertRegex(self.quote().quote_fingerprint, r"\A[0-9a-f]{64}\Z")

    def test_fingerprint_changes_for_commercial_inputs(self):
        original = self.quote().quote_fingerprint
        for changes in ({"customer_id": 9}, {"product_id": 9}, {"grade_code": "B"}, {"quantity": 4},
                        {"base_price": Decimal("106")}, {"price_source": "another-source"},
                        {"price_source_version": "v2"}):
            with self.subTest(changes=changes):
                self.assertNotEqual(self.quote(**changes).quote_fingerprint, original)

    def test_fingerprint_changes_for_calculation_policy_version(self):
        original = self.quote().quote_fingerprint
        with patch("apps.products.pricing.CALCULATION_POLICY_VERSION", "NEXT_POLICY"):
            self.assertNotEqual(self.quote().quote_fingerprint, original)


class DemoPriceProviderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grade_a = CustomerGrade.objects.create(code="A", name="A")
        cls.grade_b = CustomerGrade.objects.create(code="B", name="B")
        cls.customer = Customer.objects.create(customer_code="PRICING-C", name="مشتری", grade=cls.grade_a)
        cls.brand = Brand.objects.create(code="PRICING", name="برند")
        cls.category = Category.objects.create(code="PRICING", name="دسته")
        cls.product = Product.objects.create(product_code="PRICING-P", name="محصول", brand=cls.brand, category=cls.category)
        cls.price = ProductDemoPrice.objects.create(product=cls.product, base_price=Decimal("105"), currency="TOMAN", source="isolated-fixture", source_version="v1")

    def setUp(self):
        self.provider = DemoPriceProvider()

    def create_product(self, code):
        return Product.objects.create(product_code=code, name="محصول", brand=self.brand, category=self.category)

    def test_provider_returns_structured_quote_with_fresh_grade(self):
        quote = self.provider.quote(self.customer.pk, self.product.pk, 3).quote
        self.assertEqual(quote.line_total, Decimal("285"))
        self.assertEqual(quote.price_source, "isolated-fixture")
        Customer.objects.filter(pk=self.customer.pk).update(grade=self.grade_b)
        updated = self.provider.quote(self.customer.pk, self.product.pk, 3).quote
        self.assertEqual(updated.discount_percentage, Decimal("5"))
        self.assertEqual(updated.line_total, Decimal("300"))
        self.assertNotEqual(updated.quote_fingerprint, quote.quote_fingerprint)

    def test_missing_grade_is_zero_discount(self):
        Customer.objects.filter(pk=self.customer.pk).update(grade=None)
        quote = self.provider.quote(self.customer.pk, self.product.pk).quote
        self.assertEqual(quote.discount_percentage, Decimal("0"))
        self.assertEqual(quote.final_unit_price, Decimal("105"))

    def test_missing_price_is_unavailable_even_with_historical_sales(self):
        product = self.create_product("PRICING-MISSING")
        sale = Sale.objects.create(customer=self.customer, invoice_number="PRICING-OLD", sale_date=date(2026, 10, 1))
        SaleItem.objects.create(sale=sale, product=product, quantity=2, unit_price=Decimal("99"))
        result = self.provider.quote(self.customer.pk, product.pk)
        self.assertEqual(result.state, PriceState.UNAVAILABLE)
        self.assertEqual(result.reason_code, "MISSING_PRICE")
        self.assertIsNone(result.quote)
        self.assertFalse(ProductDemoPrice.objects.filter(product=product).exists())

    def test_explicit_zero_price_is_available_and_distinct_from_missing(self):
        self.price.base_price = Decimal("0")
        self.price.save()
        result = self.provider.quote(self.customer.pk, self.product.pk)
        self.assertEqual(result.state, PriceState.AVAILABLE)
        self.assertIsNone(result.reason_code)
        self.assertEqual(result.quote.final_unit_price, Decimal("0"))

    def test_fractional_persisted_price_is_configuration_error_not_repaired(self):
        self.price.base_price = Decimal("105.50")
        self.price.save()  # Model supports precision; MVP provider must reject it.
        result = self.provider.quote(self.customer.pk, self.product.pk)
        self.assertEqual(result.state, PriceState.CONFIGURATION_ERROR)
        self.assertEqual(result.reason_code, "FRACTIONAL_BASE_PRICE")
        self.assertIsNone(result.quote)
        self.price.refresh_from_db()
        self.assertEqual(self.price.base_price, Decimal("105.50"))

    def test_batch_handles_valid_invalid_and_missing_prices_independently(self):
        invalid = self.create_product("PRICING-FRACTIONAL")
        missing = self.create_product("PRICING-ABSENT")
        ProductDemoPrice.objects.create(product=invalid, base_price=Decimal("1.50"), currency="TOMAN", source="fixture", source_version="v1")
        results = self.provider.quote_many(self.customer.pk, {self.product.pk: 3, invalid.pk: 1, missing.pk: 1})
        self.assertEqual(results[self.product.pk].quote.line_total, Decimal("285"))
        self.assertEqual(results[invalid.pk].state, PriceState.CONFIGURATION_ERROR)
        self.assertEqual(results[missing.pk].state, PriceState.UNAVAILABLE)

    def test_batch_query_count_is_two_for_single_and_many_products(self):
        quantities = {self.product.pk: 2}
        for index in range(20):
            product = self.create_product(f"PRICING-BATCH-{index}")
            ProductDemoPrice.objects.create(product=product, base_price=Decimal("100"), currency="TOMAN", source="fixture", source_version="v1")
            quantities[product.pk] = index + 1
        with self.assertNumQueries(2):
            one = self.provider.quote(self.customer.pk, self.product.pk, 2)
        with self.assertNumQueries(2):
            many = self.provider.quote_many(self.customer.pk, quantities)
        self.assertEqual(many[self.product.pk], one)
        self.assertEqual(len(many), 21)

    def test_batch_order_does_not_change_per_product_fingerprint(self):
        missing = self.create_product("PRICING-ORDER")
        forward = self.provider.quote_many(self.customer.pk, {self.product.pk: 3, missing.pk: 1})
        reverse = self.provider.quote_many(self.customer.pk, {missing.pk: 1, self.product.pk: 3})
        self.assertEqual(forward, reverse)

    def test_empty_batch_needs_no_queries(self):
        with self.assertNumQueries(0):
            self.assertEqual(self.provider.quote_many(self.customer.pk, {}), {})

    def test_invalid_inputs_fail_before_database_reads(self):
        for customer_id, quantities in ((True, {}), (self.customer.pk, {self.product.pk: True}),
                                        (self.customer.pk, {self.product.pk: 0}), (self.customer.pk, {"1": 1}),
                                        (self.customer.pk, [(self.product.pk, 1)])):
            with self.subTest(quantities=quantities), self.assertNumQueries(0), self.assertRaises(PricingInputError):
                self.provider.quote_many(customer_id, quantities)

    def test_nonexistent_customer_is_input_error(self):
        with self.assertRaises(PricingInputError) as failure:
            self.provider.quote(self.customer.pk + 999, self.product.pk)
        self.assertEqual(failure.exception.code, "CUSTOMER_NOT_FOUND")

    def test_timestamp_only_updates_do_not_change_fingerprint(self):
        original = self.provider.quote(self.customer.pk, self.product.pk).quote.quote_fingerprint
        self.price.save(update_fields=["updated_at"])
        self.customer.save(update_fields=["updated_at"])
        self.assertEqual(self.provider.quote(self.customer.pk, self.product.pk).quote.quote_fingerprint, original)

    def test_current_price_and_source_version_changes_are_re_read(self):
        original = self.provider.quote(self.customer.pk, self.product.pk).quote.quote_fingerprint
        self.price.base_price = Decimal("106")
        self.price.source_version = "v2"
        self.price.save()
        result = self.provider.quote(self.customer.pk, self.product.pk).quote
        self.assertEqual(result.base_unit_price, Decimal("106"))
        self.assertEqual(result.price_source_version, "v2")
        self.assertNotEqual(result.quote_fingerprint, original)

    def test_promotions_do_not_stack_and_tax_is_not_calculated(self):
        promotion = Promotion.objects.create(
            code="PRICING-PROMO", name="تخفیف", promotion_type="PERCENTAGE",
            start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), discount_percent=Decimal("50"),
        )
        PromotionProduct.objects.create(promotion=promotion, product=self.product)
        promotion.customer_grades.add(self.grade_a)
        quote = self.provider.quote(self.customer.pk, self.product.pk, 3).quote
        self.assertEqual(quote.discount_percentage, Decimal("10"))
        self.assertEqual(quote.line_total, Decimal("285"))
        self.assertNotIn("tax", quote.as_dict())

    def test_reads_leave_prices_and_all_workflow_tables_unchanged(self):
        models = (ProductDemoPrice, Customer, Visit, Inventory, SalesRequest, SalesRequestLine,
                  SalesRequestMutationReceipt, RecommendationFeedbackEvent, Sale, SaleItem)
        before = {model: list(model.objects.order_by("pk").values()) for model in models}
        with CaptureQueriesContext(connection) as queries:
            self.provider.quote_many(self.customer.pk, {self.product.pk: 3})
        self.assertTrue(all(query["sql"].lstrip().upper().startswith("SELECT") for query in queries))
        for model, rows in before.items():
            self.assertEqual(list(model.objects.order_by("pk").values()), rows)
