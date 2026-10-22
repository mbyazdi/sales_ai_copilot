"""Separate strategy capabilities, mapped to the current single manager role."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied


def can_view_strategy(user):
    return bool(user and user.is_authenticated and user.is_active and user.is_staff)


def can_manage_strategy(user):
    return can_view_strategy(user)


def require_strategy_manager(actor_id, using="default"):
    # Never trust cached request-user role flags for a management write/replay.
    user = get_user_model().objects.using(using).filter(pk=actor_id).first()
    if not can_manage_strategy(user):
        raise PermissionDenied("دسترسی مدیریت راهبرد مجاز نیست.")
    return user


def require_strategy_viewer(actor_id, using="default"):
    """Dedicated management reads; never impersonate catalog/salesperson access."""
    user = get_user_model().objects.using(using).filter(pk=actor_id).first()
    if not can_view_strategy(user):
        raise PermissionDenied("دسترسی مشاهدهٔ راهبرد مجاز نیست.")
    return user
