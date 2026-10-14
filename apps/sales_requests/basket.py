"""DRAFT-only coordination. Reads never create or repair business records."""
import hashlib
import json
from decimal import Decimal

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import Http404
from django.utils import timezone

from apps.products.catalog_access import visit_customer_access
from apps.products.eligibility import product_eligibility
from apps.products.models import Product
from apps.products.pricing import CURRENCY, MAX_WHOLE_AMOUNT, DemoPriceProvider, PriceState, PricingInputError
from apps.recommendations.catalog_context import CONTEXT_SALT, CatalogContextUnavailable, saved_priority
from apps.recommendations.models import RecommendationFeedbackEvent
from apps.visits.models import Visit
from .models import SalesRequest, SalesRequestLine, SalesRequestMutationReceipt


MAX_BASKET_ITEMS = 50


class BasketConflict(Exception):
    def __init__(self, code, detail):
        self.code, self.detail = code, detail
        super().__init__(code)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _lines(request):
    return list(request.lines.filter(is_selected=True).order_by("pk")) if request else []


def _read_selection(access):
    request = SalesRequest.objects.filter(visit=access.visit).first()
    lines = _lines(request)
    if request and not SalesRequest.objects.filter(pk=request.pk, revision=request.revision, status=request.status).exists():
        raise BasketConflict("REVISION_CONFLICT", "درخواست هنگام خواندن تغییر کرده است؛ وضعیت فعلی را دوباره بررسی کنید.")
    return request, lines


def _commercial(access, quantities):
    """Fixed-size batched reads, fresh prices/stock; no reservation guarantee."""
    if len(quantities) > MAX_BASKET_ITEMS:
        raise BasketConflict("BASKET_LIMIT", "حداکثر ۵۰ محصول در درخواست قابل انتخاب است.")
    products = {p.pk: p for p in Product.objects.filter(pk__in=quantities).select_related("inventory").order_by("pk")}
    if len(products) != len(quantities):
        raise Http404
    try:
        prices = DemoPriceProvider().quote_many(access.customer.pk, quantities)
    except PricingInputError as error:
        # A changed price can overflow an existing line. Reads/removal must
        # remain available; do not round, fabricate or silently reprice it.
        items = [{"product_id": pk, "product_code": products[pk].product_code, "name": products[pk].name,
                  "quantity": quantities[pk], "inventory": product_eligibility(products[pk]),
                  "pricing_state": "CONFIGURATION_ERROR", "pricing_reason": error.code,
                  "quote": None, "valid": False, "reason_code": "PRICE_CONFIGURATION_ERROR"}
                 for pk in sorted(quantities)]
        return {"items": items, "totals": None, "valid": False, "quote_fingerprint": None}, products
    items = []
    for pk in sorted(quantities):
        product, result = products[pk], prices[pk]
        inventory = product_eligibility(product)
        reason = inventory["non_addable_reason"]
        if reason is None and quantities[pk] > inventory["available_quantity"]:
            reason = "INSUFFICIENT_STOCK"
        if reason is None and result.state != PriceState.AVAILABLE:
            reason = "PRICE_UNAVAILABLE" if result.state == PriceState.UNAVAILABLE else "PRICE_CONFIGURATION_ERROR"
        items.append({"product_id": pk, "product_code": product.product_code, "name": product.name,
                      "quantity": quantities[pk], "inventory": inventory,
                      "pricing_state": str(result.state), "pricing_reason": result.reason_code,
                      "quote": result.quote.as_dict() if result.quote else None,
                      "valid": reason is None, "reason_code": reason})
    try:
        totals = _totals([item["quote"] for item in items])
    except BasketConflict:
        return {"items": items, "totals": None, "valid": False, "quote_fingerprint": None,
                "reason_code": "REQUEST_AMOUNT_OUT_OF_RANGE"}, products
    valid = all(item["valid"] for item in items)
    # Pricing fingerprint deliberately excludes volatile stock/timestamps. Stock
    # is independently enforced on every priced mutation, even with a valid quote.
    fingerprint = _hash({"version": 1, "customer_id": access.customer.pk, "visit_id": access.visit.pk,
                         "items": [[item["product_id"], item["quantity"], item["quote"]] for item in items]})
    return {"items": items, "totals": totals, "valid": valid,
            "quote_fingerprint": fingerprint}, products


def _totals(quotes):
    if any(not quote or any(key not in quote for key in ("line_base", "line_discount", "line_total")) for quote in quotes):
        return None
    totals = {out: sum((Decimal(q[key]) for q in quotes), Decimal(0)) for out, key in (
        ("base", "line_base"), ("discount", "line_discount"), ("final", "line_total"))}
    if any(value > MAX_WHOLE_AMOUNT for value in totals.values()):
        raise BasketConflict("REQUEST_AMOUNT_OUT_OF_RANGE", "جمع درخواست بیش از محدوده مجاز است.")
    return {key: format(value, ".0f") for key, value in totals.items()}


def _projection(access, request, lines, commercial):
    by_product = {item["product_id"]: item for item in commercial["items"]}
    return {"version": 1, "customer": {"id": access.customer.pk, "code": access.customer.customer_code},
            "visit": {"id": access.visit.pk, "status": access.visit.status}, "currency": CURRENCY,
            "request": {"id": request.pk, "status": request.status, "revision": request.revision} if request else None,
            "editable": access.visit.status == Visit.VisitStatus.IN_PROGRESS and (not request or request.status == "DRAFT"),
            "item_count": len(lines), "total_units": sum(line.quantity for line in lines),
            "saved_totals": _totals([line.pricing_snapshot for line in lines]),
            "lines": [{"id": line.pk, "product_id": line.product_id, "quantity": line.quantity,
                       "selection_source": line.selection_source, "recommendation_id": line.recommendation_id,
                       "product_snapshot": line.product_snapshot, "lineage_snapshot": line.lineage_snapshot,
                       "eligibility_snapshot": line.eligibility_snapshot, "pricing_snapshot": line.pricing_snapshot}
                      for line in lines],
            "current_quote": commercial,
            "quote_changed": any(line.pricing_snapshot != by_product[line.product_id]["quote"] for line in lines)}


def inspect_basket(user, customer_code, visit_id):
    access = visit_customer_access(user, customer_code, visit_id)
    # Detect a changed header/selection observation without taking runtime write
    # locks or automatically retrying. Mutation revalidates price/stock separately.
    request, lines = _read_selection(access)
    commercial, _ = _commercial(access, {line.product_id: line.quantity for line in lines})
    return _projection(access, request, lines, commercial)


def basket_quote(user, customer_code, visit_id, product_id, quantity):
    """Quote the resulting selection, including all existing selected products."""
    access = visit_customer_access(user, customer_code, visit_id)
    request, lines = _read_selection(access)
    quantities = {line.product_id: line.quantity for line in lines}
    quantities[product_id] = quantity
    commercial, _ = _commercial(access, quantities)
    return {"version": 1, "visit_id": access.visit.pk, "customer_code": customer_code,
            "editable": access.visit.status == Visit.VisitStatus.IN_PROGRESS and (not request or request.status == "DRAFT"),
            "expected_request_revision": request.revision if request else None, **commercial}


def _captured_context(access, token):
    # Edits/removals use existing captured lineage; don't revalidate regenerated
    # recommendation rows or strand a draft because the selling token expired.
    try:
        payload = signing.loads(token, salt=CONTEXT_SALT)
        binding = {"version": 1, "actor": access.user.pk, "salesperson": access.visit.salesperson_id,
                   "customer": access.customer.pk, "visit": access.visit.pk}
        if not isinstance(payload, dict) or any(payload.get(k) != v for k, v in binding.items()):
            raise CatalogContextUnavailable
    except (signing.BadSignature, TypeError, ValueError) as error:
        raise CatalogContextUnavailable from error


def _replay(receipt, access, operation, fingerprint):
    if receipt.actor_id != access.user.pk:
        raise PermissionDenied
    if receipt.operation != operation or receipt.intent_fingerprint != fingerprint:
        raise BasketConflict("COMMAND_CONFLICT", "شناسه فرمان قبلاً برای درخواست دیگری استفاده شده است.")
    return receipt.result["body"], receipt.result["http_status"], True


def _save_quote(line, item):
    quote = item["quote"]
    line.quantity = item["quantity"]
    line.base_unit_price = Decimal(quote["base_unit_price"])
    line.discount_percentage = Decimal(quote["discount_percentage"])
    # Stage 1 discount_amount is the per-unit discount snapshot.
    line.discount_amount = Decimal(quote["unit_discount"])
    line.final_unit_price = Decimal(quote["final_unit_price"])
    line.line_total = Decimal(quote["line_total"])
    line.currency = quote["currency"]
    line.pricing_source, line.pricing_version = quote["price_source"], quote["price_source_version"]
    line.pricing_snapshot, line.eligibility_snapshot = quote, item["inventory"]
    line.save()


def _event(access, request, line, event_type):
    if line.selection_source == SalesRequestLine.SelectionSource.RECOMMENDATION:
        RecommendationFeedbackEvent.objects.create(
            visit=access.visit, recommendation_id=line.recommendation_id, sales_request=request,
            line=line, event_type=event_type, lineage_snapshot={**line.lineage_snapshot, "line_id": line.pk})


def mutate_basket(user, visit_id, operation, command, *, request_id=None, line_id=None):
    """Serialize Visit -> Request; acquire revision before lines/events/receipt.

    No automatic retry on ambiguous/database-busy errors. Any failed command
    rolls back all effects. Visit locking coordinates with the feedback API;
    uniqueness and target-row CAS remain the durable correctness boundaries.
    """
    intent = {"version": 1, "visit_id": visit_id, "operation": operation,
              "request_id": request_id, "line_id": line_id,
              **{k: v for k, v in command.items() if k != "command_uuid"}}
    fingerprint = _hash(intent)
    try:
        with transaction.atomic():
            access = visit_customer_access(user, command["customer_code"], visit_id, lock_visit=True)
            receipt = SalesRequestMutationReceipt.objects.filter(visit=access.visit, command_uuid=command["command_uuid"]).first()
            if receipt:
                return _replay(receipt, access, operation, fingerprint)
            if access.visit.status != Visit.VisitStatus.IN_PROGRESS:
                raise BasketConflict("VISIT_NOT_ACTIVE", "تغییر درخواست فقط در ویزیت در حال انجام مجاز است.")
            request = SalesRequest.objects.select_for_update().filter(visit=access.visit).first()
            if request_id is not None and (not request or request.pk != request_id):
                raise Http404
            if request and request.status != SalesRequest.Status.DRAFT:
                raise BasketConflict("REQUEST_NOT_DRAFT", "درخواست ثبت‌شده قابل تغییر نیست.")
            if command["expected_request_revision"] != (request.revision if request else None):
                raise BasketConflict("REVISION_CONFLICT", "درخواست تغییر کرده است؛ وضعیت فعلی را دوباره بررسی کنید.")
            lines = _lines(request)
            line = next((row for row in lines if row.pk == line_id), None)
            if operation != "ADD_PRODUCT" and line is None:
                raise BasketConflict("LINE_NOT_SELECTED", "این قلم دیگر در درخواست انتخاب نشده است.")
            recommendation = None
            if operation == "ADD_PRODUCT":
                priority = saved_priority(access, command["catalog_context"])
                product_id = command["product_id"]
                if any(row.product_id == product_id for row in lines):
                    raise BasketConflict("PRODUCT_ALREADY_SELECTED", "محصول انتخاب شده است؛ تعداد قلم موجود را تغییر دهید.")
                recommendation = next((r for r in priority.recommendations if r.product_id == product_id), None)
            else:
                _captured_context(access, command["catalog_context"])
                product_id = line.product_id
            quantities = {row.product_id: row.quantity for row in lines}
            if operation == "REMOVE_PRODUCT":
                quantities.pop(product_id)
            else:
                quantities[product_id] = command["quantity"]
            commercial, products = _commercial(access, quantities)
            if operation != "REMOVE_PRODUCT":
                invalid = next((item for item in commercial["items"] if not item["valid"]), None)
                if invalid:
                    raise BasketConflict(invalid["reason_code"], "قیمت یا موجودی یکی از اقلام برای این تعداد در دسترس نیست.")
                if not commercial["valid"]:
                    raise BasketConflict("REQUEST_AMOUNT_OUT_OF_RANGE", "جمع درخواست بیش از محدوده مجاز است.")
                if commercial["quote_fingerprint"] != command["accepted_quote_fingerprint"]:
                    raise BasketConflict("PRICE_CHANGED", "قیمت درخواست تغییر کرده است؛ قیمت جدید را بررسی و تأیید کنید.")
            if request is None:
                request = SalesRequest.objects.create(visit=access.visit)
            revision = request.revision
            updated = SalesRequest.objects.filter(pk=request.pk, status="DRAFT", revision=revision,
                                                  visit__status="IN_PROGRESS").update(revision=F("revision") + 1, updated_at=timezone.now())
            if updated != 1:
                raise BasketConflict("REVISION_CONFLICT", "درخواست تغییر کرده است؛ وضعیت فعلی را دوباره بررسی کنید.")
            request.revision = revision + 1
            if operation == "REMOVE_PRODUCT":
                line.is_selected, line.removed_at = False, timezone.now()
                line.save()
                _event(access, request, line, "REMOVED_FROM_REQUEST")
                lines.remove(line)
            else:
                if operation == "ADD_PRODUCT":
                    product = products[product_id]
                    lineage = {}
                    if recommendation:
                        lineage = {"recommendation_id": recommendation.pk, "product_id": product_id,
                                   "customer_id": access.customer.pk, "visit_id": visit_id, "actor_id": access.user.pk,
                                   "rank": recommendation.rank, "recommendation_type": recommendation.recommendation_type,
                                   "reason": recommendation.reason, "explanation_snapshot": recommendation.explanation_snapshot,
                                   "score_breakdown": recommendation.score_breakdown, "score": str(recommendation.score),
                                   "context_fingerprint": hashlib.sha256(priority.token.encode()).hexdigest()}
                    line = SalesRequestLine(sales_request=request, product=product,
                        selection_source="RECOMMENDATION" if recommendation else "ORDINARY", recommendation=recommendation,
                        quantity=command["quantity"], lineage_snapshot=lineage,
                        product_snapshot={"id": product_id, "code": product.product_code, "name": product.name, "unit": product.unit})
                    lines.append(line)
                quoted = {item["product_id"]: item for item in commercial["items"]}
                for row in lines:
                    _save_quote(row, quoted[row.product_id])
                if operation == "ADD_PRODUCT":
                    _event(access, request, line, "ADDED_TO_REQUEST")
            totals = _totals([row.pricing_snapshot for row in lines])
            request.base_total = Decimal(totals["base"]) if totals else None
            request.discount_total = Decimal(totals["discount"]) if totals else None
            request.final_total = Decimal(totals["final"]) if totals else None
            request.currency = CURRENCY
            request.pricing_snapshot = {"version": 1, "totals": totals,
                                        "line_quote_fingerprints": [row.pricing_snapshot.get("quote_fingerprint") for row in lines]}
            request.save()
            body = _projection(access, request, lines, commercial)
            status = 201 if operation == "ADD_PRODUCT" else 200
            SalesRequestMutationReceipt.objects.create(visit=access.visit, actor=access.user,
                command_uuid=command["command_uuid"], operation=operation, intent_fingerprint=fingerprint,
                sales_request=request, applied_revision=request.revision, result={"http_status": status, "body": body})
            return body, status, False
    except IntegrityError:
        access = visit_customer_access(user, command["customer_code"], visit_id)
        receipt = SalesRequestMutationReceipt.objects.filter(visit=access.visit, command_uuid=command["command_uuid"]).first()
        if receipt:
            return _replay(receipt, access, operation, fingerprint)
        raise


def command_status(user, customer_code, visit_id, command_uuid):
    access = visit_customer_access(user, customer_code, visit_id)
    receipt = SalesRequestMutationReceipt.objects.filter(visit=access.visit, actor=access.user, command_uuid=command_uuid).first()
    if receipt is None:
        raise Http404
    return {"version": 1, "command_uuid": str(receipt.command_uuid), "operation": receipt.operation,
            "applied_revision": receipt.applied_revision, "result": receipt.result}
