from django.db import models

from apps.customers.models import CustomerGrade
from apps.products.models import Product


class Promotion(models.Model):
    """
    Sales promotion.

    A promotion can target:
    - specific products
    - specific customer grades
    - a specific date range
    """

    class PromotionType(models.TextChoices):
        PERCENTAGE = "PERCENTAGE", "Percentage Discount"
        FIXED_AMOUNT = "FIXED_AMOUNT", "Fixed Amount Discount"
        BUY_X_GET_Y = "BUY_X_GET_Y", "Buy X Get Y"

    name = models.CharField(
        max_length=200
    )

    code = models.CharField(
        max_length=50,
        unique=True
    )

    promotion_type = models.CharField(
        max_length=20,
        choices=PromotionType.choices
    )

    start_date = models.DateField()

    end_date = models.DateField()

    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    discount_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    minimum_quantity = models.PositiveIntegerField(
        default=1
    )

    maximum_quantity = models.PositiveIntegerField(
        null=True,
        blank=True
    )

    description = models.TextField(
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    products = models.ManyToManyField(
        Product,
        related_name="promotions",
        through="PromotionProduct"
    )

    customer_grades = models.ManyToManyField(
        CustomerGrade,
        related_name="promotions",
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class PromotionProduct(models.Model):
    """
    Associates a promotion with a product.
    """

    promotion = models.ForeignKey(
        Promotion,
        on_delete=models.CASCADE,
        related_name="promotion_products"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="promotion_products"
    )

    priority = models.PositiveSmallIntegerField(
        default=0
    )

    class Meta:
        unique_together = [
            ("promotion", "product")
        ]

    def __str__(self):
        return (
            f"{self.promotion.code} - "
            f"{self.product.product_code}"
        )