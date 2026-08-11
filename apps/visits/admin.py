from django.contrib import admin

from .models import (
    CustomerAssignment,
    Salesperson,
    Visit,
)


@admin.register(Salesperson)
class SalespersonAdmin(admin.ModelAdmin):
    list_display = (
        "employee_code",
        "first_name",
        "last_name",
        "phone",
        "is_active",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "employee_code",
        "first_name",
        "last_name",
        "phone",
    )


@admin.register(CustomerAssignment)
class CustomerAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "customer",
        "salesperson",
        "start_date",
        "end_date",
        "is_active",
    )

    list_filter = (
        "is_active",
        "start_date",
        "end_date",
    )

    search_fields = (
        "customer__customer_code",
        "customer__name",
        "salesperson__employee_code",
        "salesperson__first_name",
        "salesperson__last_name",
    )


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        "visit_date",
        "customer",
        "salesperson",
        "status",
        "order_created",
        "order_amount",
        "follow_up_required",
    )

    list_filter = (
        "status",
        "order_created",
        "follow_up_required",
        "visit_date",
    )

    search_fields = (
        "customer__customer_code",
        "customer__name",
        "salesperson__employee_code",
        "salesperson__first_name",
        "salesperson__last_name",
        "customer_request",
    )