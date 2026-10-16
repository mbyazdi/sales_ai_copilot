"""Authoritative review and explicit submission; no delivery or Visit completion.

Submission replay uses the immutable header's submission_key/intent hash, not a
basket MutationReceipt. Every returned submission field comes from frozen data.
"""
from dataclasses import replace
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import Http404
from django.utils import timezone

from apps.core.reference_locks import lock_submission_references
from apps.customers.models import Customer
from apps.products.catalog_access import visit_customer_access
from apps.products.quotes import MAX_QUANTITY
from apps.visits.models import Visit
from .basket import BasketConflict, _captured_context, _commercial, _hash, _lines, _read_selection, _totals
from .models import SalesRequest, SalesRequestMutationReceipt


MESSAGE_DISCLOSURE = "در نسخه فعلی این پیام ارسال نمی‌شود و فقط نمایش داده می‌شود."


def _prepared_customer_message(request):
    """Format a NEW snapshot only; reads/replay must return the stored text."""
    amount = format(request.final_total, ",.0f").translate(str.maketrans("0123456789,", "۰۱۲۳۴۵۶۷۸۹٬"))
    return (
        f"{request.customer_snapshot['name']}، درخواست فروش شما با شماره {request.number} "
        f"به مبلغ {amount} تومان ثبت شد. از همراهی شما سپاسگزاریم.\n{MESSAGE_DISCLOSURE}"
    )


class SubmissionConflict(BasketConflict):
    def __init__(self, code, detail, review=None):
        super().__init__(code, detail)
        self.review = review


def submitted_result(request, lines):
    """Stable replay across process restarts/master-data changes; no repricing."""
    submission = request.pricing_snapshot.get("submission", {})
    if not submission.get("visit"):
        # Pre-service/imported foundation snapshots must never be repaired by GET.
        raise BasketConflict("SUBMISSION_SNAPSHOT_UNAVAILABLE", "اطلاعات ثبت این درخواست کامل نیست؛ با پشتیبانی بررسی کنید.")
    return {
        "version": 1,
        "request": {"id": request.pk, "number": request.number, "status": request.status,
                    "revision": request.revision, "submitted_at": request.submitted_at.isoformat()},
        "customer": request.customer_snapshot,
        "salesperson": request.salesperson_snapshot,
        "visit": submission["visit"],
        "currency": request.currency,
        "totals": {"base": format(request.base_total, ".0f"),
                   "discount": format(request.discount_total, ".0f"),
                   "final": format(request.final_total, ".0f")},
        "item_count": len(lines), "total_units": sum(line.quantity for line in lines),
        "lines": [{"id": line.pk, "product_id": line.product_id, "quantity": line.quantity,
                   "selection_source": line.selection_source, "recommendation_id": line.recommendation_id,
                   "product_snapshot": line.product_snapshot, "lineage_snapshot": line.lineage_snapshot,
                   "eligibility_snapshot": line.eligibility_snapshot, "pricing_snapshot": line.pricing_snapshot}
                  for line in lines],
        "pricing_snapshot": request.pricing_snapshot,
        "prepared_message_snapshot": request.prepared_message_snapshot,
        "message_disclosure": MESSAGE_DISCLOSURE,
        "can_submit": False,
    }


def _snapshot_totals(lines):
    try:
        return _totals([line.pricing_snapshot for line in lines])
    except (BasketConflict, ArithmeticError, TypeError, ValueError):
        return None


def _draft_validation(request, lines):
    """Reject contradictory persisted snapshots; GET never repairs them."""
    issues = []
    for line in lines:
        try:
            line.validate_submission_snapshot()
            quote = line.pricing_snapshot
            if (not isinstance(line.quantity, int) or isinstance(line.quantity, bool)
                    or not 1 <= line.quantity <= MAX_QUANTITY):
                raise ValueError
            if (quote["product_id"] != line.product_id or quote["customer_id"] != request.customer_id
                    or quote["quantity"] != line.quantity or line.currency != "TOMAN"
                    or quote["currency"] != "TOMAN" or not quote.get("quote_fingerprint")
                    or line.product_snapshot.get("id") != line.product_id
                    or not all(line.product_snapshot.get(k) for k in ("name", "code", "unit"))):
                raise ValueError
            for field, key in (("base_unit_price", "base_unit_price"), ("discount_percentage", "discount_percentage"),
                               ("discount_amount", "unit_discount"), ("final_unit_price", "final_unit_price"),
                               ("line_total", "line_total")):
                if getattr(line, field) != Decimal(quote[key]):
                    raise ValueError
            if line.pricing_source != quote["price_source"] or line.pricing_version != quote["price_source_version"]:
                raise ValueError
        except (ValidationError, ValueError, KeyError, TypeError, ArithmeticError):
            issues.append({"code": "DRAFT_INVALID", "line_id": line.pk, "product_id": line.product_id})
    if not issues:
        totals = _snapshot_totals(lines)
        if (request.currency != "TOMAN" or not totals
                or any(getattr(request, field) != Decimal(totals[key]) for field, key in (
                    ("base_total", "base"), ("discount_total", "discount"), ("final_total", "final")))
                or request.pricing_snapshot.get("totals") != totals
                or request.pricing_snapshot.get("line_quote_fingerprints") != [line.pricing_snapshot["quote_fingerprint"] for line in lines]):
            issues.append({"code": "DRAFT_INVALID", "line_id": None, "product_id": None})
    return issues


def _review(access, request, lines):
    commercial, _ = _commercial(access, {line.product_id: line.quantity for line in lines})
    by_product = {item["product_id"]: item for item in commercial["items"]}
    issues = _draft_validation(request, lines) if lines else [{"code": "EMPTY_BASKET"}]
    for line in lines:
        item = by_product[line.product_id]
        if not item["valid"]:
            issues.append({"code": item["reason_code"], "line_id": line.pk, "product_id": line.product_id})
        elif item["quote"] != line.pricing_snapshot:
            issues.append({"code": "PRICE_CHANGED", "line_id": line.pk, "product_id": line.product_id})
    if not commercial["valid"] and commercial.get("reason_code"):
        issues.append({"code": commercial["reason_code"]})
    active = access.visit.status == Visit.VisitStatus.IN_PROGRESS
    if not active:
        issues.append({"code": "VISIT_NOT_ACTIVE"})
    state = {
        "version": 1, "request": {"id": request.pk, "status": request.status, "revision": request.revision},
        "customer": {"id": access.customer.pk, "code": access.customer.customer_code, "name": access.customer.name},
        "visit": {"id": access.visit.pk, "status": access.visit.status}, "currency": "TOMAN",
        "item_count": len(lines), "total_units": sum(line.quantity for line in lines),
        "saved_totals": _snapshot_totals(lines),
        "lines": [{"id": line.pk, "product_id": line.product_id, "quantity": line.quantity,
                   "product_snapshot": line.product_snapshot, "lineage_snapshot": line.lineage_snapshot,
                   "selection_source": line.selection_source, "recommendation_id": line.recommendation_id,
                   "pricing_snapshot": line.pricing_snapshot, "saved_inventory": line.eligibility_snapshot,
                   "current": by_product[line.product_id]} for line in lines],
        "current_quote": commercial, "validation": {"valid": not issues, "issues": issues},
        "can_submit": not issues,
    }
    state["review_fingerprint"] = _hash(state)
    return state


def review_request(user, customer_code, visit_id):
    access = visit_customer_access(user, customer_code, visit_id)
    request, lines = _read_selection(access)
    if request is None:
        raise Http404
    if request.status == SalesRequest.Status.SUBMITTED:
        return submitted_result(request, lines)
    result = _review(access, request, lines)
    if not SalesRequest.objects.filter(pk=request.pk, revision=request.revision, status="DRAFT").exists():
        raise BasketConflict("REVISION_CONFLICT", "درخواست تغییر کرده است؛ بازبینی را دوباره انجام دهید.")
    return result


def _intent(access, request, command):
    return _hash({"version": 1, "operation": "SUBMIT", "actor_id": access.user.pk,
                  "visit_id": access.visit.pk, "request_id": request.pk,
                  **{key: value for key, value in command.items() if key != "command_uuid"}})


def _replay(access, request, fingerprint):
    if request.salesperson_snapshot.get("user_id") != access.user.pk:
        raise PermissionDenied
    if request.submission_intent_hash != fingerprint:
        raise BasketConflict("COMMAND_CONFLICT", "شناسه ثبت قبلاً با اطلاعات دیگری استفاده شده است.")
    return submitted_result(request, _lines(request)), 201, True


def _lock_commercial(access, lines):
    """Stabilize product/grade/inventory rows through commit on PostgreSQL.

    No stock reservation/deduction or missing-row creation. Missing data fails
    validation. Order IDs consistently; do not lock nullable outer joins.
    Demo prices are SELECT-only for runtime. The provider reads current prices
    at the validation boundary; those versioned quotes are point-in-time terms,
    not a lock on future price configuration (or a future external provider).
    """
    lock_submission_references(access.customer.pk, sorted(line.product_id for line in lines))
    customer = Customer.objects.get(pk=access.customer.pk)
    if not customer.is_active:
        raise PermissionDenied
    return replace(access, customer=customer)


def submit_request(user, visit_id, command):
    """Visit -> Request locks, target-row revision CAS, full guarded submission.

    Failed confirmation changes nothing. Matching committed replay precedes
    lifecycle/context/repricing checks but always follows current authorization.
    """
    with transaction.atomic():
        access = visit_customer_access(user, command["customer_code"], visit_id, lock_visit=True)
        request = SalesRequest.objects.select_for_update().filter(visit=access.visit).first()
        if request is None:
            raise Http404
        fingerprint = _intent(access, request, command)
        if request.status == "SUBMITTED" and request.submission_key == command["command_uuid"]:
            return _replay(access, request, fingerprint)
        if (SalesRequest.objects.filter(submission_key=command["command_uuid"]).exists()
                or SalesRequestMutationReceipt.objects.filter(visit=access.visit, command_uuid=command["command_uuid"]).exists()):
            raise BasketConflict("COMMAND_CONFLICT", "شناسه فرمان قبلاً برای عملیات دیگری استفاده شده است.")
        if request.status != "DRAFT":
            raise BasketConflict("REQUEST_NOT_DRAFT", "این درخواست قبلاً ثبت شده است و قابل تغییر نیست.")
        if access.visit.status != Visit.VisitStatus.IN_PROGRESS:
            raise BasketConflict("VISIT_NOT_ACTIVE", "ثبت درخواست فقط در ویزیت در حال انجام مجاز است.")
        if request.revision != command["expected_request_revision"]:
            raise BasketConflict("REVISION_CONFLICT", "درخواست تغییر کرده است؛ بازبینی را دوباره انجام دهید.")
        _captured_context(access, command["catalog_context"])
        lines = list(request.lines.select_for_update().filter(is_selected=True).order_by("pk"))
        access = _lock_commercial(access, lines)
        review = _review(access, request, lines)
        if not review["can_submit"]:
            code = review["validation"]["issues"][0]["code"]
            raise SubmissionConflict(code, "برخی اقلام نیاز به بررسی دارند؛ درخواست بدون تغییر باقی ماند.", review)
        if review["review_fingerprint"] != command["accepted_review_fingerprint"]:
            raise SubmissionConflict("REVIEW_CHANGED", "شرایط بازبینی تغییر کرده است؛ شرایط فعلی را بررسی و دوباره تأیید کنید.", review)
        updated = SalesRequest.objects.filter(pk=request.pk, revision=request.revision, status="DRAFT",
                                              visit__status="IN_PROGRESS").update(revision=F("revision") + 1, updated_at=timezone.now())
        if updated != 1:
            raise BasketConflict("REVISION_CONFLICT", "درخواست تغییر کرده است؛ بازبینی را دوباره انجام دهید.")
        request.revision += 1
        current = {item["product_id"]: item for item in review["current_quote"]["items"]}
        for line in lines:
            line.eligibility_snapshot = current[line.product_id]["inventory"]
            line.save()
        salesperson = access.user.salesperson_profile
        request.customer_snapshot = {"id": access.customer.pk, "code": access.customer.customer_code, "name": access.customer.name}
        request.salesperson_snapshot = {"id": salesperson.pk, "employee_code": salesperson.employee_code,
                                        "name": salesperson.full_name, "user_id": access.user.pk}
        request.pricing_snapshot = {**request.pricing_snapshot, "submission": {
            "version": 1, "review_fingerprint": review["review_fingerprint"],
            "quote_fingerprint": review["current_quote"]["quote_fingerprint"],
            "visit": {"id": access.visit.pk, "status": access.visit.status, "date": access.visit.visit_date.isoformat()},
        }}
        request.number = f"SR-{request.pk:08d}"
        request.submission_key, request.submission_intent_hash = command["command_uuid"], fingerprint
        request.submitted_at = timezone.now()
        request.prepared_message_snapshot = _prepared_customer_message(request)
        request.status = SalesRequest.Status.SUBMITTED
        # Full save is mandatory: the model rejects partial submission saves.
        try:
            request.save()
        except IntegrityError as error:
            # A globally reused submission UUID on another Visit may race. The
            # atomic block rolls back all snapshots/revision; never retry writes.
            raise BasketConflict("COMMAND_CONFLICT", "شناسه ثبت تکراری است؛ وضعیت درخواست را بررسی کنید.") from error
        return submitted_result(request, lines), 201, False
