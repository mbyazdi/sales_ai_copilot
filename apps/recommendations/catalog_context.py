"""Saved, signed priority read context. No ranking engine or session writes."""
import hashlib
import json
from dataclasses import dataclass

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import DatabaseError

from .models import CustomerRecommendation


CONTEXT_SALT = "recommendations.guided-catalog.v1"
CONTEXT_MAX_AGE = 8 * 60 * 60


class CatalogContextUnavailable(Exception):
    """Do not silently replace a stale/invalid saved selling context."""


@dataclass(frozen=True)
class SavedPriority:
    token: str
    recommendations: tuple
    strategy: dict | None = None

    def strategy_for(self, recommendation_id):
        if self.strategy is None:
            return None
        return {"policy_version_id": self.strategy["policy_version_id"], "algorithm_version": self.strategy["algorithm_version"],
                "policy_revision": self.strategy["policy_revision"], "evaluation_date": self.strategy["evaluation_date"],
                "config_hash": self.strategy["config_hash"], "source_fingerprint": self.strategy["source_fingerprint"],
                "recommendation_fingerprint": self.strategy["recommendation_fingerprint"],
                "evidence_digest": self.strategy["evidence_digest"],
                **self.strategy["rows"][str(recommendation_id)]}


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
    if not isinstance(token, str) or len(token) > 100000:
        raise CatalogContextUnavailable
    binding = {
        "version": 1, "actor": access.user.pk, "salesperson": access.visit.salesperson_id,
        "customer": access.customer.pk, "visit": access.visit.pk,
    }
    rows = CustomerRecommendation.objects.filter(customer=access.customer, is_active=True)
    if not token:
        from apps.management.selling_strategy import resolve_fresh_strategy
        try:
            ordered, strategy = resolve_fresh_strategy(access)
        except (ValidationError, DatabaseError) as error:
            raise CatalogContextUnavailable from error  # No unlocked/neutral fallback on capability failure.
        payload = {**binding, "rows": [[row.pk, _fingerprint(row)] for row in ordered]}
        if strategy is not None:
            # Optional V1 extension: old signatures/bindings remain valid, and
            # current policy is never consulted when this token is reused.
            from apps.management.strategy_serialization import fingerprint
            strategy["recommendation_fingerprint"] = fingerprint(payload["rows"])
            strategy.pop("evidence_digest")
            strategy["evidence_digest"] = fingerprint(strategy)
            payload["strategy"] = strategy
        signed = signing.dumps(payload, salt=CONTEXT_SALT, compress=True)
        if len(signed) > 100000:
            raise CatalogContextUnavailable
        return SavedPriority(signed, ordered, strategy)
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
        strategy = payload.get("strategy")
        if "strategy" in payload:
            from apps.management.strategy_serialization import ALGORITHM_VERSION, fingerprint
            if (not isinstance(strategy, dict) or type(strategy.get("schema_version")) is not int or strategy["schema_version"] != 1
                    or strategy.get("algorithm_version") != ALGORITHM_VERSION
                    or type(strategy.get("policy_version_id")) is not int or strategy["policy_version_id"] < 1
                    or strategy.get("effective_order") != ids
                    or strategy.get("recommendation_fingerprint") != fingerprint(identities)
                    or not isinstance(strategy.get("rows"), dict)
                    or set(strategy["rows"]) != {str(pk) for pk in ids}
                    or any(not isinstance(value, dict) for value in strategy["rows"].values())
                    or strategy.get("evidence_digest") != fingerprint({k: v for k, v in strategy.items() if k != "evidence_digest"})):
                raise CatalogContextUnavailable
        return SavedPriority(token, tuple(by_id[pk] for pk in ids), strategy)
    except (signing.BadSignature, KeyError, TypeError, ValueError, ValidationError) as error:
        raise CatalogContextUnavailable from error
