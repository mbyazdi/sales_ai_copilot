"""Customer360's Visit-scoped entry to the shared signed priority resolver."""
from django.core.exceptions import PermissionDenied
from apps.products.catalog_access import visit_customer_access
from apps.recommendations.catalog_context import CatalogContextUnavailable, saved_priority
from apps.visits.models import Visit


def customer_selling_priority(user, customer, visit, token=""):
    if user.is_staff or visit is None:
        if token:
            raise PermissionDenied
        return None
    if not token and visit.status not in (Visit.VisitStatus.PLANNED, Visit.VisitStatus.IN_PROGRESS):
        return None
    if not isinstance(token, str) or len(token) > 100000:
        raise CatalogContextUnavailable
    access = visit_customer_access(user, customer.customer_code, visit.pk)
    return saved_priority(access, token)
