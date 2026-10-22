"""Management-only authoritative capture. No recommendation generation or DML."""
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import date
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connections, transaction
from django.db.models import Q

from apps.customers.models import Customer, CustomerGrade
from apps.inventory.models import Inventory
from apps.products.models import Brand, Category, Product, ProductDemoPrice
from apps.products.pricing import CALCULATION_POLICY_VERSION, PricingConfigurationError, calculate_demo_quote
from apps.promotions.models import Promotion, PromotionProduct
from apps.recommendations.models import CustomerRecommendation
from apps.targets.models import SalesTarget
from apps.visits.models import CustomerAssignment, Salesperson
from .models import StrategyPolicy, StrategyPolicyVersion
from .strategy_access import require_strategy_viewer
from .strategy_evaluator import (
    CommercialFacts, ProductFacts, PromotionFacts, SavedRecommendation, StrategyInputError,
    StrategyRules, StrategySnapshot, TargetFacts, evaluate_strategy,
)
from .strategy_persistence import StrategyConflict
from .strategy_serialization import canonical_json, configuration_fingerprint, fingerprint, neutral_config


SOURCE_VERSION = "STRATEGY_CAPTURE_V1"
MAX_SOURCE_ROWS = 5000  # Fail closed rather than truncate a source or expand candidates.


def positive_id(value):
    if type(value) is not int or not 1 <= value <= 2**63 - 1:
        raise ValidationError("شناسهٔ معتبر لازم است.", code="INVALID_ID")
    return value


def validate_context(customer_id, salesperson_id, proposed_version_id, expected_revision, evaluation_date):
    for value in (customer_id, salesperson_id, proposed_version_id):
        positive_id(value)
    if type(expected_revision) is not int or expected_revision < 0 or type(evaluation_date) is not date:
        raise ValidationError("تاریخ ارزیابی و بازبینی سیاست معتبر نیست.", code="INVALID_COMPARISON_CONTEXT")


@contextmanager
def snapshot_transaction(using, *, readonly):
    """A top-level MVCC image; never silently inherit READ COMMITTED/nested state.

    A comparison is an as-observed simulation, not a reservation of current facts.
    Source changes after this image are allowed; they affect the next capture.
    """
    db = connections[using]
    if db.in_atomic_block or not db.get_autocommit():
        raise ValidationError("مقایسه به تراکنش مستقل نیاز دارد.", code="TOP_LEVEL_TRANSACTION_REQUIRED")
    try:
        with transaction.atomic(using=using):
            if db.vendor == "postgresql":
                with db.cursor() as cursor:
                    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ" + (", READ ONLY" if readonly else ""))
            elif db.vendor != "sqlite":
                raise ValidationError("پایگاه داده پشتیبانی نمی‌شود.", code="UNSUPPORTED_DATABASE")
            yield
    except DatabaseError as error:
        state = getattr(error.__cause__, "sqlstate", None)
        if state in {"40001", "40P01"}:
            raise StrategyConflict("CONCURRENT_POLICY_OR_SOURCE_CHANGE") from error
        raise


def _rows(queryset, *fields, json_fields=()):
    rows = list(queryset.order_by("pk").values(*fields)[:MAX_SOURCE_ROWS + 1])
    if len(rows) > MAX_SOURCE_ROWS:
        raise ValidationError("حجم دادهٔ مقایسه بیش از حد مجاز است.", code="SNAPSHOT_TOO_LARGE")
    for row in rows:
        for field in json_fields:
            # Saved engine JSON legitimately contains floats: retain it as opaque
            # canonical JSON text, never convert its components into overlay data.
            row[field] = json.dumps(row[field], sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return rows


def _version(identity, policy, using):
    if identity is None:
        return None, StrategyRules.from_config(neutral_config())
    version = StrategyPolicyVersion.objects.using(using).filter(pk=identity, policy=policy).first()
    if version is None or configuration_fingerprint(version.config, version.algorithm_version) != version.config_hash:
        raise ValidationError("نسخهٔ سیاست معتبر نیست.", code="INVALID_POLICY_VERSION")
    return version, StrategyRules.from_config(version.config, version.algorithm_version)


@dataclass(frozen=True, slots=True)
class CapturedStrategyInputs:
    snapshot: StrategySnapshot
    active_rules: StrategyRules
    document_json: str
    source_fingerprint: str

    def as_dict(self):
        return json.loads(self.document_json)


def _context_facts(customer_id, salesperson_id, evaluation_date, using):
    """Shared authoritative assignment facts; caller separately authorizes actor."""
    customer = Customer.objects.using(using).filter(pk=customer_id, is_active=True).values(
        "id", "customer_code", "name", "grade_id", "is_active", "updated_at",
    ).first()
    salesperson = Salesperson.objects.using(using).filter(pk=salesperson_id, is_active=True).values(
        "id", "employee_code", "first_name", "last_name", "user_id", "is_active", "updated_at",
    ).first()
    assignments = _rows(CustomerAssignment.objects.using(using).filter(customer_id=customer_id, salesperson_id=salesperson_id))
    if customer is None or salesperson is None or not any(
        row["is_active"] and row["start_date"] <= evaluation_date and (row["end_date"] is None or row["end_date"] >= evaluation_date)
        for row in assignments
    ):
        raise PermissionDenied("دسترسی به مشتری و فروشندهٔ تخصیص‌یافته مجاز نیست.")
    return customer, salesperson, assignments


def _capture(actor, customer_id, salesperson_id, proposed_version_id, expected_revision, evaluation_date, using, policy=None):
    """Management boundary; caller owns snapshot transaction and optional head lock."""
    require_strategy_viewer(getattr(actor, "pk", None), using)
    context = _context_facts(customer_id, salesperson_id, evaluation_date, using)
    policy = policy or StrategyPolicy.objects.using(using).filter(pk=1).first()
    if policy is None or policy.revision != expected_revision:
        raise StrategyConflict("STALE_POLICY_REVISION")
    if policy.draft_version_id != proposed_version_id:
        raise StrategyConflict("STRATEGY_DRAFT_CHANGED")
    active, active_rules = _version(policy.active_version_id, policy, using)
    proposed, rules = _version(proposed_version_id, policy, using)
    return _capture_facts(customer_id, salesperson_id, evaluation_date, using, policy, active, active_rules, proposed, rules, context)


def _capture_facts(customer_id, salesperson_id, evaluation_date, using, policy, active, active_rules, proposed, rules, context):
    """One fact adapter. Only authorized management/selling wrappers call this.

    Both wrappers own a consistent transaction and supply verified assignment
    facts. This function does not confer management or salesperson access.
    """
    customer, salesperson, assignments = context
    all_rules = active_rules.priority_rules + rules.priority_rules
    recommendations = _rows(CustomerRecommendation.objects.using(using).filter(customer_id=customer_id, is_active=True),
                            json_fields=("score_breakdown", "explanation_snapshot"))
    recommendations.sort(key=lambda row: (row["rank"], row["id"]))
    shortlist_ids = {row["product_id"] for row in recommendations}
    shortlist_products = _rows(Product.objects.using(using).filter(pk__in=shortlist_ids),
                              "id", "brand_id", "category_id", "product_group")
    categories = {row["category_id"] for row in shortlist_products}
    groups = {row["product_group"] for row in shortlist_products}
    targets = _rows(SalesTarget.objects.using(using).filter(salesperson_id=salesperson_id).filter(
        Q(scope_type="PRODUCT", product_id__in=shortlist_ids) | Q(scope_type="CATEGORY", category_id__in=categories)
        | Q(scope_type="PRODUCT_GROUP", product_group__in=groups)))
    emphasized_ids = {rule.promotion_id for rule in active_rules.promotion_rules + rules.promotion_rules}
    promotions = _rows(Promotion.objects.using(using).filter(
        Q(pk__in=emphasized_ids) | Q(promotion_products__product_id__in=shortlist_ids)).distinct())
    promo_ids = {row["id"] for row in promotions}
    promo_products = _rows(PromotionProduct.objects.using(using).filter(promotion_id__in=promo_ids))
    promo_grades = _rows(Promotion.customer_grades.through.objects.using(using).filter(promotion_id__in=promo_ids))
    product_ids = shortlist_ids | {rule.scope_id for rule in all_rules if rule.scope_type == "PRODUCT"}
    product_ids |= {row["product_id"] for row in promo_products}
    product_ids |= {row["product_id"] for row in targets if row["scope_type"] == "PRODUCT"}
    products = _rows(Product.objects.using(using).filter(pk__in=product_ids),
                     "id", "product_code", "name", "brand_id", "category_id", "product_group", "is_active", "unit", "updated_at")
    brand_ids = {row["brand_id"] for row in products} | {rule.scope_id for rule in all_rules if rule.scope_type == "BRAND"}
    category_ids = {row["category_id"] for row in products} | {rule.scope_id for rule in all_rules if rule.scope_type == "CATEGORY"}
    grade_ids = {row["customergrade_id"] for row in promo_grades}
    if customer["grade_id"] is not None:
        grade_ids.add(customer["grade_id"])
    brands = _rows(Brand.objects.using(using).filter(pk__in=brand_ids), "id", "code", "name", "is_active", "updated_at")
    category_rows = _rows(Category.objects.using(using).filter(pk__in=category_ids), "id", "code", "name", "parent_id", "is_active", "updated_at")
    grades = _rows(CustomerGrade.objects.using(using).filter(pk__in=grade_ids), "id", "code", "name", "is_active", "updated_at")
    inventories = _rows(Inventory.objects.using(using).filter(product_id__in=shortlist_ids))
    prices = _rows(ProductDemoPrice.objects.using(using).filter(product_id__in=shortlist_ids))
    by_product = {row["id"]: row for row in products}
    inventory_map = {row["product_id"]: row for row in inventories}
    price_map = {row["product_id"]: row for row in prices}
    grade = next((row for row in grades if row["id"] == customer["grade_id"]), None)
    quoted, saved = {}, []
    for row in recommendations:
        product = by_product.get(row["product_id"])
        if product is None:
            raise ValidationError("محصول پیشنهاد ذخیره‌شده یافت نشد.", code="INVALID_SOURCE_SNAPSHOT")
        inventory = inventory_map.get(row["product_id"])
        quantity = None if inventory is None else max(inventory["available_quantity"] - inventory["reserved_quantity"], 0)
        stock_state = "UNKNOWN" if quantity is None else ("AVAILABLE" if quantity > 0 else "UNAVAILABLE")
        price = price_map.get(row["product_id"])
        pricing_state, pricing_reason, quote = "UNAVAILABLE", "MISSING_PRICE", None
        if price is not None:
            try:
                quote = calculate_demo_quote(customer_id=customer_id, product_id=row["product_id"], grade_code=grade["code"] if grade else None,
                                             quantity=1, base_price=price["base_price"], currency=price["currency"],
                                             price_source=price["source"], price_source_version=price["source_version"])
                pricing_state, pricing_reason = "AVAILABLE", None
            except PricingConfigurationError as error:
                pricing_state, pricing_reason = "CONFIGURATION_ERROR", error.code
        reason = "INACTIVE_PRODUCT" if not product["is_active"] else (
            "INVENTORY_UNKNOWN" if quantity is None else "OUT_OF_STOCK" if quantity == 0 else None)
        if reason is None and pricing_state != "AVAILABLE":
            reason = "PRICE_UNAVAILABLE" if pricing_state == "UNAVAILABLE" else "PRICE_CONFIGURATION_ERROR"
        quoted[str(row["product_id"])] = {"state": pricing_state, "reason_code": pricing_reason,
                                          "quote": quote.as_dict() if quote else None}
        evidence = json.dumps({"score_breakdown": json.loads(row["score_breakdown"]),
                               "explanation_snapshot": json.loads(row["explanation_snapshot"]),
                               "recommendation_type": row["recommendation_type"], "confidence_score": str(row["confidence_score"]),
                               "evidence_quality": row["evidence_quality"]},
                              sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        saved.append(SavedRecommendation(row["id"], row["product_id"], row["rank"], row["score"], row["reason"],
                                        CommercialFacts(stock_state, quantity, pricing_state, reason is None, reason, pricing_reason), evidence))
    snapshot = StrategySnapshot(
        customer_id, salesperson_id, customer["grade_id"], evaluation_date, tuple(saved),
        tuple(ProductFacts(row["id"], row["product_code"], row["brand_id"], row["category_id"], row["product_group"], row["is_active"]) for row in products),
        tuple(row["id"] for row in brands), tuple(row["id"] for row in category_rows), tuple(row["id"] for row in grades),
        tuple(TargetFacts(row["id"], row["salesperson_id"], row["scope_type"],
                          row[{"PRODUCT": "product_id", "CATEGORY": "category_id", "PRODUCT_GROUP": "product_group"}.get(row["scope_type"], "scope_type")],
                          row["target_unit"], row["target_value"], row["actual_value"], row["period_start"], row["period_end"], row["is_active"]) for row in targets),
        tuple(PromotionFacts(row["id"], tuple(sorted(link["product_id"] for link in promo_products if link["promotion_id"] == row["id"])),
                             tuple(sorted(link["customergrade_id"] for link in promo_grades if link["promotion_id"] == row["id"])),
                             row["start_date"], row["end_date"], row["minimum_quantity"], row["maximum_quantity"], row["is_active"]) for row in promotions), rules,
    )
    try:
        evaluate_strategy(snapshot)
        evaluate_strategy(replace(snapshot, strategy=active_rules))
    except StrategyInputError as error:
        raise ValidationError("دادهٔ مبنای مقایسه معتبر نیست.", code="INVALID_SOURCE_SNAPSHOT") from error
    sources = {"customer": customer, "salesperson": salesperson, "assignments": assignments,
               "recommendations": recommendations, "products": products, "brands": brands, "categories": category_rows,
               "grades": grades, "targets": targets, "promotions": promotions, "promotion_products": promo_products,
               "promotion_grades": promo_grades, "inventory": inventories, "prices": prices}
    db = connections[using]
    identity = {"vendor": db.vendor, "name": str(db.settings_dict["NAME"]),
                "host": str(db.settings_dict.get("HOST", "")), "port": str(db.settings_dict.get("PORT", ""))}
    facts = asdict(snapshot)
    facts.pop("strategy")
    document = {"schema_version": 1, "source_version": SOURCE_VERSION, "database": identity, "timezone": "Asia/Tehran",
                "policy_revision": policy.revision, "active_version_id": active.pk if active else None,
                "proposed_version_id": proposed.pk, "active_config": active_rules.as_config(), "proposed_config": rules.as_config(),
                "active_algorithm": active_rules.algorithm_version, "proposed_algorithm": rules.algorithm_version,
                "source_fingerprints": {key: fingerprint(value) for key, value in sources.items()}, "sources": sources,
                "facts": facts, "quotes": quoted, "pricing_policy": CALCULATION_POLICY_VERSION,
                "availability_scope": "COMMERCIAL_QUANTITY_ONE_NOT_VISIT_MUTATION_AUTHORIZATION"}
    return CapturedStrategyInputs(snapshot, active_rules, canonical_json(document), fingerprint(document))


def capture_strategy_snapshot(*, actor, customer_id, salesperson_id, proposed_version_id, expected_revision, evaluation_date, using="default"):
    validate_context(customer_id, salesperson_id, proposed_version_id, expected_revision, evaluation_date)
    with snapshot_transaction(using, readonly=True):
        return _capture(actor, customer_id, salesperson_id, proposed_version_id, expected_revision, evaluation_date, using)


def evaluate_comparison(captured):
    before = evaluate_strategy(replace(captured.snapshot, strategy=captured.active_rules))
    after = evaluate_strategy(captured.snapshot)
    before_ranks = {row.source.recommendation_id: row.after_rank for row in before.rows}
    return {"schema_version": 1, "simulation_only": True, "revenue_uplift": None,
            "note_fa": "این مقایسه شبیه‌سازی اولویت‌هاست و افزایش درآمد واقعی را نشان نمی‌دهد.",
            "before": before.as_dict(), "after": after.as_dict(),
            "movements": [{"recommendation_id": row.source.recommendation_id, "before_rank": before_ranks[row.source.recommendation_id],
                           "after_rank": row.after_rank, "positions_gained": before_ranks[row.source.recommendation_id] - row.after_rank}
                          for row in after.rows]}
