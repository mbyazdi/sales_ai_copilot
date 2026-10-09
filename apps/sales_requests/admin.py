from django.contrib import admin

from .admin_base import InspectionOnlyAdmin
from .models import SalesRequest, SalesRequestAcknowledgement, SalesRequestLine, SalesRequestMutationReceipt


@admin.register(SalesRequest)
class SalesRequestAdmin(InspectionOnlyAdmin):
    list_display = ("id", "number", "visit", "status", "revision", "submitted_at")
    list_filter = ("status",)
    search_fields = ("number", "visit__customer__customer_code")
    list_select_related = ("visit__customer", "visit__salesperson")


@admin.register(SalesRequestLine)
class SalesRequestLineAdmin(InspectionOnlyAdmin):
    list_display = ("id", "sales_request", "product", "quantity", "is_selected", "selection_source")
    list_select_related = ("sales_request", "product")


@admin.register(SalesRequestAcknowledgement)
class SalesRequestAcknowledgementAdmin(InspectionOnlyAdmin):
    list_display = ("id", "sales_request", "actor", "acknowledged_at")
    list_select_related = ("sales_request", "actor")


@admin.register(SalesRequestMutationReceipt)
class SalesRequestMutationReceiptAdmin(InspectionOnlyAdmin):
    list_display = ("id", "visit", "command_uuid", "operation", "actor", "applied_revision", "created_at")
    list_select_related = ("visit", "actor", "sales_request")
