"""Explicit Visit completion, independent of request submission and legacy POST."""
import hashlib
import json

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from apps.products.catalog_access import visit_customer_access
from apps.sales_requests.models import (
    SalesRequest, SalesRequestAcknowledgement, SalesRequestMutationReceipt,
)
from .models import Visit


OPERATION = SalesRequestMutationReceipt.Operation.COMPLETE_VISIT


class CompletionConflict(Exception):
    def __init__(self, code, detail):
        self.code, self.detail = code, detail
        super().__init__(code)


def _intent(actor_id, visit_id, customer_code):
    value = {"version": 1, "operation": OPERATION, "actor_id": actor_id,
             "visit_id": visit_id, "customer_code": customer_code}
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def _acknowledgement(acknowledgement):
    if acknowledgement is None:
        return None
    return {"id": acknowledgement.pk, "sales_request_id": acknowledgement.sales_request_id,
            "actor_id": acknowledgement.actor_id,
            "acknowledged_at": acknowledgement.acknowledged_at.isoformat()}


def _request(request):
    if request is None:
        return None
    return {"id": request.pk, "status": request.status, "revision": request.revision,
            "number": request.number}


def complete_visit(user, visit_id, command):
    """Caller supplies validated customer_code/UUID; success is atomic and durable.

    Visit -> Request is the same lock order as basket, feedback and submission.
    The target-row status predicate also protects against the unmodified legacy
    endpoint, which does not participate in this locking protocol.
    """
    with transaction.atomic():
        access = visit_customer_access(user, command["customer_code"], visit_id, lock_visit=True)
        fingerprint = _intent(access.user.pk, access.visit.pk, command["customer_code"])
        receipt = SalesRequestMutationReceipt.objects.filter(
            visit=access.visit, command_uuid=command["command_uuid"],
        ).first()
        if receipt:
            if receipt.actor_id != access.user.pk:
                raise PermissionDenied
            if receipt.operation != OPERATION or receipt.intent_fingerprint != fingerprint:
                raise CompletionConflict("COMMAND_CONFLICT", "شناسه فرمان قبلاً برای عملیات دیگری استفاده شده است.")
            # Reauthorize, then return frozen evidence; do not reconstruct it.
            return receipt.result["body"], receipt.result["http_status"], True
        if access.visit.status != Visit.VisitStatus.IN_PROGRESS:
            raise CompletionConflict("VISIT_NOT_ACTIVE", "فقط ویزیت در حال انجام قابل پایان است؛ وضعیت فعلی را بررسی کنید.")
        request = SalesRequest.objects.select_for_update().filter(visit=access.visit).first()
        if request and request.submission_key == command["command_uuid"]:
            raise CompletionConflict("COMMAND_CONFLICT", "شناسه فرمان قبلاً برای ثبت درخواست استفاده شده است.")
        finished_at = timezone.now()
        changed = Visit.objects.filter(
            pk=access.visit.pk, customer=access.customer,
            salesperson=access.user.salesperson_profile, status=Visit.VisitStatus.IN_PROGRESS,
        ).update(status=Visit.VisitStatus.COMPLETED, updated_at=finished_at)
        if changed != 1:
            raise CompletionConflict("VISIT_NOT_ACTIVE", "وضعیت ویزیت تغییر کرده است؛ وضعیت فعلی را بررسی کنید.")
        acknowledgement = None
        if request and request.status == SalesRequest.Status.SUBMITTED:
            acknowledgement = SalesRequestAcknowledgement.objects.filter(sales_request=request).first()
            if acknowledgement is None:
                acknowledgement = SalesRequestAcknowledgement.objects.create(
                    sales_request=request, actor=access.user.salesperson_profile,
                    metadata={"version": 1, "operation": OPERATION, "visit_id": access.visit.pk,
                              "command_uuid": str(command["command_uuid"]),
                              "completed_at": finished_at.isoformat()},
                )
            elif acknowledgement.actor_id != access.user.salesperson_profile.pk:
                raise PermissionDenied
        body = {
            "version": 1, "success": True,
            "customer": {"id": access.customer.pk, "code": access.customer.customer_code},
            "visit": {"id": access.visit.pk, "status": Visit.VisitStatus.COMPLETED,
                      "customer_code": access.customer.customer_code,
                      "salesperson_code": access.user.salesperson_profile.employee_code},
            "command_uuid": str(command["command_uuid"]), "completed_at": finished_at.isoformat(),
            "request": _request(request), "acknowledgement": _acknowledgement(acknowledgement),
        }
        SalesRequestMutationReceipt.objects.create(
            visit=access.visit, actor=access.user, command_uuid=command["command_uuid"],
            operation=OPERATION, intent_fingerprint=fingerprint, sales_request=request,
            applied_revision=request.revision if request else None,
            result={"http_status": 200, "body": body},
        )
        return body, 200, False


def completion_state(user, customer_code, visit_id):
    """One coherent SELECT projection after authorization; never creates evidence.

    A legacy-completed Visit legitimately has no new completion receipt. Do not
    backfill one, create an acknowledgement or infer a timestamp from updated_at.
    """
    access = visit_customer_access(user, customer_code, visit_id)
    receipts = SalesRequestMutationReceipt.objects.filter(visit_id=OuterRef("pk"), operation=OPERATION)
    state = Visit.objects.filter(pk=access.visit.pk).annotate(
        recorded=Subquery(receipts.order_by("pk").values("result")[:1]),
    ).values("id", "status", "sales_request__id", "sales_request__status", "sales_request__revision",
             "sales_request__number", "recorded").get()
    return {
        "version": 1, "customer": {"id": access.customer.pk, "code": access.customer.customer_code},
        "visit": {"id": state["id"], "status": state["status"]},
        "can_complete": state["status"] == Visit.VisitStatus.IN_PROGRESS,
        "request": ({"id": state["sales_request__id"], "status": state["sales_request__status"],
                     "revision": state["sales_request__revision"], "number": state["sales_request__number"]}
                    if state["sales_request__id"] is not None else None),
        "recorded_result": state["recorded"]["body"] if state["recorded"] else None,
    }
