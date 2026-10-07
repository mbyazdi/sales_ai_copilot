from django.db import models
from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.sales_requests.model_guards import AppendOnlyModel, validate_snapshot


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
    score_breakdown = models.JSONField(
        default=dict,
        blank=True,
    )

    confidence_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
    )

    evidence_quality = models.CharField(
        max_length=20,
        default="LOW",
    )

    explanation_snapshot = models.JSONField(
        default=dict,
        blank=True,
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

class RecommendationTuningSuggestion(models.Model):
    """
    Stores a proposed tuning change for the
    recommendation engine.

    Suggestions are generated from observed
    recommendation performance, but are not applied
    automatically.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        APPLIED = "APPLIED", "Applied"
        ROLLED_BACK = "ROLLED_BACK", "Rolled Back"

    recommendation_type = models.CharField(
        max_length=30,
        choices=CustomerRecommendation.RecommendationType.choices,
        blank=True,
    )

    metric = models.CharField(
        max_length=100,
    )

    current_value = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
    )

    suggested_value = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
    )

    reason = models.TextField(
        blank=True,
    )

    performance_snapshot = models.JSONField(
        default=dict,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    applied_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    applied_previous_value = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        null=True,
        blank=True,
    )

    rolled_back_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-created_at",
            "-id",
        ]

    def __str__(self):
        return (
            f"{self.recommendation_type or 'GENERAL'} "
            f"- {self.metric} "
            f"- {self.status}"
        )


class RecommendationFeedbackEvent(AppendOnlyModel):
    """Recommendation acceptance/rejection history, separate from legacy outcomes."""

    class EventType(models.TextChoices):
        ADDED_TO_REQUEST = "ADDED_TO_REQUEST", "افزوده‌شده به درخواست"
        REMOVED_FROM_REQUEST = "REMOVED_FROM_REQUEST", "حذف‌شده از درخواست"
        REJECTED = "REJECTED", "رد پیشنهاد"

    class RejectionReason(models.TextChoices):
        NOT_INTERESTED = "NOT_INTERESTED", "مشتری علاقه‌مند نبود"
        PRICE = "PRICE", "قیمت مناسب نبود"
        STOCK = "STOCK", "موجودی کافی نبود"
        NO_CURRENT_NEED = "NO_CURRENT_NEED", "فعلاً نیاز ندارد"
        OTHER_BRAND = "OTHER_BRAND", "قبلاً از برند/مدل دیگری استفاده می‌کند"
        LATER = "LATER", "بعداً پیگیری شود"
        OTHER = "OTHER", "دلیل دیگر"

    visit = models.ForeignKey("visits.Visit", on_delete=models.PROTECT, related_name="recommendation_feedback_events")
    recommendation = models.ForeignKey(CustomerRecommendation, on_delete=models.PROTECT, related_name="feedback_events")
    sales_request = models.ForeignKey("sales_requests.SalesRequest", on_delete=models.PROTECT, null=True, blank=True, related_name="feedback_events")
    line = models.ForeignKey("sales_requests.SalesRequestLine", on_delete=models.PROTECT, null=True, blank=True, related_name="feedback_events")
    event_type = models.CharField(max_length=24, choices=EventType.choices)
    reason_code = models.CharField(max_length=24, choices=RejectionReason.choices, blank=True)
    note = models.CharField(max_length=200, blank=True)
    lineage_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "رویداد بازخورد پیشنهاد"
        verbose_name_plural = "رویدادهای بازخورد پیشنهاد"
        ordering = ["created_at", "pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(event_type__in=["ADDED_TO_REQUEST", "REMOVED_FROM_REQUEST", "REJECTED"]), name="rfe_valid_event_type"),
            models.CheckConstraint(
                condition=(models.Q(event_type="REJECTED", reason_code__in=["NOT_INTERESTED", "PRICE", "STOCK", "NO_CURRENT_NEED", "OTHER_BRAND", "LATER", "OTHER"]) | models.Q(event_type__in=["ADDED_TO_REQUEST", "REMOVED_FROM_REQUEST"], reason_code="")),
                name="rfe_rejection_reason",
            ),
            models.CheckConstraint(condition=models.Q(event_type="REJECTED") | models.Q(sales_request__isnull=False, line__isnull=False), name="rfe_acceptance_has_line"),
            models.CheckConstraint(condition=models.Q(line__isnull=True) | models.Q(sales_request__isnull=False), name="rfe_line_has_request"),
        ]

    @property
    def product(self):
        return self.recommendation.product

    def clean(self):
        super().clean()
        validate_snapshot(self.lineage_snapshot, "lineage_snapshot")
        if not self.visit_id or not self.recommendation_id:
            return  # Field validation supplies the missing-reference error.
        recommendation = CustomerRecommendation.objects.filter(pk=self.recommendation_id).first()
        visit_model = self._meta.get_field("visit").remote_field.model
        visit = visit_model.objects.filter(pk=self.visit_id).first()
        if recommendation is None or visit is None:
            raise ValidationError("The authoritative visit and recommendation must exist.")
        if recommendation.customer_id != visit.customer_id:
            raise ValidationError({"recommendation": "Recommendation must belong to the visit customer."})
        if self.lineage_snapshot.get("recommendation_id") != self.recommendation_id:
            raise ValidationError({"lineage_snapshot": "Preserve the linked recommendation identity."})
        if self.sales_request_id:
            request_model = self._meta.get_field("sales_request").remote_field.model
            request_visit = request_model.objects.filter(pk=self.sales_request_id).values_list("visit_id", flat=True).first()
            if request_visit != self.visit_id:
                raise ValidationError({"sales_request": "Request must belong to the event visit."})
        if self.line_id:
            line_model = self._meta.get_field("line").remote_field.model
            line = line_model.objects.filter(pk=self.line_id).first()
            if line is None or line.sales_request_id != self.sales_request_id or line.recommendation_id != self.recommendation_id or line.product_id != recommendation.product_id:
                raise ValidationError({"line": "Line, request and recommendation identities must match."})

    def __str__(self):
        return f"پیشنهاد {self.recommendation_id} · {self.get_event_type_display()}"
