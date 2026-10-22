"""Fresh-only salesperson strategy resolver. Reuse never reads current policy."""
from django.core.exceptions import ValidationError
from django.db import connections
from django.utils import timezone
from zoneinfo import ZoneInfo

from apps.products.catalog_access import catalog_access
from apps.recommendations.models import CustomerRecommendation
from .models import StrategyPolicy, StrategyPolicyEvent
from .strategy_persistence import validate_stored_evidence
from .strategy_evaluator import evaluate_strategy
from .strategy_serialization import ALGORITHM_VERSION, fingerprint
from .strategy_snapshots import _capture_facts, _context_facts, _version, snapshot_transaction


def _saved_rows(access):
    return tuple(CustomerRecommendation.objects.filter(customer=access.customer, is_active=True)
                 .select_related("product", "product__category").order_by("rank", "pk"))


def resolve_fresh_strategy(access):
    """Return rows + detached overlay evidence, with no policy/engine writes.

    Missing active policy is legacy-neutral. Active policy capture requires a
    top-level read-only RR image; never inherit a weaker PostgreSQL transaction.
    Authorization is re-read inside that image, never manager impersonation.
    """
    db = connections["default"]
    if db.in_atomic_block:
        # Existing TestCase/legacy callers may own transactions. Neutral reads
        # need no fact capture; non-neutral/active capture must fail closed.
        head = StrategyPolicy.objects.filter(pk=1).first()
        if head is not None and head.active_version_id is not None:
            raise ValidationError("زمینهٔ تازه به تراکنش مستقل نیاز دارد.", code="TOP_LEVEL_TRANSACTION_REQUIRED")
        return _saved_rows(access), None
    with snapshot_transaction("default", readonly=True):
        access = catalog_access(access.user, access.customer.customer_code, access.visit.pk)
        head = StrategyPolicy.objects.filter(pk=1).first()
        if head is None or head.active_version_id is None:
            return _saved_rows(access), None
        version, rules = _version(head.active_version_id, head, "default")
        publication = StrategyPolicyEvent.objects.filter(policy=head, version=version,
                        operation__in=("PUBLISH", "ROLLBACK")).order_by("-applied_revision").first()
        if publication is None:
            raise ValidationError("شواهد انتشار سیاست موجود نیست.", code="INVALID_STRATEGY_EVIDENCE")
        validate_stored_evidence(publication)
        if (publication.applied_revision > head.revision or publication.result.get("active_version_id") != version.pk
                or publication.result.get("config_hash") != version.config_hash
                or publication.result.get("policy_revision") != publication.applied_revision):
            raise ValidationError("شواهد انتشار سیاست معتبر نیست.", code="INVALID_STRATEGY_EVIDENCE")
        day = timezone.localdate(timezone=ZoneInfo("Asia/Tehran"))
        context = _context_facts(access.customer.pk, access.visit.salesperson_id, day, "default")
        captured = _capture_facts(access.customer.pk, access.visit.salesperson_id, day, "default",
                                  head, version, rules, version, rules, context)
        evaluation = evaluate_strategy(captured.snapshot).as_dict()
        by_id = {row.pk: row for row in _saved_rows(access)}
        source = captured.as_dict()
        # Only ranking evidence is carried; current commercial authorization and
        # quotes remain independent. No capture database credentials/identity leak.
        rows = {str(row["source"]["recommendation_id"]): {
            "base_score": row["source"]["base_score"], "saved_rank": row["source"]["saved_rank"],
            "original_position": row["original_position"], "effective_position": row["after_rank"],
            "base_priority": row["base_priority"], "effective_priority": row["effective_priority"],
            "overlay_adjustment": row["overlay_adjustment"], "priority": row["priority"],
            "target": row["target"], "promotion": row["promotion"],
        } for row in evaluation["rows"]}
        evidence = {"schema_version": 1, "policy_version_id": version.pk, "policy_revision": head.revision,
                    "algorithm_version": ALGORITHM_VERSION, "config_hash": version.config_hash,
                    "evaluation_date": day.isoformat(), "timezone": "Asia/Tehran",
                    "source_fingerprint": captured.source_fingerprint, "source_fingerprints": source["source_fingerprints"],
                    "effective_order": evaluation["after_ids"], "rows": rows,
                    "meaning_fa": "اولویت بازچینی است؛ احتمال خرید یا میزان اطمینان نیست."}
        evidence["evidence_digest"] = fingerprint(evidence)
        return tuple(by_id[pk] for pk in evaluation["after_ids"]), evidence
