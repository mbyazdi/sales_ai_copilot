from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect


@login_required
def role_home(request):
    """
    Route authenticated users to the correct
    workspace based on their application role.
    """

    if (
        request.user.is_staff
        or request.user.is_superuser
    ):
        return redirect(
            "recommendation-performance-dashboard"
        )

    salesperson = getattr(
        request.user,
        "salesperson_profile",
        None,
    )

    if (
        salesperson
        and salesperson.is_active
    ):
        return redirect(
            "salesperson-dashboard"
        )

    return HttpResponseForbidden(
        "No active Sales AI Copilot role is assigned "
        "to this user."
    )