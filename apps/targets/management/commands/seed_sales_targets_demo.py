from datetime import date
from decimal import Decimal

from django.core.management.base import (
    BaseCommand,
)

from apps.products.models import (
    Category,
    Product,
)

from apps.targets.models import (
    SalesTarget,
)

from apps.visits.models import (
    Salesperson,
)


class Command(BaseCommand):

    help = (
        "Safely create or update Sales Target "
        "demo data for SP001."
    )

    SALESPERSON_CODE = "SP001"

    PERIOD_START = date(
        2026,
        8,
        1,
    )

    PERIOD_END = date(
        2026,
        8,
        31,
    )

    def handle(
        self,
        *args,
        **options,
    ):

        salesperson = (
            Salesperson.objects
            .filter(
                employee_code=(
                    self.SALESPERSON_CODE
                ),
                is_active=True,
            )
            .first()
        )

        if salesperson is None:

            self.stderr.write(
                self.style.ERROR(
                    "Active salesperson SP001 "
                    "was not found."
                )
            )

            return

        product = Product.objects.get(
            product_code="PHI002",
        )

        blender_category = (
            Category.objects.get(
                code="BLENDER",
            )
        )

        targets = [
            {
                "scope_type": (
                    SalesTarget
                    .ScopeType
                    .PRODUCT_GROUP
                ),

                "product_group": (
                    Product
                    .ProductGroup
                    .PERSONAL_ELECTRICAL
                ),

                "target_value":
                    Decimal("1000"),

                "actual_value":
                    Decimal("720"),
            },

            {
                "scope_type": (
                    SalesTarget
                    .ScopeType
                    .PRODUCT_GROUP
                ),

                "product_group": (
                    Product
                    .ProductGroup
                    .HOME_APPLIANCE
                ),

                "target_value":
                    Decimal("800"),

                "actual_value":
                    Decimal("440"),
            },

            {
                "scope_type": (
                    SalesTarget
                    .ScopeType
                    .PRODUCT
                ),

                "product":
                    product,

                "target_value":
                    Decimal("500"),

                "actual_value":
                    Decimal("410"),
            },

            {
                "scope_type": (
                    SalesTarget
                    .ScopeType
                    .CATEGORY
                ),

                "category":
                    blender_category,

                "target_value":
                    Decimal("300"),

                "actual_value":
                    Decimal("165"),
            },
        ]

        created_count = 0
        updated_count = 0

        for data in targets:

            scope_type = data[
                "scope_type"
            ]

            lookup = {
                "salesperson":
                    salesperson,

                "period_start":
                    self.PERIOD_START,

                "period_end":
                    self.PERIOD_END,

                "scope_type":
                    scope_type,

                "target_unit": (
                    SalesTarget
                    .TargetUnit
                    .QUANTITY
                ),

                "is_active":
                    True,
            }

            if (
                scope_type
                == SalesTarget
                .ScopeType
                .PRODUCT
            ):
                lookup[
                    "product"
                ] = data["product"]

            elif (
                scope_type
                == SalesTarget
                .ScopeType
                .CATEGORY
            ):
                lookup[
                    "category"
                ] = data["category"]

            elif (
                scope_type
                == SalesTarget
                .ScopeType
                .PRODUCT_GROUP
            ):
                lookup[
                    "product_group"
                ] = data[
                    "product_group"
                ]

            target, created = (
                SalesTarget.objects
                .update_or_create(
                    **lookup,
                    defaults={
                        "target_value":
                            data[
                                "target_value"
                            ],

                        "actual_value":
                            data[
                                "actual_value"
                            ],
                    },
                )
            )

            target.full_clean()

            if created:
                created_count += 1

                state = "created"
            else:
                updated_count += 1

                state = "updated"

            self.stdout.write(
                "  "
                f"{target.scope_type} "
                f"| {target.scope_code} "
                f"| {state} "
                f"| achievement="
                f"{target.achievement_percent:.2f}%"
            )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Sales Target Demo seed completed."
            )
        )

        self.stdout.write(
            f"Created: {created_count}"
        )

        self.stdout.write(
            f"Updated: {updated_count}"
        )