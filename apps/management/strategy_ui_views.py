"""Read-only management page shell. Frozen evidence comes from the existing API."""
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from django.utils import timezone
from zoneinfo import ZoneInfo

from .strategy_access import require_strategy_viewer, can_manage_strategy


@never_cache
@login_required
@require_safe
def strategy_overview(request):
    try:
        actor = require_strategy_viewer(request.user.pk)
    except PermissionDenied:
        return render(request, "management/strategy_overview.html", {"access_denied": True}, status=403)
    return render(request, "management/strategy_overview.html", {"can_edit_strategy": can_manage_strategy(actor)})


@never_cache
@login_required
@require_safe
def strategy_control(request):
    try:
        actor = require_strategy_viewer(request.user.pk)
    except PermissionDenied:
        return render(request, "management/strategy_control.html", {"access_denied": True}, status=403)
    return render(request, "management/strategy_control.html", {
        "can_edit_strategy": can_manage_strategy(actor), "editor_actor_id": actor.pk,
        "editor_environment": request.get_host() + ":" + settings.SESSION_COOKIE_NAME,
    })


@never_cache
@login_required
@require_safe
def strategy_comparison(request, comparison_id=None):
    try:
        actor = require_strategy_viewer(request.user.pk)
    except PermissionDenied:
        return render(request, "management/strategy_comparison.html", {"access_denied": True}, status=403)
    if comparison_id is not None and comparison_id < 1:
        return render(request, "management/strategy_comparison.html", {"invalid_id": True}, status=404)
    return render(request, "management/strategy_comparison.html", {
        "comparison_id": comparison_id, "can_create_comparison": can_manage_strategy(actor),
        "creation_actor_id": actor.pk,
        "creation_date": timezone.localtime(timezone.now(), ZoneInfo("Asia/Tehran")).date().isoformat(),
    })
