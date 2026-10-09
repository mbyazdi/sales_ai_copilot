"""Explicit rejection/defer only. Never creates a Draft, task or legacy outcome."""
import hashlib
import json

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import Http404

from apps.products.catalog_access import visit_customer_access
from apps.sales_requests.models import SalesRequest, SalesRequestLine, SalesRequestMutationReceipt
from apps.visits.models import Visit
from .catalog_context import CatalogContextUnavailable, saved_priority
from .models import CustomerRecommendation, RecommendationFeedbackEvent


class FeedbackConflict(Exception):
    def __init__(self, code, detail):
        self.code, self.detail = code, detail
        super().__init__(code)


def _intent(visit_id, command):
    intent = {"version": 1, "operation": "REJECT_RECOMMENDATION", "visit_id": visit_id,
              **{key: command[key] for key in ("customer_code", "recommendation_id", "action", "reason_code", "note", "expected_request_revision")},
              "context_fingerprint": hashlib.sha256(command["catalog_context"].encode()).hexdigest()}
    return hashlib.sha256(json.dumps(intent, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _replay(receipt, access, fingerprint):
    if receipt.actor_id != access.user.pk:
        raise PermissionDenied
    if receipt.operation != "REJECT_RECOMMENDATION" or receipt.intent_fingerprint != fingerprint:
        raise FeedbackConflict("COMMAND_CONFLICT", "شناسه این فرمان قبلاً برای تصمیم دیگری استفاده شده است.")
    return receipt.result["body"], receipt.result["http_status"], True


def _event_result(event):
    return {"id": event.pk, "recommendation_id": event.recommendation_id,
            "product_id": event.lineage_snapshot["product_id"], "event_type": event.event_type,
            "action": event.lineage_snapshot["action"], "reason_code": event.reason_code,
            "note": event.note, "created_at": event.created_at.isoformat()}


def record_feedback(user, visit_id, command):
    """Validated command -> event + successful receipt in one transaction.

    Lock order: Visit, existing Request, target Recommendation. Visit row locking
    serializes same-Visit PostgreSQL commands; receipt uniqueness is the durable
    backstop. No process locks, auto POST retries or request revision mutations.
    """
    fingerprint = _intent(visit_id, command)
    try:
        with transaction.atomic():
            access = visit_customer_access(user, command["customer_code"], visit_id, lock_visit=True)
            receipt = SalesRequestMutationReceipt.objects.filter(visit=access.visit, command_uuid=command["command_uuid"]).first()
            if receipt:
                # Retrieve historical success even after context expiry/lifecycle change.
                return _replay(receipt, access, fingerprint)
            if access.visit.status != Visit.VisitStatus.IN_PROGRESS:
                raise FeedbackConflict("VISIT_NOT_ACTIVE", "بازخورد جدید فقط برای ویزیت در حال انجام مجاز است.")
            request = SalesRequest.objects.select_for_update().filter(visit=access.visit).first()
            if request and request.status != SalesRequest.Status.DRAFT:
                raise FeedbackConflict("REQUEST_NOT_DRAFT", "درخواست ثبت‌شده قابل تغییر نیست.")
            revision = request.revision if request else None
            if command["expected_request_revision"] != revision:
                raise FeedbackConflict("REVISION_CONFLICT", "وضعیت درخواست تغییر کرده است؛ وضعیت فعلی را دوباره بررسی کنید.")
            recommendation = CustomerRecommendation.objects.select_for_update().select_related("product").filter(
                pk=command["recommendation_id"], customer=access.customer,
            ).first()
            if recommendation is None:
                raise Http404
            if not recommendation.is_active or not recommendation.product.is_active:
                raise CatalogContextUnavailable
            priority = saved_priority(access, command["catalog_context"])
            recommendation = next((row for row in priority.recommendations if row.pk == recommendation.pk), None)
            if recommendation is None:
                raise CatalogContextUnavailable
            if request and SalesRequestLine.objects.filter(sales_request=request, product_id=recommendation.product_id, is_selected=True).exists():
                raise FeedbackConflict("PRODUCT_ALREADY_SELECTED", "محصول در درخواست انتخاب شده است؛ ابتدا آن را صریحاً حذف کنید.")
            lineage = {
                "recommendation_id": recommendation.pk, "product_id": recommendation.product_id,
                "customer_id": access.customer.pk, "customer_code": access.customer.customer_code,
                "visit_id": access.visit.pk, "actor_id": access.user.pk,
                "rank": recommendation.rank, "recommendation_type": recommendation.recommendation_type,
                "score": str(recommendation.score), "confidence_score": str(recommendation.confidence_score),
                "evidence_quality": recommendation.evidence_quality, "reason": recommendation.reason,
                "explanation_snapshot": recommendation.explanation_snapshot, "score_breakdown": recommendation.score_breakdown,
                "recommendation_updated_at": recommendation.updated_at.isoformat(),
                "context_fingerprint": hashlib.sha256(priority.token.encode()).hexdigest(), "action": command["action"],
            }
            event = RecommendationFeedbackEvent.objects.create(
                visit=access.visit, recommendation=recommendation, sales_request=request,
                event_type=RecommendationFeedbackEvent.EventType.REJECTED,
                reason_code=command["reason_code"], note=command["note"], lineage_snapshot=lineage,
            )
            body = {"version": 1, "customer": {"id": access.customer.pk, "code": access.customer.customer_code},
                    "visit": {"id": access.visit.pk}, "feedback": _event_result(event)}
            SalesRequestMutationReceipt.objects.create(
                visit=access.visit, actor=access.user, command_uuid=command["command_uuid"],
                operation=SalesRequestMutationReceipt.Operation.REJECT_RECOMMENDATION,
                intent_fingerprint=fingerprint, sales_request=request, applied_revision=revision,
                result={"http_status": 201, "body": body},
            )
            return body, 201, False
    except IntegrityError:
        # A competing command may have won uniqueness; never keep a partial event.
        access = visit_customer_access(user, command["customer_code"], visit_id)
        receipt = SalesRequestMutationReceipt.objects.filter(visit=access.visit, command_uuid=command["command_uuid"]).first()
        if receipt:
            return _replay(receipt, access, fingerprint)
        raise


def feedback_history(user, customer_code, visit_id, *, recommendation_id=None, page=1):
    """Owned historical rejection/defer projection; no context/session creation."""
    from django.core.paginator import Paginator
    access = visit_customer_access(user, customer_code, visit_id)
    events = RecommendationFeedbackEvent.objects.filter(visit=access.visit, event_type="REJECTED")
    if recommendation_id is not None:
        if not CustomerRecommendation.objects.filter(pk=recommendation_id, customer=access.customer).exists():
            raise Http404
        events = events.filter(recommendation_id=recommendation_id)
    selected = Paginator(events.order_by("created_at", "pk"), 50).get_page(page)
    # Older foundation events need not contain the later action/product snapshots.
    rows = [{"id": event.pk, "recommendation_id": event.recommendation_id,
             "event_type": event.event_type, "reason_code": event.reason_code, "note": event.note,
             "created_at": event.created_at.isoformat(),
             "action": event.lineage_snapshot.get("action", "LATER" if event.reason_code == "LATER" else "REJECTED")}
            for event in selected]
    request = SalesRequest.objects.filter(visit=access.visit).values("id", "revision", "status").first()
    return {"version": 1, "customer": {"id": access.customer.pk, "code": access.customer.customer_code},
            "visit": {"id": access.visit.pk, "status": access.visit.status}, "request": request,
            "count": selected.paginator.count, "page": selected.number, "pages": selected.paginator.num_pages,
            "events": rows}
