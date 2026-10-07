"""Current operational catalog access, reusing the existing assignment boundary."""
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.customers.access import customer_access_queryset
from apps.visits.models import Visit


@dataclass(frozen=True)
class CatalogAccess:
    user: object
    customer: object
    visit: Visit


def catalog_access(user, customer_code, visit_id):
    # Re-read role/profile even for a reused/stale service caller instance.
    if not user.is_authenticated:
        raise PermissionDenied("دسترسی به فهرست محصولات مجاز نیست.")
    current_user = get_user_model().objects.select_related("salesperson_profile").filter(pk=user.pk).first()
    if current_user is None or not current_user.is_active or current_user.is_staff:
        raise PermissionDenied("دسترسی به فهرست محصولات مجاز نیست.")
    customers = customer_access_queryset(current_user)
    customer = get_object_or_404(customers, customer_code=customer_code, is_active=True)
    visit = get_object_or_404(
        Visit, pk=visit_id, customer=customer, salesperson=current_user.salesperson_profile,
    )
    # Planned visits permit read-only preparation. Closed visits are not selling sessions.
    if visit.status not in (Visit.VisitStatus.PLANNED, Visit.VisitStatus.IN_PROGRESS):
        raise Http404
    return CatalogAccess(current_user, customer, visit)
