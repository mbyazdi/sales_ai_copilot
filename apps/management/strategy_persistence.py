"""Internal transaction primitives, NOT publication or evaluation services/APIs.

Only trusted future handlers may use this boundary; they must perform their own
operation-specific preview/publication validation. No existing route calls it.
"""
from dataclasses import dataclass
import re
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models import F

from .models import StrategyComparison, StrategyPolicy, StrategyPolicyEvent, StrategyPolicyVersion
from .strategy_access import require_strategy_manager
from .strategy_serialization import canonical_value, fingerprint


class StrategyConflict(ValidationError):
    pass


@dataclass(frozen=True)
class StrategyEffect:
    version: object
    result: dict
    comparison: object = None


@dataclass(frozen=True)
class StrategyCommandResult:
    event: StrategyPolicyEvent
    replayed: bool


def validate_stored_evidence(record):
    """Stored digests are mandatory; model creation may compute blank digests.

    Do not let full_clean's creation convenience reconstruct missing historical
    evidence in memory and accidentally treat it as an accepted baseline.
    """
    for field in ("config_hash", "input_digest", "output_digest", "intent_fingerprint"):
        if hasattr(record, field) and not re.fullmatch(r"[0-9a-f]{64}", getattr(record, field) or ""):
            raise ValidationError("Stored strategy digest is missing or malformed.", code="INVALID_STRATEGY_EVIDENCE")
    record.full_clean()


def run_strategy_command(*, actor, command_uuid, operation, expected_revision, intent, handler, using="default"):
    """Serialize one successful foundation command and its canonical replay.

    Handler creates immutable foundation records and returns StrategyEffect.
    Any failure, including result validation, rolls back all handler effects.
    PREVIEW records evidence without advancing the configuration revision.
    """
    if operation not in StrategyPolicyEvent.Operation.values:
        raise ValidationError("Unsupported strategy operation.")
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValidationError("Expected revision must be a nonnegative integer.")
    try:
        command_uuid = UUID(str(command_uuid))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("A command UUID is required.") from None
    if not isinstance(intent, dict) or not intent:
        raise ValidationError("A canonical intent object is required.")
    intent = canonical_value(intent)
    with transaction.atomic(using=using):
        manager = require_strategy_manager(actor.pk, using)
        # Trusted constant-only initialization, never a GET side effect. Bypass
        # application uniqueness prechecks here so a concurrent first use cannot
        # fail between validation and INSERT; the database arbitrates the PK.
        heads = StrategyPolicy.objects.using(using).all()
        if not heads.filter(pk=1).exists():
            models.QuerySet.bulk_create(heads, [StrategyPolicy(pk=1)], ignore_conflicts=True)
        policy = StrategyPolicy.objects.using(using).select_for_update().get(pk=1)
        intent_hash = fingerprint({"policy": policy.pk, "actor": manager.pk, "operation": operation,
                                   "expected_revision": expected_revision, "intent": intent})
        prior = StrategyPolicyEvent.objects.using(using).filter(policy=policy, command_uuid=command_uuid).first()
        if prior:
            if prior.actor_id != manager.pk or prior.intent_fingerprint != intent_hash:
                raise StrategyConflict("COMMAND_INTENT_CONFLICT")
            validate_stored_evidence(prior)
            return StrategyCommandResult(prior, True)
        if policy.revision != expected_revision:
            raise StrategyConflict("STALE_POLICY_REVISION")
        effect = handler(policy)
        if not isinstance(effect, StrategyEffect):
            raise ValidationError("Handler must return canonical strategy evidence.")
        version = effect.version
        if not isinstance(version, StrategyPolicyVersion) or version._state.adding or version._state.db != using or version.policy_id != policy.pk:
            raise ValidationError("Effect must reference a persisted version of this policy/database.")
        version = StrategyPolicyVersion.objects.using(using).get(pk=version.pk, policy=policy)
        comparison = effect.comparison
        if comparison is not None:
            if not isinstance(comparison, StrategyComparison) or comparison._state.adding or comparison._state.db != using:
                raise ValidationError("Effect must reference a persisted comparison in this database.")
            comparison = StrategyComparison.objects.using(using).get(pk=comparison.pk, policy=policy)
        if operation == StrategyPolicyEvent.Operation.PREVIEW:
            if comparison is None:
                raise ValidationError("Preview requires frozen comparison evidence.")
        else:
            pointers = ({"draft_version_id": version.pk} if operation == StrategyPolicyEvent.Operation.SAVE_DRAFT
                        else {"active_version_id": version.pk, "draft_version_id": None})
            # No joined id-subquery: the revision predicate targets the UPDATE row.
            selected = StrategyPolicy.objects.using(using).filter(pk=policy.pk, revision=expected_revision)
            changed = models.QuerySet.update(selected, revision=F("revision") + 1, **pointers)
            if changed != 1:
                raise StrategyConflict("STALE_POLICY_REVISION")
            policy.refresh_from_db()
        event = StrategyPolicyEvent.objects.using(using).create(
            policy=policy, actor=manager, command_uuid=command_uuid, operation=operation,
            expected_revision=expected_revision, applied_revision=policy.revision, intent=intent,
            intent_fingerprint=intent_hash, version=version, comparison=comparison, result=effect.result,
        )
        return StrategyCommandResult(event, False)


def run_snapshot_command(*, actor, command_uuid, operation, expected_revision, intent, handler, using="default"):
    """One consistent command image; recover only an already committed receipt.

    Never retry a handler after serialization/UUID collision. A fresh read can
    recover the winning identical command; absent evidence remains a conflict.
    """
    from .strategy_snapshots import snapshot_transaction  # Avoid adapter import cycle.

    try:
        with snapshot_transaction(using, readonly=False):
            manager = require_strategy_manager(getattr(actor, "pk", None), using)
            return run_strategy_command(actor=manager, command_uuid=command_uuid, operation=operation,
                                        expected_revision=expected_revision, intent=intent, handler=handler, using=using)
    except (IntegrityError, StrategyConflict) as error:
        collision = getattr(getattr(error.__cause__, "diag", None), "constraint_name", None) == "strategy_unique_command"
        concurrent = isinstance(error, StrategyConflict) and error.messages == ["CONCURRENT_POLICY_OR_SOURCE_CHANGE"]
        if not collision and not concurrent:
            raise
        with snapshot_transaction(using, readonly=True):
            manager = require_strategy_manager(getattr(actor, "pk", None), using)
            prior = StrategyPolicyEvent.objects.using(using).filter(policy_id=1, command_uuid=command_uuid).first()
            if prior is None:
                raise error
            expected_hash = fingerprint({"policy": 1, "actor": manager.pk, "operation": operation,
                                         "expected_revision": expected_revision, "intent": intent})
            if prior.actor_id != manager.pk or prior.intent_fingerprint != expected_hash:
                raise StrategyConflict("COMMAND_INTENT_CONFLICT") from error
            validate_stored_evidence(prior)
            return StrategyCommandResult(prior, True)
