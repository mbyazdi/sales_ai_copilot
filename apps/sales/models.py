from decimal import Decimal

from django.db import models


class Sale(models.Model):
    """
    Represents one customer sales transaction/order.
    """

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="sales",
    )

    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
    )

    sale_date = models.DateField(
        db_index=True,
    )

    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
    )

    description = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-sale_date", "-id"]

    def __str__(self):
        return (
            f"{self.invoice_number} - "
            f"{self.customer.customer_code}"
        )


class SaleItem(models.Model):
    """
    Individual product line within a sale.
    """

    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="sale_items",
    )

    quantity = models.PositiveIntegerField(
        default=1,
    )

    unit_price = models.DecimalField(
        max_digits=18,
        decimal_places=2,
    )

    discount_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
    )

    total_amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0"),
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    def calculate_total(self):
        """
        Calculate final line amount.
        """

        gross_amount = (
            Decimal(self.quantity)
            * self.unit_price
        )

        return gross_amount - self.discount_amount

    def save(self, *args, **kwargs):

        self.total_amount = self.calculate_total()

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.sale.invoice_number} - "
            f"{self.product.product_code} - "
            f"{self.quantity}"
        )