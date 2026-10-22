"""Explicit authorized comparison commands/recovery. No publication or routes."""
import re
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError

from .models import StrategyComparison, StrategyPolicyEvent
from .strategy_access import require_strategy_viewer
from .strategy_persistence import StrategyConflict, StrategyEffect, run_snapshot_command, validate_stored_evidence
from .strategy_serialization import fingerprint
from .strategy_snapshots import (
    SOURCE_VERSION, _capture, evaluate_comparison, positive_id, snapshot_transaction, validate_context,
)


def create_strategy_comparison(*, actor, command_uuid, customer_id, salesperson_id, proposed_version_id,
                               expected_revision, evaluation_date, accepted_source_fingerprint, using="default"):
    validate_context(customer_id, salesperson_id, proposed_version_id, expected_revision, evaluation_date)
    if type(accepted_source_fingerprint) is not str or not re.fullmatch(r"[0-9a-f]{64}", accepted_source_fingerprint):
        raise ValidationError("اثر انگشت دادهٔ پذیرفته‌شده معتبر نیست.", code="INVALID_SOURCE_FINGERPRINT")
    intent = {"customer_id": customer_id, "salesperson_id": salesperson_id, "proposed_version_id": proposed_version_id,
              "evaluation_date": evaluation_date.isoformat(), "accepted_source_fingerprint": accepted_source_fingerprint}

    def handler(policy):
        captured = _capture(actor, customer_id, salesperson_id, proposed_version_id, expected_revision, evaluation_date, using, policy)
        if captured.source_fingerprint != accepted_source_fingerprint:
            raise StrategyConflict("STALE_STRATEGY_INPUTS")
        comparison = StrategyComparison.objects.using(using).create(
            policy=policy, before_version_id=policy.active_version_id, after_version_id=proposed_version_id,
            customer_id=customer_id, salesperson_id=salesperson_id, author_id=actor.pk,
            evaluation_date=evaluation_date, source_version=SOURCE_VERSION,
            inputs={"source_fingerprint": captured.source_fingerprint, "capture": captured.as_dict()},
            outputs=evaluate_comparison(captured),
        )
        return StrategyEffect(comparison.after_version, {
            "comparison_id": comparison.pk, "policy_revision": policy.revision, "source_fingerprint": captured.source_fingerprint,
            "input_digest": comparison.input_digest, "output_digest": comparison.output_digest,
        }, comparison)

    return run_snapshot_command(actor=actor, command_uuid=command_uuid, operation="PREVIEW", expected_revision=expected_revision,
                                intent=intent, handler=handler, using=using)


def _frozen_result(comparison):
    # Historical validation does not require a current assignment or re-read live
    # commercial facts. Detect contradictory stored hashes; never repair them.
    validate_stored_evidence(comparison)
    captured = comparison.inputs.get("capture")
    if not isinstance(captured, dict) or fingerprint(captured) != comparison.inputs.get("source_fingerprint"):
        raise ValidationError("شواهد ذخیره‌شدهٔ مقایسه معتبر نیست.", code="INVALID_COMPARISON_EVIDENCE")
    return {"comparison_id": comparison.pk, "policy_revision": captured["policy_revision"],
            "customer_id": comparison.customer_id, "salesperson_id": comparison.salesperson_id,
            "evaluation_date": comparison.evaluation_date.isoformat(), "source_version": comparison.source_version,
            "before_version_id": comparison.before_version_id, "after_version_id": comparison.after_version_id,
            "input_digest": comparison.input_digest, "output_digest": comparison.output_digest,
            "inputs": comparison.inputs, "outputs": comparison.outputs}


def get_strategy_comparison(*, actor, comparison_id, using="default"):
    positive_id(comparison_id)
    with snapshot_transaction(using, readonly=True):
        require_strategy_viewer(getattr(actor, "pk", None), using)
        return _frozen_result(StrategyComparison.objects.using(using).get(pk=comparison_id))


def recover_strategy_comparison(*, actor, command_uuid, using="default"):
    """Read-only UUID status. Missing means no committed success, never auto retry."""
    with snapshot_transaction(using, readonly=True):
        require_strategy_viewer(getattr(actor, "pk", None), using)
        try:
            command_uuid = UUID(str(command_uuid))
            event = StrategyPolicyEvent.objects.using(using).filter(policy_id=1, command_uuid=command_uuid).first()
        except (ValueError, ValidationError) as error:
            raise ValidationError("شناسهٔ فرمان معتبر نیست.", code="INVALID_COMMAND_UUID") from error
        if event is None:
            return None
        if event.actor_id != actor.pk or event.operation != StrategyPolicyEvent.Operation.PREVIEW:
            raise PermissionDenied("دسترسی به نتیجهٔ این فرمان مجاز نیست.")
        event.full_clean()
        comparison = _frozen_result(event.comparison)
        if event.result.get("comparison_id") != comparison["comparison_id"] or event.result.get("output_digest") != comparison["output_digest"]:
            raise ValidationError("رسید مقایسه با شواهد سازگار نیست.", code="INVALID_COMPARISON_EVIDENCE")
        return {"result": event.result, "comparison": comparison}
