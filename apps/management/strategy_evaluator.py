"""Pure SAVED_RANK_OVERLAY_V1: frozen facts in, detached ranking evidence out.

No ORM, settings, wall clock, pricing calculation or publication. Reference
registries may include facts outside the shortlist; they NEVER become candidates.
"""
from dataclasses import asdict, dataclass, fields, is_dataclass, replace
from datetime import date
from decimal import Context, Decimal, ROUND_HALF_UP, localcontext
import json
from typing import Literal

from django.core.exceptions import ValidationError

from .strategy_serialization import ALGORITHM_VERSION, canonical_value, configuration_fingerprint, fingerprint, normalize_config


CENT = Decimal("0.01")
ZERO = Decimal("0.00")
CAP = Decimal("30.00")
MAX_ID = 2**63 - 1
MAX_AMOUNT = Decimal("9999999999999999.99")  # Existing target Decimal(18, 2).
GROUPS = ("BEAUTY", "PERSONAL_ELECTRICAL", "HOME_APPLIANCE", "OTHER")


class StrategyInputError(ValueError):
    def __init__(self, code, path):
        self.code, self.path = code, path
        super().__init__(f"{code}: {path}")


@dataclass(frozen=True, slots=True)
class PriorityRule:
    scope_type: Literal["PRODUCT", "BRAND", "CATEGORY"]
    scope_id: int
    points: int


@dataclass(frozen=True, slots=True)
class PromotionRule:
    promotion_id: int
    points: int


@dataclass(frozen=True, slots=True)
class StrategyRules:
    priority_rules: tuple[PriorityRule, ...]
    target_weight: int
    promotion_rules: tuple[PromotionRule, ...]
    algorithm_version: str = ALGORITHM_VERSION
    schema_version: int = 1

    @classmethod
    def from_config(cls, config, algorithm_version=ALGORITHM_VERSION):
        try:
            normalized = normalize_config(config)
            configuration_fingerprint(normalized, algorithm_version)
        except (ValidationError, TypeError, ValueError) as error:
            raise StrategyInputError("INVALID_STRATEGY_CONFIG", "strategy") from error
        return cls(tuple(PriorityRule(**row) for row in normalized["priority_rules"]), normalized["target_weight"],
                   tuple(PromotionRule(**row) for row in normalized["promotion_rules"]), algorithm_version)

    def as_config(self):
        return {"schema_version": self.schema_version, "target_weight": self.target_weight,
                "priority_rules": [asdict(row) for row in self.priority_rules],
                "promotion_rules": [asdict(row) for row in self.promotion_rules]}


@dataclass(frozen=True, slots=True)
class CommercialFacts:
    stock_state: Literal["AVAILABLE", "UNAVAILABLE", "UNKNOWN"]
    sellable_quantity: int | None
    pricing_state: Literal["AVAILABLE", "UNAVAILABLE", "CONFIGURATION_ERROR"]
    can_add: bool
    non_addable_reason: str | None
    pricing_reason: str | None = None


@dataclass(frozen=True, slots=True)
class ProductFacts:
    product_id: int
    product_code: str
    brand_id: int
    category_id: int
    product_group: str
    is_active: bool


@dataclass(frozen=True, slots=True)
class SavedRecommendation:
    recommendation_id: int
    product_id: int
    saved_rank: int
    base_score: Decimal
    stored_reason: str
    commercial: CommercialFacts
    # Optional opaque saved JSON, not reconstructed components. Existing engine
    # JSON may contain floats; preserve its exact text without using its numbers.
    source_evidence_json: str | None = None


@dataclass(frozen=True, slots=True)
class TargetFacts:
    target_id: int
    salesperson_id: int
    scope_type: Literal["PRODUCT", "CATEGORY", "PRODUCT_GROUP"]
    scope_id: int | str
    unit: Literal["QUANTITY", "MSU"]
    target_value: Decimal
    actual_value: Decimal
    period_start: date
    period_end: date
    is_active: bool


@dataclass(frozen=True, slots=True)
class PromotionFacts:
    promotion_id: int
    product_ids: tuple[int, ...]
    grade_ids: tuple[int, ...]  # Empty means unrestricted; missing customer grade is not grade zero.
    start_date: date
    end_date: date
    minimum_quantity: int
    maximum_quantity: int | None
    is_active: bool


@dataclass(frozen=True, slots=True)
class StrategySnapshot:
    customer_id: int
    salesperson_id: int
    customer_grade_id: int | None
    evaluation_date: date  # Already resolved to Asia/Tehran by the future capture boundary.
    recommendations: tuple[SavedRecommendation, ...]  # Authoritative saved order.
    products: tuple[ProductFacts, ...]
    brand_ids: tuple[int, ...]
    category_ids: tuple[int, ...]
    grade_ids: tuple[int, ...]
    targets: tuple[TargetFacts, ...]  # Explicit empty tuple = known none; None is invalid/unavailable.
    promotions: tuple[PromotionFacts, ...]
    strategy: StrategyRules


@dataclass(frozen=True, slots=True)
class StrategyReason:
    code: str
    text_fa: str
    source_id: int | None = None
    data: tuple[tuple[str, str | int | Decimal | None], ...] = ()


@dataclass(frozen=True, slots=True)
class Contribution:
    points: Decimal
    reasons: tuple[StrategyReason, ...]
    source_id: int | None = None


@dataclass(frozen=True, slots=True)
class RankedRecommendation:
    source: SavedRecommendation
    product: ProductFacts
    original_position: int
    after_rank: int
    base_priority: Decimal
    priority: Contribution
    target: Contribution
    promotion: Contribution
    overlay_adjustment: Decimal
    effective_priority: Decimal


@dataclass(frozen=True, slots=True)
class StrategyEvaluation:
    algorithm_version: str
    config_hash: str
    input_digest: str
    before_ids: tuple[int, ...]
    after_ids: tuple[int, ...]
    rows: tuple[RankedRecommendation, ...]  # After order; source.saved_rank remains unchanged.

    def as_dict(self):
        return _wire(self)

    @property
    def result_digest(self):
        return fingerprint(self.as_dict())


def _wire(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if type(value) is date:
        return value.isoformat()
    if isinstance(value, StrategyReason):
        return {"code": value.code, "text_fa": value.text_fa, "source_id": value.source_id,
                "data": {key: canonical_value(item) for key, item in value.data}}
    if isinstance(value, SavedRecommendation):
        result = {field.name: _wire(getattr(value, field.name)) for field in fields(value)}
        # Match the existing saved-score field's four places without mutating
        # source evidence. Equivalent Decimal encodings must have identical wire
        # evidence, consistent with M-C1's canonical input digest.
        score = value.base_score.copy_abs() if value.base_score == 0 else value.base_score
        result["base_score"] = format(score, ".4f")
        return result
    if is_dataclass(value):
        return {field.name: _wire(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (tuple, list)):
        return [_wire(item) for item in value]
    return value


def _require(condition, code, path):
    if not condition:
        raise StrategyInputError(code, path)


def _id(value, path):
    _require(type(value) is int and 1 <= value <= MAX_ID, "INVALID_ID", path)


def _ids(values, path):
    _require(type(values) is tuple, "EXPECTED_IMMUTABLE_TUPLE", path)
    for value in values:
        _id(value, path)
    _require(len(set(values)) == len(values), "DUPLICATE_ID", path)


def _records(values, kind, key, path):
    _require(type(values) is tuple and all(type(row) is kind for row in values), "INVALID_FACTS", path)
    ids = tuple(getattr(row, key) for row in values)
    _ids(ids, path)


def _period(start, end, path):
    _require(type(start) is date and type(end) is date and start <= end, "INVALID_PERIOD", path)


def _decimal(value, path, maximum, positive=False, scale=None):
    _require(type(value) is Decimal and value.is_finite(), "INVALID_DECIMAL", path)
    _require(0 < value <= maximum if positive else 0 <= value <= maximum, "DECIMAL_OUT_OF_RANGE", path)
    if scale is not None:
        _require(value == value.quantize(scale), "INVALID_DECIMAL_SCALE", path)


def _invalid_json_constant(value):
    raise ValueError("Non-finite saved JSON constant: " + value)


def _validate(snapshot):
    _require(type(snapshot) is StrategySnapshot, "INVALID_SNAPSHOT", "snapshot")
    _id(snapshot.customer_id, "customer_id")
    _id(snapshot.salesperson_id, "salesperson_id")
    _require(type(snapshot.evaluation_date) is date, "INVALID_DATE", "evaluation_date")
    for name in ("brand_ids", "category_ids", "grade_ids"):
        _ids(getattr(snapshot, name), name)
    if snapshot.customer_grade_id is not None:
        _id(snapshot.customer_grade_id, "customer_grade_id")
        _require(snapshot.customer_grade_id in snapshot.grade_ids, "UNKNOWN_REFERENCE", "customer_grade_id")
    _records(snapshot.products, ProductFacts, "product_id", "products")
    products = {row.product_id: row for row in snapshot.products}
    codes = set()
    for product in snapshot.products:
        _require(type(product.product_code) is str and bool(product.product_code.strip()), "INVALID_PRODUCT_CODE", "products")
        _require(product.product_code not in codes, "DUPLICATE_PRODUCT_CODE", "products")
        codes.add(product.product_code)
        for field, references in (("brand_id", snapshot.brand_ids), ("category_id", snapshot.category_ids)):
            _id(getattr(product, field), field)
            _require(getattr(product, field) in references, "UNKNOWN_REFERENCE", field)
        _require(product.product_group in GROUPS and type(product.is_active) is bool, "INVALID_PRODUCT_FACTS", "products")
    _records(snapshot.recommendations, SavedRecommendation, "recommendation_id", "recommendations")
    seen_products = set()
    for row in snapshot.recommendations:
        _id(row.product_id, "recommendations.product_id")
        _require(row.product_id in products and row.product_id not in seen_products, "INVALID_SHORTLIST_PRODUCT", "recommendations")
        seen_products.add(row.product_id)
        _require(type(row.saved_rank) is int and 0 <= row.saved_rank <= 32767, "INVALID_SAVED_RANK", "recommendations")
        _decimal(row.base_score, "recommendations.base_score", Decimal("9999.9999"), scale=Decimal("0.0001"))
        _require(type(row.stored_reason) is str, "INVALID_STORED_REASON", "recommendations")
        if row.source_evidence_json is not None:
            _require(type(row.source_evidence_json) is str, "INVALID_SOURCE_EVIDENCE", "recommendations")
            try:
                # Parse only to validate existing JSON, never evaluate or rewrite it.
                evidence = json.loads(row.source_evidence_json, parse_float=Decimal, parse_constant=_invalid_json_constant)
                _require(type(evidence) is dict, "INVALID_SOURCE_EVIDENCE", "recommendations")
            except (ValueError, RecursionError) as error:
                raise StrategyInputError("INVALID_SOURCE_EVIDENCE", "recommendations") from error
        facts = row.commercial
        _require(type(facts) is CommercialFacts, "INVALID_COMMERCIAL_FACTS", "recommendations")
        _require(facts.stock_state in ("AVAILABLE", "UNAVAILABLE", "UNKNOWN") and
                 facts.pricing_state in ("AVAILABLE", "UNAVAILABLE", "CONFIGURATION_ERROR") and type(facts.can_add) is bool,
                 "INVALID_COMMERCIAL_FACTS", "recommendations")
        quantity = facts.sellable_quantity
        valid_quantity = (quantity is None if facts.stock_state == "UNKNOWN" else
                          type(quantity) is int and 0 <= quantity <= 2147483647 and
                          (quantity > 0 if facts.stock_state == "AVAILABLE" else quantity == 0))
        _require(valid_quantity, "INCONSISTENT_STOCK_ANNOTATION", "recommendations")
        for reason in (facts.non_addable_reason, facts.pricing_reason):
            _require(reason is None or type(reason) is str and bool(reason.strip()), "INVALID_COMMERCIAL_REASON", "recommendations")
        _require((facts.non_addable_reason is None) == facts.can_add, "INCONSISTENT_ADDABILITY", "recommendations")
        _require(not facts.can_add or products[row.product_id].is_active and facts.stock_state == "AVAILABLE"
                 and facts.pricing_state == "AVAILABLE", "INCONSISTENT_ADDABILITY", "recommendations")
    _records(snapshot.targets, TargetFacts, "target_id", "targets")
    for target in snapshot.targets:
        _id(target.salesperson_id, "targets.salesperson_id")
        _require(target.scope_type in ("PRODUCT", "CATEGORY", "PRODUCT_GROUP"), "INVALID_TARGET_SCOPE", "targets")
        if target.scope_type == "PRODUCT_GROUP":
            _require(type(target.scope_id) is str and target.scope_id in GROUPS, "UNKNOWN_REFERENCE", "targets.scope_id")
        else:
            _id(target.scope_id, "targets.scope_id")
            _require(target.scope_id in (products if target.scope_type == "PRODUCT" else snapshot.category_ids), "UNKNOWN_REFERENCE", "targets.scope_id")
        _require(target.unit in ("QUANTITY", "MSU") and type(target.is_active) is bool, "INVALID_TARGET_FACTS", "targets")
        _period(target.period_start, target.period_end, "targets")
        _decimal(target.target_value, "targets.target_value", MAX_AMOUNT, positive=True, scale=CENT)
        _decimal(target.actual_value, "targets.actual_value", MAX_AMOUNT, scale=CENT)
    _records(snapshot.promotions, PromotionFacts, "promotion_id", "promotions")
    for promotion in snapshot.promotions:
        _ids(promotion.product_ids, "promotions.product_ids")
        _ids(promotion.grade_ids, "promotions.grade_ids")
        _require(set(promotion.product_ids) <= products.keys() and set(promotion.grade_ids) <= set(snapshot.grade_ids), "UNKNOWN_REFERENCE", "promotions")
        _period(promotion.start_date, promotion.end_date, "promotions")
        _require(type(promotion.is_active) is bool, "INVALID_PROMOTION_FACTS", "promotions")
        _require(type(promotion.minimum_quantity) is int and 0 <= promotion.minimum_quantity <= 2147483647,
                 "INVALID_PROMOTION_QUANTITY", "promotions")
        _require(promotion.maximum_quantity is None or type(promotion.maximum_quantity) is int and
                 promotion.minimum_quantity <= promotion.maximum_quantity <= 2147483647, "INVALID_PROMOTION_QUANTITY", "promotions")
    rules = snapshot.strategy
    _require(type(rules) is StrategyRules and type(rules.priority_rules) is tuple and
             all(type(rule) is PriorityRule for rule in rules.priority_rules) and type(rules.promotion_rules) is tuple and
             all(type(rule) is PromotionRule for rule in rules.promotion_rules), "INVALID_STRATEGY_CONFIG", "strategy")
    normalized = StrategyRules.from_config(rules.as_config(), rules.algorithm_version)
    for rule in normalized.priority_rules:
        references = {"PRODUCT": products, "BRAND": snapshot.brand_ids, "CATEGORY": snapshot.category_ids}[rule.scope_type]
        _require(rule.scope_id in references, "UNKNOWN_REFERENCE", "strategy.priority_rules")
    promotion_ids = {row.promotion_id for row in snapshot.promotions}
    _require(all(rule.promotion_id in promotion_ids for rule in normalized.promotion_rules), "UNKNOWN_REFERENCE", "strategy.promotion_rules")
    return products, normalized


def _reason(code, text, source_id=None, **data):
    return StrategyReason(code, text, source_id, tuple(sorted(data.items())))


def _priority(product, rules):
    identities = {"PRODUCT": product.product_id, "BRAND": product.brand_id, "CATEGORY": product.category_id}
    matches = {rule.scope_type: rule for rule in rules if rule.scope_id == identities[rule.scope_type]}
    for scope in ("PRODUCT", "BRAND", "CATEGORY"):
        if scope in matches:
            rule = matches[scope]
            reason = _reason("PRIORITY_EXPLICIT_ZERO" if rule.points == 0 else "PRIORITY_APPLIED",
                             "قاعدهٔ مشخص‌تر با امتیاز صفر اعمال شد." if rule.points == 0 else "اولویت مدیریتی این محصول اعمال شد.",
                             rule.scope_id, scope_type=scope, points=rule.points, overridden_rules=len(matches) - 1)
            return Contribution(Decimal(rule.points).quantize(CENT), (reason,), rule.scope_id)
    return Contribution(ZERO, (_reason("NO_PRIORITY_RULE", "اولویت ویژه‌ای برای این محصول تعیین نشده است."),))


def _target(product, snapshot, weight):
    if weight == 0:
        return Contribution(ZERO, (_reason("TARGET_INFLUENCE_DISABLED", "تأثیر هدف فروش در این سیاست غیرفعال است."),))
    matches, reasons = [], []
    specificity = {"PRODUCT": 0, "CATEGORY": 1, "PRODUCT_GROUP": 2}
    scopes = {"PRODUCT": product.product_id, "CATEGORY": product.category_id, "PRODUCT_GROUP": product.product_group}
    for target in sorted(snapshot.targets, key=lambda item: item.target_id):
        if target.scope_id != scopes[target.scope_type]:
            continue
        code, text = None, None
        if target.salesperson_id != snapshot.salesperson_id:
            code, text = "TARGET_OTHER_SALESPERSON", "این هدف متعلق به فروشندهٔ دیگری است."
        elif not target.is_active:
            code, text = "TARGET_INACTIVE", "این هدف فروش غیرفعال است."
        elif not target.period_start <= snapshot.evaluation_date <= target.period_end:
            code, text = "TARGET_OUTSIDE_PERIOD", "این هدف خارج از بازهٔ ارزیابی است."
        elif target.unit != "QUANTITY":
            code, text = "TARGET_UNIT_UNSUPPORTED", "هدف MSU در اولویت‌بندی این نسخه محاسبه نمی‌شود."
        elif target.actual_value >= target.target_value:
            code, text = "TARGET_ACHIEVED", "هدف فروش تأمین شده و امتیاز بیشتری ایجاد نمی‌کند."
        if code:
            reasons.append(_reason(code, text, target.target_id))
        else:
            points = (Decimal(weight) * (target.target_value - target.actual_value) / target.target_value).quantize(CENT, rounding=ROUND_HALF_UP)
            matches.append((points, specificity[target.scope_type], target.target_id, target))
    selected = min(matches, key=lambda item: (-item[0], item[1], item[2])) if matches else None
    for points, _, identity, target in matches:
        winner = identity == selected[2]
        reasons.append(_reason("TARGET_APPLIED" if winner else "TARGET_OVERLAP_NOT_STACKED",
                               "بیشترین سهم هدف فروش اعمال شد." if winner else "هدف هم‌پوشان با هدف دیگر جمع نشده است.", identity,
                               target_value=target.target_value, actual_value=target.actual_value, weight=weight, points=points))
    reasons.sort(key=lambda item: item.source_id)
    return Contribution(selected[0] if selected else ZERO,
                        tuple(reasons) or (_reason("NO_QUALIFYING_TARGET", "هدف واجد شرایطی برای افزایش اولویت وجود ندارد."),),
                        selected[2] if selected else None)


def _promotion(product, snapshot, rules):
    if not rules:
        return Contribution(ZERO, (_reason("PROMOTION_EMPHASIS_DISABLED", "تأکید ترویجی در این سیاست تعیین نشده است."),))
    by_id = {row.promotion_id: row for row in snapshot.promotions}
    candidates, reasons = [], []
    for rule in rules:
        promotion = by_id[rule.promotion_id]
        if product.product_id not in promotion.product_ids:
            continue
        code, text = None, None
        if not promotion.is_active:
            code, text = "PROMOTION_INACTIVE", "این برنامهٔ ترویجی غیرفعال است."
        elif not promotion.start_date <= snapshot.evaluation_date <= promotion.end_date:
            code, text = "PROMOTION_OUTSIDE_PERIOD", "برنامهٔ ترویجی خارج از بازهٔ ارزیابی است."
        elif promotion.grade_ids and snapshot.customer_grade_id not in promotion.grade_ids:
            code, text = "PROMOTION_GRADE_INELIGIBLE", "گروه مشتری مشمول این برنامهٔ ترویجی نیست."
        elif promotion.minimum_quantity > 1 or promotion.maximum_quantity is not None and promotion.maximum_quantity < 1:
            code, text = "PROMOTION_QUANTITY_ONE_INELIGIBLE", "شرط تعداد این برنامه با ارزیابی یک عدد سازگار نیست."
        if code:
            reasons.append(_reason(code, text, promotion.promotion_id))
        else:
            candidates.append((rule.points, rule.promotion_id))
    selected = min(candidates, key=lambda item: (-item[0], item[1])) if candidates else None
    for points, identity in candidates:
        winner = identity == selected[1]
        code = "PROMOTION_APPLIED" if winner else "PROMOTION_OVERLAP_NOT_STACKED"
        text = "تأکید برنامهٔ ترویجی اعمال شد؛ مبلغ قیمت تغییر نمی‌کند." if winner else "تأکید برنامه‌های ترویجی با هم جمع نمی‌شود."
        if winner and points == 0:
            code, text = "PROMOTION_EMPHASIS_ZERO", "تأکید ترویجی این سیاست صفر است."
        reasons.append(_reason(code, text, identity, points=points))
    reasons.sort(key=lambda item: item.source_id)
    return Contribution(Decimal(selected[0]).quantize(CENT) if selected else ZERO,
                        tuple(reasons) or (_reason("NO_QUALIFYING_PROMOTION", "برنامهٔ ترویجی واجد شرایطی برای افزایش اولویت وجود ندارد."),),
                        selected[1] if selected else None)


def evaluate_strategy(snapshot: StrategySnapshot) -> StrategyEvaluation:
    """Before = saved shortlist; after = this policy applied to identical facts.

    Missing required facts fail closed. Zero contributions mean no applied boost,
    not measured zero stock/price/target actuals. Even inactive products remain
    in audit output with their original disabled annotations; catalog visibility
    and commercial eligibility remain caller-owned, never overridden here.
    """
    with localcontext(Context(prec=64, rounding=ROUND_HALF_UP)):
        products, rules = _validate(snapshot)
        normalized = replace(snapshot, strategy=rules, products=tuple(sorted(snapshot.products, key=lambda item: item.product_id)),
                             brand_ids=tuple(sorted(snapshot.brand_ids)), category_ids=tuple(sorted(snapshot.category_ids)),
                             grade_ids=tuple(sorted(snapshot.grade_ids)), targets=tuple(sorted(snapshot.targets, key=lambda item: item.target_id)),
                             promotions=tuple(replace(item, product_ids=tuple(sorted(item.product_ids)), grade_ids=tuple(sorted(item.grade_ids)))
                                              for item in sorted(snapshot.promotions, key=lambda item: item.promotion_id)))
        rows = []
        for position, row in enumerate(snapshot.recommendations, 1):
            product = products[row.product_id]
            priority = _priority(product, rules.priority_rules)
            target = _target(product, normalized, rules.target_weight)
            promotion = _promotion(product, normalized, rules.promotion_rules)
            base = Decimal(10 * (len(snapshot.recommendations) - position)).quantize(CENT)
            adjustment = min(CAP, priority.points + target.points + promotion.points).quantize(CENT)
            rows.append(RankedRecommendation(row, product, position, 0, base, priority, target, promotion, adjustment, base + adjustment))
        rows.sort(key=lambda row: (-row.effective_priority, row.original_position, row.source.recommendation_id))
        ranked = tuple(replace(row, after_rank=rank) for rank, row in enumerate(rows, 1))
        return StrategyEvaluation(rules.algorithm_version, configuration_fingerprint(rules.as_config(), rules.algorithm_version),
                                  fingerprint(asdict(normalized)), tuple(row.recommendation_id for row in snapshot.recommendations),
                                  tuple(row.source.recommendation_id for row in ranked), ranked)
