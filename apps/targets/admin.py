from django.contrib import admin

from .models import SalesTarget


@admin.register(SalesTarget)
class SalesTargetAdmin(admin.ModelAdmin):

    list_display = (
        "salesperson",
        "period_start",
        "period_end",
        "scope_type",
        "scope_code",
        "target_unit",
        "target_value",
        "actual_value",
        "is_active",
    )

    list_filter = (
        "scope_type",
        "target_unit",
        "is_active",
        "period_start",
    )

    search_fields = (
        "salesperson__employee_code",
        "salesperson__first_name",
        "salesperson__last_name",
        "product__product_code",
        "product__name",
        "category__code",
        "category__name",
        "product_group",
    )

    list_select_related = (
        "salesperson",
        "product",
        "category",
    )