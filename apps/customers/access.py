"""Current-customer access boundary; historical visit ownership is separate."""

from django.core.exceptions import PermissionDenied

from .models import Customer


def customer_access_queryset(user, queryset=None):
    """Staff override, otherwise active profile plus is_active assignment.

    Assignment dates do not introduce additional eligibility rules here.
    Filtering the queryset protects both code and primary-key lookups.
    """
    if not user.is_authenticated:
        raise PermissionDenied("دسترسی به اطلاعات مشتری مجاز نیست.")
    if queryset is None:
        queryset = Customer.objects.all()
    if user.is_staff:
        # Existing temporary staff inspection override; no manager/team relation
        # exists yet. Current customer reads exclude inactive master records.
        return queryset.filter(is_active=True)
    salesperson = getattr(user, "salesperson_profile", None)
    if salesperson is None or not salesperson.is_active:
        raise PermissionDenied("دسترسی به اطلاعات مشتری مجاز نیست.")
    return queryset.filter(
        salesperson_assignments__salesperson=salesperson,
        salesperson_assignments__is_active=True,
    ).distinct()
