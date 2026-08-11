from django.db import models


class CustomerRecommendation(models.Model):
    """
    Stores a product recommendation generated for a customer.
    """

    class RecommendationType(models.TextChoices):
        CROSS_SELL = "CROSS_SELL", "Cross Sell"
        REPEAT_PURCHASE = "REPEAT_PURCHASE", "Repeat Purchase"
        SIMILAR_PRODUCT = "SIMILAR_PRODUCT", "Similar Product"
        CATEGORY = "CATEGORY", "Category Recommendation"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="recommendations",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="recommendations",
    )

    recommendation_type = models.CharField(
        max_length=30,
        choices=RecommendationType.choices,
    )

    score = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=0,
    )

    reason = models.TextField(
        blank=True,
    )

    rank = models.PositiveSmallIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-score", "rank"]
        indexes = [
            models.Index(
                fields=["customer", "is_active"]
            ),
            models.Index(
                fields=["customer", "recommendation_type"]
            ),
        ]

    def __str__(self):
        return (
            f"{self.customer.customer_code} - "
            f"{self.product.product_code} - "
            f"{self.score}"
        )