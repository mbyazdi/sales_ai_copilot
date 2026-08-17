from django.db import models
from decimal import Decimal


class CustomerRecommendation(models.Model):
    """
    Stores a product recommendation generated for a customer.
    """

    class RecommendationType(models.TextChoices):
        CROSS_SELL = "CROSS_SELL", "Cross Sell"
        REPEAT_PURCHASE = "REPEAT_PURCHASE", "Repeat Purchase"
        SIMILAR_PRODUCT = "SIMILAR_PRODUCT", "Similar Product"
        CATEGORY = "CATEGORY", "Category Recommendation"
        UP_SELL = "UP_SELL", "Up Sell"

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

        constraints = [
            models.UniqueConstraint(
                fields=["customer", "product"],
                condition=models.Q(is_active=True),
                name="unique_active_customer_product_recommendation",
            ),
        ]

        indexes = [
            models.Index(
                fields=["customer", "is_active"],
            ),
            models.Index(
                fields=["customer", "recommendation_type"],
            ),
        ]
    def __str__(self):
        return (
            f"{self.customer.customer_code} - "
            f"{self.product.product_code} - "
            f"{self.score}"
        )
class ProductAssociation(models.Model):
    """
    Stores product-to-product purchase associations.

    Example:
        BOS002 -> PHD001

    Meaning:
        Customers who purchased BOS002 also frequently
        purchased PHD001.
    """

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="associations",
    )

    associated_product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="associated_from",
    )

    occurrence_count = models.PositiveIntegerField(
        default=0,
    )

    support = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=0,
    )

    confidence = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        default=0,
    )

    lift = models.DecimalField(
        max_digits=8,
        decimal_places=4,
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
        ordering = [
            "-lift",
            "-confidence",
            "-occurrence_count",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "product",
                    "associated_product",
                ],
                name="unique_product_association",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "product",
                    "is_active",
                ]
            ),
            models.Index(
                fields=[
                    "associated_product",
                    "is_active",
                ]
            ),
        ]

    def __str__(self):
        return (
            f"{self.product.product_code} -> "
            f"{self.associated_product.product_code} "
            f"(lift={self.lift})"
        )


    
class RecommendationConfig(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True,
        default="default",
    )

    is_active = models.BooleanField(
        default=True,
    )

    # General
    min_recommendation_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("20"),
    )

    max_recommendations = models.PositiveIntegerField(
        default=5,
    )

    # Category affinity
    category_rank_1_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("30"),
    )

    category_rank_2_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("25"),
    )

    category_rank_3_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("20"),
    )

    category_rank_4_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("15"),
    )

    category_rank_5_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("10"),
    )

    category_rank_6_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("10"),
    )

    category_rank_7_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("8"),
    )

    category_rank_8_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("8"),
    )

    category_rank_9_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("5"),
    )

    category_rank_10_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("5"),
    )

    category_rank_11_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("5"),
    )

    # Customer grade
    grade_a_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("15"),
    )

    grade_b_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("10"),
    )

    grade_c_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("5"),
    )

    # Promotion
    promotion_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("20"),
    )

    # Association
    association_max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("15"),
    )

    association_lift_max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("10"),
    )

    association_evidence_1_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("1"),
    )

    association_evidence_2_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("3"),
    )

    association_evidence_3_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("5"),
    )

    # Repurchase
    repurchase_no_cycle_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("20"),
    )

    repurchase_overdue_30_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("35"),
    )

    repurchase_overdue_90_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("40"),
    )

    repurchase_overdue_high_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("45"),
    )

    durable_previous_purchase_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("5"),
    )

    # Up-sell
    upsell_10_percent_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("10"),
    )

    upsell_25_percent_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("20"),
    )

    upsell_50_percent_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("30"),
    )

    upsell_high_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("35"),
    )

    # Similar product
    similar_product_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("15"),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.name