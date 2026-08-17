from collections import defaultdict
from itertools import combinations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.sales.models import SaleItem
from apps.recommendations.models import ProductAssociation


class Command(BaseCommand):

    help = "Build customer-level product-to-product purchase associations"

    def handle(self, *args, **options):

        self.stdout.write(
            "Building product associations..."
        )

        # =====================================================
        # 1. Build product sets per customer
        # =====================================================

        customer_products = defaultdict(set)

        rows = (
            SaleItem.objects
            .values(
                "sale__customer_id",
                "product_id",
            )
            .distinct()
            .iterator()
        )

        for row in rows:

            customer_products[
                row["sale__customer_id"]
            ].add(
                row["product_id"]
            )

        total_customers = len(customer_products)

        if total_customers == 0:

            self.stdout.write(
                self.style.WARNING(
                    "No sales data found."
                )
            )

            return

        self.stdout.write(
            f"Customers with purchases: "
            f"{total_customers}"
        )

        # =====================================================
        # 2. Count product customer frequency
        # =====================================================

        product_customer_count = defaultdict(int)

        for products in customer_products.values():

            for product_id in products:

                product_customer_count[
                    product_id
                ] += 1

        # =====================================================
        # 3. Count product pairs
        # =====================================================

        pair_count = defaultdict(int)

        for products in customer_products.values():

            products = sorted(products)

            if len(products) < 2:
                continue

            for product_a, product_b in combinations(
                products,
                2,
            ):

                pair_count[
                    (product_a, product_b)
                ] += 1

        self.stdout.write(
            f"Product pairs found: "
            f"{len(pair_count)}"
        )

        # =====================================================
        # 4. Create directional associations
        # =====================================================

        associations = []

        for (
            (product_a, product_b),
            occurrence,
        ) in pair_count.items():

            count_a = product_customer_count[
                product_a
            ]

            count_b = product_customer_count[
                product_b
            ]

            if count_a == 0 or count_b == 0:
                continue

            # -------------------------------------------------
            # Support
            # -------------------------------------------------

            support = (
                occurrence
                / total_customers
            )

            # -------------------------------------------------
            # Confidence A -> B
            # -------------------------------------------------

            confidence_a_b = (
                occurrence
                / count_a
            )

            # -------------------------------------------------
            # Confidence B -> A
            # -------------------------------------------------

            confidence_b_a = (
                occurrence
                / count_b
            )

            # -------------------------------------------------
            # Product probabilities
            # -------------------------------------------------

            probability_a = (
                count_a
                / total_customers
            )

            probability_b = (
                count_b
                / total_customers
            )

            # -------------------------------------------------
            # Lift
            # -------------------------------------------------

            lift_a_b = (
                confidence_a_b
                / probability_b
                if probability_b > 0
                else 0
            )

            lift_b_a = (
                confidence_b_a
                / probability_a
                if probability_a > 0
                else 0
            )

            # -------------------------------------------------
            # A -> B
            # -------------------------------------------------

            associations.append(
                ProductAssociation(
                    product_id=product_a,
                    associated_product_id=product_b,
                    occurrence_count=occurrence,
                    support=support,
                    confidence=confidence_a_b,
                    lift=lift_a_b,
                    is_active=True,
                )
            )

            # -------------------------------------------------
            # B -> A
            # -------------------------------------------------

            associations.append(
                ProductAssociation(
                    product_id=product_b,
                    associated_product_id=product_a,
                    occurrence_count=occurrence,
                    support=support,
                    confidence=confidence_b_a,
                    lift=lift_b_a,
                    is_active=True,
                )
            )

        # =====================================================
        # 5. Save
        # =====================================================

        with transaction.atomic():

            ProductAssociation.objects.all().delete()

            ProductAssociation.objects.bulk_create(
                associations,
                batch_size=1000,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created "
                f"{len(associations)} "
                f"product associations."
            )
        )