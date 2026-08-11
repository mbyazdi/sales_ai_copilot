from django.contrib import admin

from .models import Promotion, PromotionProduct


class PromotionProductInline(admin.TabularInline):
    model = PromotionProduct
    extra = 1


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "promotion_type",
        "start_date",
        "end_date",
        "minimum_quantity",
        "is_active",
    )

    list_filter = (
        "promotion_type",
        "is_active",
        "start_date",
        "end_date",
    )

    search_fields = (
        "code",
        "name",
    )

    filter_horizontal = (
        "customer_grades",
    )

    inlines = [
        PromotionProductInline,
    ]