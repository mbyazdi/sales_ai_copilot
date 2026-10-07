"""Saved, signed priority read context. No ranking engine or session writes."""
import hashlib
import json
from dataclasses import dataclass

from django.core import signing

from .models import CustomerRecommendation


CONTEXT_SALT = "recommendations.guided-catalog.v1"
CONTEXT_MAX_AGE = 8 * 60 * 60


class CatalogContextUnavailable(Exception):
    """Do not silently replace a stale/invalid saved selling context."""


@dataclass(frozen=True)
class SavedPriority:
    token: str
    recommendations: tuple


def _fingerprint(row):
    saved = {
        "id": row.pk, "product": row.product_id, "rank": row.rank,
        "type": row.recommendation_type, "reason": row.reason,
        "explanation": row.explanation_snapshot, "breakdown": row.score_breakdown,
        "score": str(row.score), "confidence": str(row.confidence_score),
        "evidence": row.evidence_quality, "updated_at": row.updated_at.isoformat(),
    }
    return hashlib.sha256(json.dumps(saved, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def saved_priority(access, token=""):
    binding = {
        "version": 1, "actor": access.user.pk, "salesperson": access.visit.salesperson_id,
        "customer": access.customer.pk, "visit": access.visit.pk,
    }
    rows = CustomerRecommendation.objects.filter(customer=access.customer, is_active=True)
    if not token:
        ordered = tuple(rows.order_by("rank", "pk"))
        payload = {**binding, "rows": [[row.pk, _fingerprint(row)] for row in ordered]}
        return SavedPriority(signing.dumps(payload, salt=CONTEXT_SALT, compress=True), ordered)
    try:
        payload = signing.loads(token, salt=CONTEXT_SALT, max_age=CONTEXT_MAX_AGE)
        if not isinstance(payload, dict) or any(payload.get(key) != value for key, value in binding.items()):
            raise CatalogContextUnavailable
        identities = payload["rows"]
        if not isinstance(identities, list) or any(
            not isinstance(item, list) or len(item) != 2 or type(item[0]) is not int or not isinstance(item[1], str)
            for item in identities
        ):
            raise CatalogContextUnavailable
        ids = [item[0] for item in identities]
        if len(ids) != len(set(ids)):
            raise CatalogContextUnavailable
        by_id = {row.pk: row for row in rows.filter(pk__in=ids)}
        if any(pk not in by_id or _fingerprint(by_id[pk]) != fingerprint for pk, fingerprint in identities):
            raise CatalogContextUnavailable
        return SavedPriority(token, tuple(by_id[pk] for pk in ids))
    except (signing.BadSignature, KeyError, TypeError, ValueError) as error:
        raise CatalogContextUnavailable from error
