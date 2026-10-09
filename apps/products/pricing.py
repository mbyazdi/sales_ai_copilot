"""Read-only pricing core. Authorization, inventory and mutations are caller-owned.

    Demo prices are current configuration, not historical sales or promotions.
    Replace PricingProvider to integrate a future pricing service without changing
    consumers of the immutable quote/result contract. No rows are created or saved.
"""
import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
from enum import StrEnum
from typing import Protocol

from apps.customers.models import Customer
from .models import ProductDemoPrice


CURRENCY = "TOMAN"
CALCULATION_POLICY_VERSION = "DEMO_GRADE_UNIT_HALF_UP_V1"
# Existing demo-price and request snapshot fields have 18 digits, 2 decimal places.
MAX_WHOLE_AMOUNT = Decimal("9999999999999999")
_AMOUNT_FIELDS = (
    "base_unit_price", "discount_percentage", "unit_discount", "final_unit_price",
    "line_base", "line_discount", "line_total",
)


class PricingInputError(ValueError):
    """Invalid identity/quantity or an amount that cannot fit existing snapshots."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class PricingConfigurationError(ValueError):
    """Explicit demo data exists but cannot yield a truthful MVP quote."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


class PriceState(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"


def _decimal_strings(values):
    return {key: format(value, "f") if key in _AMOUNT_FIELDS else value for key, value in values.items()}


@dataclass(frozen=True)
class PriceQuote:
    customer_id: int
    product_id: int
    grade_code: str | None
    quantity: int
    base_unit_price: Decimal
    discount_percentage: Decimal
    unit_discount: Decimal
    final_unit_price: Decimal
    line_base: Decimal
    line_discount: Decimal
    line_total: Decimal
    currency: str
    price_source: str
    price_source_version: str
    calculation_policy_version: str
    quote_fingerprint: str

    def as_dict(self):
        """Wire/snapshot-ready decimal strings; no floats or formatted UI copy."""
        return _decimal_strings(asdict(self))


@dataclass(frozen=True)
class PricingResult:
    product_id: int
    quantity: int
    state: PriceState
    quote: PriceQuote | None = None
    reason_code: str | None = None


class PricingProvider(Protocol):
    """Call after authorizing context; quote_many avoids per-card database reads."""

    def quote(self, customer_id: int, product_id: int, quantity: int = 1) -> PricingResult: ...

    def quote_many(self, customer_id: int, quantities: Mapping[int, int]) -> dict[int, PricingResult]: ...


def _positive_integer(value, code):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PricingInputError(code)


def calculate_demo_quote(*, customer_id, product_id, grade_code, quantity, base_price,
                         currency, price_source, price_source_version):
    """Pure demo-policy calculation; inputs are explicit, with no database access.

    Fractional base data is rejected, not repaired. Round the final unit once;
    derive its discount and multiply those unit amounts by absolute quantity.
    """
    _positive_integer(customer_id, "INVALID_CUSTOMER_ID")
    _positive_integer(product_id, "INVALID_PRODUCT_ID")
    _positive_integer(quantity, "INVALID_QUANTITY")
    if grade_code is not None and not isinstance(grade_code, str):
        raise PricingInputError("INVALID_GRADE_CODE")
    if not isinstance(base_price, Decimal) or not base_price.is_finite():
        raise PricingConfigurationError("INVALID_BASE_PRICE")
    if base_price < 0 or base_price > MAX_WHOLE_AMOUNT:
        raise PricingConfigurationError("BASE_PRICE_OUT_OF_RANGE")
    if base_price != base_price.to_integral_value():
        raise PricingConfigurationError("FRACTIONAL_BASE_PRICE")
    if currency != CURRENCY:
        raise PricingConfigurationError("INVALID_CURRENCY")
    if any(not isinstance(value, str) or not value.strip() or len(value) > 100
           for value in (price_source, price_source_version)):
        raise PricingConfigurationError("INVALID_PRICE_SOURCE")

    discount_percentage = {"A": Decimal("10"), "B": Decimal("5")}.get(grade_code, Decimal("0"))
    # Isolate arithmetic from a caller's precision/rounding context.
    with localcontext(Context(prec=40)):
        base_unit = base_price.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        final_unit = (base_unit * (Decimal("1") - discount_percentage / Decimal("100"))).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP,
        )
        unit_discount = base_unit - final_unit
        line_base = base_unit * Decimal(quantity)
        line_discount = unit_discount * Decimal(quantity)
        line_total = final_unit * Decimal(quantity)
        if line_base > MAX_WHOLE_AMOUNT:
            raise PricingInputError("LINE_AMOUNT_OUT_OF_RANGE")

    values = {
        "customer_id": customer_id, "product_id": product_id, "grade_code": grade_code,
        "quantity": quantity, "base_unit_price": base_unit,
        "discount_percentage": discount_percentage, "unit_discount": unit_discount,
        "final_unit_price": final_unit, "line_base": line_base,
        "line_discount": line_discount, "line_total": line_total, "currency": CURRENCY,
        "price_source": price_source, "price_source_version": price_source_version,
        "calculation_policy_version": CALCULATION_POLICY_VERSION,
    }
    canonical = json.dumps(_decimal_strings(values), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return PriceQuote(**values, quote_fingerprint=fingerprint)


class DemoPriceProvider:
    """Two queries per nonempty batch: fresh grade, then all configured prices.

    Pricing does not establish permission to sell or inventory availability.
    Missing/invalid rows produce per-product states; invalid command inputs raise.
    No persistent cache, write-on-read, seeding, fallback or promotion stacking.
    """

    def quote(self, customer_id: int, product_id: int, quantity: int = 1) -> PricingResult:
        return self.quote_many(customer_id, {product_id: quantity})[product_id]

    def quote_many(self, customer_id: int, quantities: Mapping[int, int]) -> dict[int, PricingResult]:
        _positive_integer(customer_id, "INVALID_CUSTOMER_ID")
        if not isinstance(quantities, Mapping):
            raise PricingInputError("INVALID_QUANTITIES")
        quantities = dict(quantities)
        for product_id, quantity in quantities.items():
            _positive_integer(product_id, "INVALID_PRODUCT_ID")
            _positive_integer(quantity, "INVALID_QUANTITY")
        if not quantities:
            return {}
        try:
            customer = Customer.objects.values("grade__code").get(pk=customer_id)
        except Customer.DoesNotExist as error:
            raise PricingInputError("CUSTOMER_NOT_FOUND") from error
        prices = {
            row["product_id"]: row for row in ProductDemoPrice.objects.filter(product_id__in=quantities).values(
                "product_id", "base_price", "currency", "source", "source_version",
            )
        }
        results = {}
        for product_id, quantity in quantities.items():
            row = prices.get(product_id)
            if row is None:
                results[product_id] = PricingResult(product_id, quantity, PriceState.UNAVAILABLE, reason_code="MISSING_PRICE")
                continue
            try:
                quote = calculate_demo_quote(
                    customer_id=customer_id, product_id=product_id, grade_code=customer["grade__code"],
                    quantity=quantity, base_price=row["base_price"], currency=row["currency"],
                    price_source=row["source"], price_source_version=row["source_version"],
                )
            except PricingConfigurationError as error:
                results[product_id] = PricingResult(product_id, quantity, PriceState.CONFIGURATION_ERROR, reason_code=error.code)
            else:
                results[product_id] = PricingResult(product_id, quantity, PriceState.AVAILABLE, quote=quote)
        return results
