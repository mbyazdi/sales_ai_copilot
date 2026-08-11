from django.contrib import admin

from .models import Inventory


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "available_quantity",
        "reserved_quantity",
        "sellable_quantity",
        "minimum_stock",
        "last_updated",
    )

    list_filter = (
        "product__product_group",
    )

    search_fields = (
        "product__product_code",
        "product__name",
    )