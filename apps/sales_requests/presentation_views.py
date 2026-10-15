"""Read-only page shells; commercial state/confirmation remains API-owned."""
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_safe

from apps.products.catalog import CatalogOptions
from apps.products.catalog_access import visit_customer_access
from apps.recommendations.catalog_context import CatalogContextUnavailable
from .basket import BasketConflict, _captured_context
from .submission import MESSAGE_DISCLOSURE, review_request


def _page_context(request, customer_code, visit_id):
    access = visit_customer_access(request.user, customer_code, visit_id)
    options = CatalogOptions.parse(request.GET)
    if options.catalog_context:
        _captured_context(access, options.catalog_context)
    query = {"visit_id": visit_id, **options.navigation_query(options.catalog_context)}
    return {
        "customer": access.customer, "visit": access.visit, "salesperson": access.user.salesperson_profile,
        "catalog_context": options.catalog_context or "",
        "basket_url": reverse("recommendation-presentation", args=[customer_code]) + "?" + urlencode(query) + "#basketPanel",
        "result_url": reverse("sales-request-result", args=[customer_code, visit_id]) + "?" + urlencode(options.navigation_query(options.catalog_context)),
        "review_api": reverse("visit-request-review-v1", args=[visit_id]),
        "submit_api": reverse("visit-request-submit-v1", args=[visit_id]),
    }


def _unavailable(request, error):
    status = 403 if isinstance(error, PermissionDenied) else 404
    if isinstance(error, (BasketConflict, CatalogContextUnavailable, ValueError, ValidationError)):
        status = 409
    response = render(request, "sales_requests/unavailable.html", status=status)
    response["Cache-Control"] = "no-store, private"
    return response


@login_required
@require_safe
def sales_request_review(request, customer_code, visit_id):
    try:
        context = _page_context(request, customer_code, visit_id)
    except (PermissionDenied, Http404, ValueError, ValidationError, CatalogContextUnavailable) as error:
        return _unavailable(request, error)
    response = render(request, "sales_requests/review.html", context)
    response["Cache-Control"] = "no-store, private"
    return response


@login_required
@require_safe
def sales_request_result(request, customer_code, visit_id):
    try:
        context = _page_context(request, customer_code, visit_id)
        state = review_request(request.user, customer_code, visit_id)
        if state["request"]["status"] != "SUBMITTED":
            response = redirect(reverse("sales-request-review", args=[customer_code, visit_id]) + "?" + urlencode(request.GET))
            response["Cache-Control"] = "no-store, private"
            return response
    except (PermissionDenied, Http404, ValueError, ValidationError, CatalogContextUnavailable, BasketConflict) as error:
        return _unavailable(request, error)
    # Presentation-only extraction from the stored snapshot. Do not regenerate
    # customer wording, alter persistence or include delivery info in copied text.
    context["copy_message"] = "\n".join(
        line for line in state["prepared_message_snapshot"].splitlines() if line.strip() != MESSAGE_DISCLOSURE
    ).strip()
    context["initial_state"] = state
    context["customer"] = {"name": state["customer"]["name"], "customer_code": state["customer"]["code"]}
    response = render(request, "sales_requests/result.html", context)
    response["Cache-Control"] = "no-store, private"
    return response
