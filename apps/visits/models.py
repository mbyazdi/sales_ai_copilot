from django.db import models
from django.conf import settings
from apps.customers.models import Customer


class Salesperson(models.Model):
    """
    Salesperson / field sales representative.
    """

    employee_code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="salesperson_profile",
    )

    first_name = models.CharField(
        max_length=100
    )

    last_name = models.CharField(
        max_length=100
    )

    phone = models.CharField(
        max_length=30,
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["last_name", "first_name"]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return f"{self.employee_code} - {self.full_name}"


class CustomerAssignment(models.Model):
    """
    Assigns customers to salespersons.

    A customer can be assigned to a salesperson.
    """

    salesperson = models.ForeignKey(
        Salesperson,
        on_delete=models.PROTECT,
        related_name="customer_assignments"
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="salesperson_assignments"
    )

    start_date = models.DateField()

    end_date = models.DateField(
        null=True,
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return (
            f"{self.salesperson} → "
            f"{self.customer}"
        )


class Visit(models.Model):
    """
    A field visit by a salesperson to a customer.
    """

    class VisitStatus(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    salesperson = models.ForeignKey(
        Salesperson,
        on_delete=models.PROTECT,
        related_name="visits"
    )

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="visits"
    )

    visit_date = models.DateField(
        db_index=True
    )

    status = models.CharField(
        max_length=20,
        choices=VisitStatus.choices,
        default=VisitStatus.PLANNED
    )

    # ------------------------------------------------
    # Information entered by salesperson
    # ------------------------------------------------

    customer_request = models.TextField(
        blank=True,
        help_text=(
            "New requirement or request mentioned "
            "by the customer during the visit."
        )
    )

    customer_feedback = models.TextField(
        blank=True
    )

    competitor_information = models.TextField(
        blank=True
    )

    notes = models.TextField(
        blank=True
    )

    # ------------------------------------------------
    # Visit result
    # ------------------------------------------------

    order_created = models.BooleanField(
        default=False
    )

    order_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0
    )

    follow_up_required = models.BooleanField(
        default=False
    )

    follow_up_date = models.DateField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = ["-visit_date", "-id"]

    def __str__(self):
        return (
            f"{self.visit_date} - "
            f"{self.customer.name} - "
            f"{self.salesperson.full_name}"
        )

class SalesOutcome(models.Model):
    """Actual outcome of presenting an AI recommendation during a sales visit."""

    class Outcome(models.TextChoices):
        PURCHASED = "PURCHASED", "خرید شد"
        INTERESTED = "INTERESTED", "علاقه‌مند شد"
        FOLLOW_UP = "FOLLOW_UP", "نیاز به پیگیری"
        REJECTED = "REJECTED", "رد شد"
        NOT_PRESENTED = "NOT_PRESENTED", "مطرح نشد"

    visit = models.ForeignKey(
        "Visit",
        on_delete=models.CASCADE,
        related_name="sales_outcomes",
    )

    recommendation = models.ForeignKey(
        "recommendations.CustomerRecommendation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_outcomes",
    )

    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
    )

    quantity = models.PositiveIntegerField(
        default=0,
    )

    sales_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    notes = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=["outcome", "created_at"]
            ),
            models.Index(
                fields=["visit", "outcome"]
            ),
            models.Index(
                fields=["recommendation", "outcome"]
            ),
        ]

    def __str__(self):
        product = getattr(
            getattr(self.recommendation, "product", None),
            "name",
            "-",
        )

        return (
            f"{product} / "
            f"{self.get_outcome_display()}"
        )

class FollowUpTask(models.Model):

    class Status(models.TextChoices):
        OPEN = "OPEN", "باز"
        DONE = "DONE", "انجام شده"
        CANCELLED = "CANCELLED", "لغو شده"

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="follow_up_tasks",
    )

    visit = models.ForeignKey(
        "Visit",
        on_delete=models.PROTECT,
        related_name="follow_up_tasks",
    )

    salesperson = models.ForeignKey(
        Salesperson,
        on_delete=models.PROTECT,
        related_name="follow_up_tasks",
    )

    due_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )

    notes = models.TextField(
        blank=True,
    )

    completed_at = models.DateTimeField(
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
            "status",
            "due_date",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.customer.customer_code} - "
            f"{self.due_date} - "
            f"{self.status}"
        )