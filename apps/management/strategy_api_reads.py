"""Bounded read projections for management only. Never initialize policy state."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef, Q

from apps.customers.models import Customer
from apps.products.models import Brand, Category, Product
from apps.promotions.models import Promotion
from apps.visits.models import CustomerAssignment, Salesperson
from .models import StrategyComparison, StrategyPolicy, StrategyPolicyEvent, StrategyPolicyVersion
from .strategy_access import require_strategy_viewer
from .strategy_serialization import ALGORITHM_VERSION, configuration_fingerprint, neutral_config
from .strategy_snapshots import _capture, _version, snapshot_transaction


LIMITATIONS_FA = "بازچینی فقط روی پیشنهادهای ذخیره‌شده شبیه‌سازی می‌شود؛ قیمت و تخفیف تغییر نمی‌کند و اثر واقعی بر فروش اندازه‌گیری نشده است."


def frozen_comparison_labels(comparison):
    """Allowlisted historical labels, ONLY after get_strategy_comparison verifies evidence.

    No ORM calls or live fallback. Global policy references outside the shortlist
    are deliberately omitted. Missing historical labels stay null.
    """
    sources = comparison["inputs"]["capture"].get("sources")
    sources = sources if isinstance(sources, dict) else {}
    def text(value):
        return value if isinstance(value, str) and value.strip() else None
    customer = sources.get("customer")
    customer = customer if isinstance(customer, dict) else {}
    rep = sources.get("salesperson")
    rep = rep if isinstance(rep, dict) else {}
    customer = customer if customer.get("id") == comparison["customer_id"] else {}
    rep = rep if rep.get("id") == comparison["salesperson_id"] else {}
    allowed = {row["source"]["product_id"] for row in comparison["outputs"]["after"]["rows"]}
    return {
        "customer": {"id": comparison["customer_id"], "code": text(customer.get("customer_code")), "name": text(customer.get("name"))},
        "salesperson": {"id": comparison["salesperson_id"], "code": text(rep.get("employee_code")),
                        "name": text(" ".join(filter(None, (text(rep.get("first_name")), text(rep.get("last_name"))))))},
        "products": [{"id": row["id"], "code": text(row.get("product_code")), "name": text(row.get("name"))}
                     for row in (sources.get("products") or []) if isinstance(row, dict) and row.get("id") in allowed],
    }


def overview(actor):
    with snapshot_transaction("default", readonly=True):
        require_strategy_viewer(actor.pk)
        head = StrategyPolicy.objects.filter(pk=1).first()
        active, _ = _version(head.active_version_id, head, "default") if head else (None, None)
        draft, _ = _version(head.draft_version_id, head, "default") if head else (None, None)
        return {"schema_version": 1, "policy_id": 1, "revision": head.revision if head else 0,
                "active_version_id": active.pk if active else None, "draft_version_id": draft.pk if draft else None,
                "active_config": active.config if active else neutral_config(), "algorithm_version": ALGORITHM_VERSION,
                "version_count": StrategyPolicyVersion.objects.filter(policy_id=1).count(),
                "comparison_count": StrategyComparison.objects.filter(policy_id=1).count(),
                "selling_context_integration": True, "impact_available": False, "limitations_fa": LIMITATIONS_FA}


def versions(actor, *, after_id, limit):
    with snapshot_transaction("default", readonly=True):
        require_strategy_viewer(actor.pk)
        published = StrategyPolicyEvent.objects.filter(policy_id=1, version_id=OuterRef("pk"), operation__in=["PUBLISH", "ROLLBACK"])
        rows = list(StrategyPolicyVersion.objects.filter(policy_id=1, pk__gt=after_id).order_by("pk")
                    .annotate(published=Exists(published)).values(
                        "id", "parent_id", "author_id", "algorithm_version", "config_hash", "config", "created_at", "published")[:limit + 1])
        for row in rows:
            if configuration_fingerprint(row["config"], row["algorithm_version"]) != row["config_hash"]:
                raise ValidationError("شواهد نسخه معتبر نیست.", code="INVALID_STRATEGY_EVIDENCE")
        return {"results": rows[:limit], "next_after_id": rows[limit - 1]["id"] if len(rows) > limit else None}


def options(actor, **query):
    with snapshot_transaction("default", readonly=True):
        require_strategy_viewer(actor.pk)
        result = {"schema_version": 1, "algorithm_version": ALGORITHM_VERSION,
                  "priority_scopes": ["PRODUCT", "BRAND", "CATEGORY"], "priority_bounds": [0, 20],
                  "target_weight_bounds": [0, 5], "promotion_points_bounds": [0, 5], "adjustment_cap": 30,
                  "rollback_actions": ["PREPARE", "ACTIVATE"], "limitations_fa": LIMITATIONS_FA}
        kind = query.get("kind")
        if kind:
            mapping = {"products": Product, "brands": Brand, "categories": Category,
                       "promotions": Promotion, "salespersons": Salesperson, "customers": Customer}
            model = mapping[kind]
            selected = model.objects.filter(is_active=True)
            if kind == "customers":
                salesperson_id, day = query["salesperson_id"], query["evaluation_date"]
                if not Salesperson.objects.filter(pk=salesperson_id, is_active=True).exists():
                    raise PermissionDenied
                assignments = CustomerAssignment.objects.filter(salesperson_id=salesperson_id, customer_id=OuterRef("pk"),
                                                               is_active=True, start_date__lte=day).filter(Q(end_date__isnull=True) | Q(end_date__gte=day))
                selected = selected.filter(Exists(assignments))
            fields = (["id", "employee_code", "first_name", "last_name"] if kind == "salespersons" else
                      ["id", "customer_code", "name"] if kind == "customers" else
                      ["id", "product_code", "name", "brand_id", "category_id"] if kind == "products" else ["id", "code", "name"])
            limit = query["limit"]
            rows = list(selected.filter(pk__gt=query["after_id"]).order_by("pk").values(*fields)[:limit + 1])
            result.update(kind=kind, results=rows[:limit], next_after_id=rows[limit - 1]["id"] if len(rows) > limit else None)
        if "customer_id" in query:
            captured = _capture(actor, query["customer_id"], query["salesperson_id"], query["proposed_version_id"],
                                query["expected_revision"], query["evaluation_date"], "default")
            result["preview_context"] = {key: query[key] for key in (
                "customer_id", "salesperson_id", "proposed_version_id", "expected_revision")}
            result["preview_context"].update(evaluation_date=query["evaluation_date"].isoformat(),
                                             accepted_source_fingerprint=captured.source_fingerprint)
        return result
