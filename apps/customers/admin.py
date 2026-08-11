from django.contrib import admin

from .models import Customer, Customer360, CustomerGrade


@admin.register(CustomerGrade)
class CustomerGradeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "priority",
        "is_active",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "code",
        "name",
    )


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "customer_code",
        "name",
        "customer_type",
        "grade",
        "city",
        "is_active",
    )

    list_filter = (
        "customer_type",
        "grade",
        "is_active",
    )

    search_fields = (
        "customer_code",
        "name",
        "phone",
    )


@admin.register(Customer360)
class Customer360Admin(admin.ModelAdmin):
    list_display = (
        "customer",
        "segment",
        "rfm_score",
        "total_sales_amount",
        "days_since_last_purchase",
        "sales_30d_change_percent",
        "calculated_at",
    )

    list_filter = (
        "segment",
    )

    search_fields = (
        "customer__customer_code",
        "customer__name",
    )

    readonly_fields = (
        "calculated_at",
    )