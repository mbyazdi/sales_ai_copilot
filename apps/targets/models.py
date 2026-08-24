from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from apps.products.models import (
    Category,
    Product,
)
from apps.visits.models import Salesperson


class SalesTarget(models.Model):
    """
    Sales target assigned to one salesperson
    for a defined period and commercial scope.

    Actual value is currently treated as an
    imported/snapshot value.

    QUANTITY can later be calculated from sales
    data when salesperson attribution is reliable.

    MSU must not be auto-calculated until a valid
    product-to-MSU conversion source exists.
    """

    class ScopeType(models.TextChoices):

        PRODUCT = (
            "PRODUCT",
            "Product",
        )

        CATEGORY = (
            "CATEGORY",
            "Category",
        )

        PRODUCT_GROUP = (
            "PRODUCT_GROUP",
            "Product Group",
        )

    class TargetUnit(models.TextChoices):

        QUANTITY = (
            "QUANTITY",
            "Quantity",
        )

        MSU = (
            "MSU",
            "MSU",
        )

    salesperson = models.ForeignKey(
        Salesperson,
        on_delete=models.PROTECT,
        related_name="sales_targets",
    )

    period_start = models.DateField(
        db_index=True,
    )

    period_end = models.DateField(
        db_index=True,
    )

    scope_type = models.CharField(
        max_length=20,
        choices=ScopeType.choices,
        db_index=True,
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="sales_targets",
        null=True,
        blank=True,
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="sales_targets",
        null=True,
        blank=True,
    )

    product_group = models.CharField(
        max_length=30,
        choices=Product.ProductGroup.choices,
        null=True,
        blank=True,
    )

    target_unit = models.CharField(
        max_length=20,
        choices=TargetUnit.choices,
        default=TargetUnit.QUANTITY,
    )

    target_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    actual_value = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
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
            "period_start",
            "salesperson_id",
            "scope_type",
            "id",
        ]

        indexes = [
            models.Index(
                fields=[
                    "salesperson",
                    "period_start",
                    "period_end",
                    "is_active",
                ],
            ),

            models.Index(
                fields=[
                    "scope_type",
                    "is_active",
                ],
            ),
        ]

        constraints = [

            models.CheckConstraint(
                condition=models.Q(
                    target_value__gt=0,
                ),
                name=(
                    "sales_target_value_gt_zero"
                ),
            ),

            models.CheckConstraint(
                condition=models.Q(
                    actual_value__gte=0,
                ),
                name=(
                    "sales_target_actual_gte_zero"
                ),
            ),

            models.CheckConstraint(
                condition=(
                    models.Q(
                        scope_type="PRODUCT",
                        product__isnull=False,
                        category__isnull=True,
                        product_group__isnull=True,
                    )
                    |
                    models.Q(
                        scope_type="CATEGORY",
                        product__isnull=True,
                        category__isnull=False,
                        product_group__isnull=True,
                    )
                    |
                    models.Q(
                        scope_type="PRODUCT_GROUP",
                        product__isnull=True,
                        category__isnull=True,
                        product_group__isnull=False,
                    )
                ),
                name=(
                    "sales_target_valid_scope"
                ),
            ),

            models.UniqueConstraint(
                fields=[
                    "salesperson",
                    "period_start",
                    "period_end",
                    "product",
                    "target_unit",
                ],
                condition=models.Q(
                    scope_type="PRODUCT",
                    is_active=True,
                ),
                name=(
                    "unique_active_product_target"
                ),
            ),

            models.UniqueConstraint(
                fields=[
                    "salesperson",
                    "period_start",
                    "period_end",
                    "category",
                    "target_unit",
                ],
                condition=models.Q(
                    scope_type="CATEGORY",
                    is_active=True,
                ),
                name=(
                    "unique_active_category_target"
                ),
            ),

            models.UniqueConstraint(
                fields=[
                    "salesperson",
                    "period_start",
                    "period_end",
                    "product_group",
                    "target_unit",
                ],
                condition=models.Q(
                    scope_type="PRODUCT_GROUP",
                    is_active=True,
                ),
                name=(
                    "unique_active_product_group_target"
                ),
            ),
        ]

    def clean(self):

        errors = {}

        if (
            self.period_start
            and self.period_end
            and self.period_end
            < self.period_start
        ):
            errors["period_end"] = (
                "Period end cannot be before "
                "period start."
            )

        scope_fields = {
            self.ScopeType.PRODUCT: (
                self.product
                if self.product_id
                else None
            ),

            self.ScopeType.CATEGORY: (
                self.category
                if self.category_id
                else None
            ),

            self.ScopeType.PRODUCT_GROUP: (
                self.product_group
            ),
        }

        selected_scope = (
            scope_fields.get(
                self.scope_type
            )
        )

        if not selected_scope:

            errors["scope_type"] = (
                "The selected scope must have "
                "its matching scope value."
            )

        if (
            self.scope_type
            != self.ScopeType.PRODUCT
            and self.product_id
        ):
            errors["product"] = (
                "Product can only be set for "
                "PRODUCT scope."
            )

        if (
            self.scope_type
            != self.ScopeType.CATEGORY
            and self.category_id
        ):
            errors["category"] = (
                "Category can only be set for "
                "CATEGORY scope."
            )

        if (
            self.scope_type
            != self.ScopeType.PRODUCT_GROUP
            and self.product_group
        ):
            errors["product_group"] = (
                "Product group can only be set "
                "for PRODUCT_GROUP scope."
            )

        if (
            self.target_value is not None
            and self.target_value <= 0
        ):
            errors["target_value"] = (
                "Target value must be greater "
                "than zero."
            )

        if (
            self.actual_value is not None
            and self.actual_value < 0
        ):
            errors["actual_value"] = (
                "Actual value cannot be negative."
            )

        if errors:
            raise ValidationError(
                errors
            )

    @property
    def remaining_value(self):

        remaining = (
            self.target_value
            - self.actual_value
        )

        return max(
            remaining,
            Decimal("0"),
        )

    @property
    def achievement_percent(self):

        if not self.target_value:
            return Decimal("0")

        return (
            self.actual_value
            / self.target_value
            * Decimal("100")
        )

    @property
    def scope_code(self):

        if (
            self.scope_type
            == self.ScopeType.PRODUCT
            and self.product
        ):
            return self.product.product_code

        if (
            self.scope_type
            == self.ScopeType.CATEGORY
            and self.category
        ):
            return self.category.code

        if (
            self.scope_type
            == self.ScopeType.PRODUCT_GROUP
        ):
            return self.product_group

        return ""

    def __str__(self):

        return (
            f"{self.salesperson.employee_code} - "
            f"{self.scope_type} - "
            f"{self.scope_code} - "
            f"{self.period_start} to "
            f"{self.period_end}"
        )