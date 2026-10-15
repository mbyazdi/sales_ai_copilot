"""Read-only shell for the explicit, receipt-backed completion API."""
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_safe

from apps.products.catalog_access import visit_customer_access
from .completion import completion_state


@login_required
@require_safe
def visit_finish(request, customer_code, visit_id):
    try:
        access = visit_customer_access(request.user, customer_code, visit_id)
        state = completion_state(request.user, customer_code, visit_id)
    except (PermissionDenied, Http404) as error:
        response = render(request, "sales_requests/unavailable.html",
                          status=403 if isinstance(error, PermissionDenied) else 404)
    else:
        access.visit.status = state["visit"]["status"]  # Presentation only; never save.
        response = render(request, "visits/finish.html", {
            "customer": access.customer, "visit": access.visit,
            "salesperson": access.user.salesperson_profile, "initial_state": state,
            "customer_url": reverse("customer-search") + "?" + urlencode({
                "customer_code": customer_code, "visit_id": visit_id,
            }),
        })
    response["Cache-Control"] = "no-store, private"
    return response
