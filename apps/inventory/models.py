from django.db import models

from apps.products.models import Product


class Inventory(models.Model):
    """
    Current inventory status of a product.
    """

    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="inventory"
    )

    available_quantity = models.PositiveIntegerField(
        default=0
    )

    reserved_quantity = models.PositiveIntegerField(
        default=0
    )

    minimum_stock = models.PositiveIntegerField(
        default=0
    )

    last_updated = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Inventory"
        verbose_name_plural = "Inventory"

    @property
    def sellable_quantity(self):
        return max(
            self.available_quantity - self.reserved_quantity,
            0
        )

    def __str__(self):
        return (
            f"{self.product.product_code} - "
            f"{self.sellable_quantity}"
        )