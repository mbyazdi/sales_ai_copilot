"""Internal Draft -> Preview -> Publish/rollback services. No live integration.

Rollback is deliberately prepared as a new draft, compared through M-C3, then
explicitly activated. An old version/comparison can never be relabelled as new.
"""
import re
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError

from .models import StrategyComparison, StrategyPolicyEvent, StrategyPolicyVersion
from .strategy_access import require_strategy_manager
from .strategy_comparisons import _frozen_result
from .strategy_persistence import StrategyConflict, StrategyEffect, run_snapshot_command, validate_stored_evidence
from .strategy_serialization import ALGORITHM_VERSION, configuration_fingerprint, neutral_config, normalize_config
from .strategy_snapshots import SOURCE_VERSION, _capture, _version, evaluate_comparison, positive_id, snapshot_transaction


def _historical_config(target_version_id, policy, using):
    if target_version_id is None:
        return None, neutral_config()
    target, _ = _version(target_version_id, policy, using)
    publication = StrategyPolicyEvent.objects.using(using).filter(
        policy=policy, version=target, operation__in=("PUBLISH", "ROLLBACK")).first()
    if publication is None:
        raise StrategyConflict("ROLLBACK_TARGET_NOT_PUBLISHED")
    validate_stored_evidence(publication)
    return target, target.config


def create_strategy_draft(*, actor, command_uuid, expected_revision, config: dict, using="default"):
    """Validate exact V1 JSON types/references and create one immutable version."""
    config = normalize_config(config)
    intent = {"kind": "CONFIGURATION", "config": config, "algorithm_version": ALGORITHM_VERSION}
    return _save_draft(actor, command_uuid, expected_revision, intent, using)


def prepare_strategy_rollback(*, actor, command_uuid, expected_revision, target_version_id: int | None, using="default"):
    """Copy a published version (None = explicit neutral) into a NEW draft.

    This does not activate anything. Preview this exact new draft before calling
    rollback_strategy with its accepted immutable comparison.
    """
    if target_version_id is not None:
        positive_id(target_version_id)
    intent = {"kind": "ROLLBACK_PREPARATION", "target_version_id": target_version_id}
    return _save_draft(actor, command_uuid, expected_revision, intent, using)


def _save_draft(actor, command_uuid, expected_revision, intent, using):
    def handler(policy):
        policy.full_clean()
        if intent["kind"] == "ROLLBACK_PREPARATION":
            parent, config = _historical_config(intent["target_version_id"], policy, using)
        else:
            parent, _ = _version(policy.active_version_id, policy, using)
            config = intent["config"]
        version = StrategyPolicyVersion.objects.using(using).create(
            policy=policy, author_id=actor.pk, parent=parent, config=config)
        return StrategyEffect(version, {"version_id": version.pk, "config_hash": version.config_hash,
                                       "policy_revision": policy.revision + 1, "kind": intent["kind"]})
    return run_snapshot_command(actor=actor, command_uuid=command_uuid, operation="SAVE_DRAFT",
                                expected_revision=expected_revision, intent=intent, handler=handler, using=using)


def publish_strategy(*, actor, command_uuid, expected_revision, draft_version_id, comparison_id,
                     accepted_comparison_digest, using="default"):
    return _activate(actor, command_uuid, expected_revision, draft_version_id, comparison_id,
                     accepted_comparison_digest, "PUBLISH", using)


def rollback_strategy(*, actor, command_uuid, expected_revision, draft_version_id, comparison_id,
                      accepted_comparison_digest, using="default"):
    """Publish an explicitly prepared, previewed NEW rollback version."""
    return _activate(actor, command_uuid, expected_revision, draft_version_id, comparison_id,
                     accepted_comparison_digest, "ROLLBACK", using)


def _activate(actor, command_uuid, expected_revision, draft_version_id, comparison_id, digest, operation, using):
    positive_id(draft_version_id)
    positive_id(comparison_id)
    if type(digest) is not str or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValidationError("اثر انگشت مقایسه معتبر نیست.", code="INVALID_COMPARISON_DIGEST")
    intent = {"draft_version_id": draft_version_id, "comparison_id": comparison_id, "accepted_comparison_digest": digest}

    def handler(policy):
        policy.full_clean()
        if policy.draft_version_id != draft_version_id:
            raise StrategyConflict("STRATEGY_DRAFT_CHANGED")
        version, _ = _version(draft_version_id, policy, using)
        preparation = StrategyPolicyEvent.objects.using(using).filter(
            policy=policy, version=version, operation="SAVE_DRAFT", applied_revision=expected_revision).first()
        if preparation is None:
            raise StrategyConflict("DRAFT_COMMAND_EVIDENCE_MISSING")
        validate_stored_evidence(preparation)
        is_rollback = preparation.intent.get("kind") == "ROLLBACK_PREPARATION"
        if (operation == "ROLLBACK") != is_rollback:
            raise StrategyConflict("DRAFT_OPERATION_MISMATCH")
        if is_rollback:
            if "target_version_id" not in preparation.intent:
                raise StrategyConflict("INVALID_ROLLBACK_EVIDENCE")
            target, config = _historical_config(preparation.intent["target_version_id"], policy, using)
            if version.parent_id != (target.pk if target else None) or version.config_hash != configuration_fingerprint(config):
                raise StrategyConflict("INVALID_ROLLBACK_EVIDENCE")
        comparison = StrategyComparison.objects.using(using).get(pk=comparison_id, policy=policy)
        frozen = _frozen_result(comparison)
        require_strategy_manager(comparison.author_id, using)
        if (comparison.output_digest != digest or comparison.after_version_id != draft_version_id
                or comparison.before_version_id != policy.active_version_id or frozen["policy_revision"] != expected_revision
                or comparison.source_version != SOURCE_VERSION):
            raise StrategyConflict("STALE_OR_MISMATCHED_COMPARISON")
        preview = StrategyPolicyEvent.objects.using(using).filter(
            policy=policy, comparison=comparison, operation="PREVIEW", actor_id=comparison.author_id,
            expected_revision=expected_revision, version=version).first()
        if preview is None:
            raise StrategyConflict("PREVIEW_COMMAND_EVIDENCE_MISSING")
        validate_stored_evidence(preview)
        captured = _capture(actor, comparison.customer_id, comparison.salesperson_id, draft_version_id,
                            expected_revision, comparison.evaluation_date, using, policy)
        expected_preview = {"comparison_id": comparison.pk, "policy_revision": expected_revision,
                            "source_fingerprint": captured.source_fingerprint,
                            "input_digest": comparison.input_digest, "output_digest": comparison.output_digest}
        if (captured.as_dict() != comparison.inputs["capture"] or preview.result != expected_preview
                or evaluate_comparison(captured) != comparison.outputs):
            raise StrategyConflict("STALE_STRATEGY_INPUTS")
        return StrategyEffect(version, {
            "active_version_id": version.pk, "previous_active_version_id": policy.active_version_id,
            "draft_version_id": None, "policy_revision": expected_revision + 1, "config_hash": version.config_hash,
            "comparison_id": comparison.pk, "accepted_comparison_digest": digest,
            "source_fingerprint": captured.source_fingerprint, "operation": operation,
            "application_scope": "FRESH_SELLING_CONTEXTS_ONLY",
        }, comparison)

    return run_snapshot_command(actor=actor, command_uuid=command_uuid, operation=operation,
                                expected_revision=expected_revision, intent=intent, handler=handler, using=using)


def recover_strategy_command(*, actor, command_uuid, using="default"):
    """Read-only actor-bound recovery, with no handler replay or source refresh."""
    try:
        command_uuid = UUID(str(command_uuid))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("شناسهٔ فرمان معتبر نیست.", code="INVALID_COMMAND_UUID") from None
    with snapshot_transaction(using, readonly=True):
        manager = require_strategy_manager(getattr(actor, "pk", None), using)
        event = StrategyPolicyEvent.objects.using(using).filter(policy_id=1, command_uuid=command_uuid).first()
        if event is None:
            return None
        if event.actor_id != manager.pk:
            raise PermissionDenied("دسترسی به نتیجهٔ این فرمان مجاز نیست.")
        validate_stored_evidence(event)
        return {"operation": event.operation, "result": event.result}
