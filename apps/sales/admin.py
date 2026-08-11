from django.contrib import admin

from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0

    fields = (
        "product",
        "quantity",
        "unit_price",
        "discount_amount",
        "total_amount",
    )

    readonly_fields = (
        "total_amount",
    )


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):

    list_display = (
        "invoice_number",
        "customer",
        "sale_date",
        "total_amount",
        "created_at",
    )

    search_fields = (
        "invoice_number",
        "customer__customer_code",
        "customer__name",
    )

    list_filter = (
        "sale_date",
    )

    date_hierarchy = "sale_date"

    ordering = (
        "-sale_date",
        "-id",
    )

    inlines = [
        SaleItemInline,
    ]


@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):

    list_display = (
        "sale",
        "product",
        "quantity",
        "unit_price",
        "discount_amount",
        "total_amount",
    )

    search_fields = (
        "sale__invoice_number",
        "product__product_code",
        "product__name",
    )

    list_filter = (
        "product__product_group",
    )