from django.contrib import admin

from apps.sales_requests.admin_base import InspectionOnlyAdmin
from .models import RecommendationFeedbackEvent


@admin.register(RecommendationFeedbackEvent)
class RecommendationFeedbackEventAdmin(InspectionOnlyAdmin):
    list_display = ("id", "visit", "recommendation", "event_type", "reason_code", "created_at")
    list_filter = ("event_type", "reason_code")
    list_select_related = ("visit", "recommendation")
