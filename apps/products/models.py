from django.db import models


class Brand(models.Model):
    """
    Product brand.
    """

    name = models.CharField(
        max_length=150,
        unique=True
    )

    code = models.CharField(
        max_length=50,
        unique=True
    )

    description = models.TextField(
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
        return self.name


class Category(models.Model):
    """
    Product category.

    Supports hierarchical categories.

    Examples:

        Beauty & Personal Care
            Hair Care
                Shampoo
                Conditioner
                Hair Mask

        Personal Electrical
            Hair Styling
                Hair Dryer
                Hair Straightener

        Home Appliances
            Floor Care
                Vacuum Cleaner
    """

    name = models.CharField(
        max_length=150
    )

    code = models.CharField(
        max_length=50,
        unique=True
    )

    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="subcategories",
        null=True,
        blank=True
    )

    description = models.TextField(
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
        verbose_name = "Category"
        verbose_name_plural = "Categories"

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} / {self.name}"

        return self.name


class Product(models.Model):
    """
    Product master data.

    The company sells:
        - Beauty & Personal Care
        - Personal Electrical
        - Home Appliances
    """

    class ProductGroup(models.TextChoices):
        BEAUTY = (
            "BEAUTY",
            "Beauty & Personal Care"
        )

        PERSONAL_ELECTRICAL = (
            "PERSONAL_ELECTRICAL",
            "Personal Electrical"
        )

        HOME_APPLIANCE = (
            "HOME_APPLIANCE",
            "Home Appliance"
        )

        OTHER = (
            "OTHER",
            "Other"
        )

    product_code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True
    )

    name = models.CharField(
        max_length=250
    )

    brand = models.ForeignKey(
        Brand,
        on_delete=models.PROTECT,
        related_name="products"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products"
    )

    product_group = models.CharField(
        max_length=30,
        choices=ProductGroup.choices,
        default=ProductGroup.BEAUTY,
        db_index=True
    )

    description = models.TextField(
        blank=True
    )

    unit = models.CharField(
        max_length=30,
        default="PCS"
    )

    package_size = models.CharField(
        max_length=100,
        blank=True
    )

    # --------------------------------
    # Product behavior
    # --------------------------------

    is_consumable = models.BooleanField(
        default=True
    )

    is_durable = models.BooleanField(
        default=False
    )

    repurchase_cycle_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Expected number of days before "
            "the customer typically repurchases this product."
        )
    )

    # --------------------------------
    # Status
    # --------------------------------

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
        return f"{self.product_code} - {self.name}"