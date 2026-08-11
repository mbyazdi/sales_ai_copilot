from django.db import models

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