from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.customers.models import CustomerGrade
from apps.inventory.models import Inventory
from apps.products.models import Product
from apps.promotions.models import (
    Promotion,
    PromotionProduct,
)


class Command(BaseCommand):

    help = (
        "Safely create or update commercial "
        "context demo data."
    )

    START_DATE = date(2026, 8, 1)
    END_DATE = date(2026, 9, 30)

    def handle(
        self,
        *args,
        **options,
    ):

        products = {
            code: Product.objects.get(
                product_code=code
            )
            for code in [
                "PHI002",
                "PHI004",
                "PHS001",
                "TEF003",
            ]
        }

        # ==========================================
        # INVENTORY
        # ==========================================

        inventory_data = {
            "PHI002": {
                "available_quantity": 180,
                "reserved_quantity": 30,
                "minimum_stock": 40,
            },

            "PHI004": {
                "available_quantity": 90,
                "reserved_quantity": 20,
                "minimum_stock": 25,
            },

            "PHS001": {
                "available_quantity": 24,
                "reserved_quantity": 8,
                "minimum_stock": 20,
            },

            "TEF003": {
                "available_quantity": 140,
                "reserved_quantity": 20,
                "minimum_stock": 30,
            },
        }

        self.stdout.write(
            "Inventory:"
        )

        for code, values in inventory_data.items():

            inventory, created = (
                Inventory.objects.update_or_create(
                    product=products[code],
                    defaults=values,
                )
            )

            state = (
                "created"
                if created
                else "updated"
            )

            self.stdout.write(
                "  "
                f"{code} | {state} "
                f"| sellable="
                f"{inventory.sellable_quantity}"
            )

        # ==========================================
        # PROMOTION 1 — PHI002
        # ==========================================

        promo_phi002, _ = (
            Promotion.objects.update_or_create(
                code="DEMO-PHI002-10",
                defaults={
                    "name": (
                        "Electric Toothbrush "
                        "Growth Offer"
                    ),

                    "promotion_type": (
                        Promotion
                        .PromotionType
                        .PERCENTAGE
                    ),

                    "start_date":
                        self.START_DATE,

                    "end_date":
                        self.END_DATE,

                    "discount_percent":
                        Decimal("10"),

                    "discount_amount":
                        None,

                    "minimum_quantity":
                        2,

                    "maximum_quantity":
                        None,

                    "description": (
                        "10 percent discount "
                        "for eligible customers."
                    ),

                    "is_active":
                        True,
                },
            )
        )

        PromotionProduct.objects.update_or_create(
            promotion=promo_phi002,
            product=products["PHI002"],
            defaults={
                "priority": 2,
            },
        )

        grades_bc = (
            CustomerGrade.objects
            .filter(
                code__in=[
                    "B",
                    "C",
                ]
            )
        )

        promo_phi002.customer_grades.set(
            grades_bc
        )

        # ==========================================
        # PROMOTION 2 — PHI004
        # ==========================================

        promo_phi004, _ = (
            Promotion.objects.update_or_create(
                code="DEMO-PHI004-07",
                defaults={
                    "name": (
                        "Blender Volume Offer"
                    ),

                    "promotion_type": (
                        Promotion
                        .PromotionType
                        .PERCENTAGE
                    ),

                    "start_date":
                        self.START_DATE,

                    "end_date":
                        self.END_DATE,

                    "discount_percent":
                        Decimal("7"),

                    "discount_amount":
                        None,

                    "minimum_quantity":
                        2,

                    "maximum_quantity":
                        None,

                    "description": (
                        "7 percent discount "
                        "on Philips Blender."
                    ),

                    "is_active":
                        True,
                },
            )
        )

        PromotionProduct.objects.update_or_create(
            promotion=promo_phi004,
            product=products["PHI004"],
            defaults={
                "priority": 1,
            },
        )

        grades_abc = (
            CustomerGrade.objects
            .filter(
                code__in=[
                    "A",
                    "B",
                    "C",
                ]
            )
        )

        promo_phi004.customer_grades.set(
            grades_abc
        )

        # ==========================================
        # PROMOTION 3 — TEF003
        # ==========================================

        promo_tef003, _ = (
            Promotion.objects.update_or_create(
                code="DEMO-TEF003-BXGY",
                defaults={
                    "name": (
                        "Tefal Blender "
                        "Buy X Get Y"
                    ),

                    "promotion_type": (
                        Promotion
                        .PromotionType
                        .BUY_X_GET_Y
                    ),

                    "start_date":
                        self.START_DATE,

                    "end_date":
                        self.END_DATE,

                    "discount_percent":
                        None,

                    "discount_amount":
                        None,

                    "minimum_quantity":
                        12,

                    "maximum_quantity":
                        None,

                    "description": (
                        "Buy 12 units and "
                        "receive 1 bonus unit."
                    ),

                    "is_active":
                        True,
                },
            )
        )

        PromotionProduct.objects.update_or_create(
            promotion=promo_tef003,
            product=products["TEF003"],
            defaults={
                "priority": 2,
            },
        )

        promo_tef003.customer_grades.clear()

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Commercial Context Demo "
                "seed completed."
            )
        )