from django.db import models


class CustomerGrade(models.Model):
    """
    Defines the commercial grade of a customer.

    Example:
        A = Strategic
        B = High Value
        C = Medium Value
        D = Low Value
    """

    code = models.CharField(
        max_length=10,
        unique=True
    )

    name = models.CharField(
        max_length=100
    )

    description = models.TextField(
        blank=True
    )

    priority = models.PositiveSmallIntegerField(
        default=0
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
        ordering = ["-priority", "code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Customer(models.Model):
    """
    Master data of customers.

    The demo data is focused on the electrical-appliance
    business and its commercial customers.
    """

    class CustomerType(models.TextChoices):
        STORE = "STORE", "Store"
        DISTRIBUTOR = "DISTRIBUTOR", "Distributor"
        WHOLESALER = "WHOLESALER", "Wholesaler"
        ELECTRICAL_STORE = "ELECTRICAL_STORE", "Electrical Store"
        HOME_APPLIANCE_STORE = (
            "HOME_APPLIANCE_STORE",
            "Home Appliance Store"
        )
        OTHER = "OTHER", "Other"

    customer_code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True
    )

    name = models.CharField(
        max_length=200
    )

    customer_type = models.CharField(
        max_length=30,
        choices=CustomerType.choices,
        default=CustomerType.STORE
    )

    grade = models.ForeignKey(
        CustomerGrade,
        on_delete=models.PROTECT,
        related_name="customers",
        null=True,
        blank=True
    )

    city = models.CharField(
        max_length=100,
        blank=True
    )

    address = models.TextField(
        blank=True
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
        ordering = ["name"]

    def __str__(self):
        return f"{self.customer_code} - {self.name}"


class Customer360(models.Model):
    """
    Pre-calculated customer 360 snapshot.

    This table is refreshed periodically and is used by
    the recommendation engine.
    """

    class Segment(models.TextChoices):
        HIGH_VALUE = "HIGH_VALUE", "High Value"
        GROWTH = "GROWTH", "Growth"
        STABLE = "STABLE", "Stable"
        AT_RISK = "AT_RISK", "At Risk"
        INACTIVE = "INACTIVE", "Inactive"
        NEW = "NEW", "New"

    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name="customer_360"
    )

    # --------------------------------
    # Purchase summary
    # --------------------------------

    total_orders = models.PositiveIntegerField(
        default=0
    )

    total_items = models.PositiveIntegerField(
        default=0
    )

    total_sales_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0
    )

    average_order_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0
    )

    # --------------------------------
    # Recency / Frequency
    # --------------------------------

    last_purchase_date = models.DateField(
        null=True,
        blank=True
    )

    first_purchase_date = models.DateField(
        null=True,
        blank=True
    )

    purchase_frequency = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    days_since_last_purchase = models.PositiveIntegerField(
        default=0
    )

    # --------------------------------
    # RFM
    # --------------------------------

    recency_score = models.PositiveSmallIntegerField(
        default=0
    )

    frequency_score = models.PositiveSmallIntegerField(
        default=0
    )

    monetary_score = models.PositiveSmallIntegerField(
        default=0
    )

    rfm_score = models.PositiveSmallIntegerField(
        default=0
    )

    # --------------------------------
    # Customer classification
    # --------------------------------

    segment = models.CharField(
        max_length=20,
        choices=Segment.choices,
        default=Segment.NEW
    )

    # --------------------------------
    # Buying behavior
    # --------------------------------

    top_category = models.CharField(
        max_length=100,
        blank=True
    )

    top_product_code = models.CharField(
        max_length=50,
        blank=True
    )

    # --------------------------------
    # Trends
    # --------------------------------

    sales_30d = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0
    )

    sales_90d = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0
    )

    sales_30d_change_percent = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )

    sales_90d_change_percent = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )

    # --------------------------------
    # Snapshot metadata
    # --------------------------------

    calculated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Customer 360"
        verbose_name_plural = "Customers 360"

    def __str__(self):
        return f"360 - {self.customer}"