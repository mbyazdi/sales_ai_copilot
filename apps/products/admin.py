from django.contrib import admin

from .models import Brand, Category, Product


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "is_active",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "code",
        "name",
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "parent",
        "is_active",
    )

    list_filter = (
        "is_active",
        "parent",
    )

    search_fields = (
        "code",
        "name",
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "product_code",
        "name",
        "brand",
        "category",
        "product_group",
        "is_consumable",
        "is_durable",
        "repurchase_cycle_days",
        "is_active",
    )

    list_filter = (
        "product_group",
        "is_consumable",
        "is_durable",
        "is_active",
        "brand",
        "category",
    )

    search_fields = (
        "product_code",
        "name",
        "brand__name",
    )