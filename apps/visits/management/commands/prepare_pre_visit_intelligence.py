from datetime import timedelta

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.utils import timezone

from apps.visits.models import Salesperson
from apps.visits.services import (
    build_pre_visit_intelligence_window,
)


class Command(BaseCommand):

    help = (
        "Build canonical pre-visit intelligence "
        "for upcoming salesperson visits."
    )

    def add_arguments(
        self,
        parser,
    ):

        parser.add_argument(
            "--salesperson",
            type=str,
            default=None,
            help=(
                "Optional salesperson employee code. "
                "If omitted, all active salespersons "
                "are processed."
            ),
        )

        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help=(
                "Number of days from today to include. "
                "Default: 1."
            ),
        )

        parser.add_argument(
            "--include-today",
            action="store_true",
            help=(
                "Include today's visits in the window."
            ),
        )

    def handle(
        self,
        *args,
        **options,
    ):

        days = options["days"]

        if days < 1:

            raise CommandError(
                "--days must be at least 1."
            )

        today = timezone.localdate()

        if options["include_today"]:

            start_date = today

            end_date = (
                today
                + timedelta(
                    days=days - 1
                )
            )

        else:

            start_date = (
                today
                + timedelta(days=1)
            )

            end_date = (
                today
                + timedelta(days=days)
            )

        salesperson_code = (
            options.get(
                "salesperson"
            )
        )

        salespersons = (
            Salesperson.objects
            .filter(
                is_active=True,
            )
            .order_by(
                "employee_code"
            )
        )

        if salesperson_code:

            salespersons = (
                salespersons.filter(
                    employee_code=(
                        salesperson_code
                    ),
                )
            )

            if not salespersons.exists():

                raise CommandError(
                    "Active salesperson "
                    f"{salesperson_code} "
                    "was not found."
                )

        self.stdout.write(
            ""
        )

        self.stdout.write(
            "=" * 100
        )

        self.stdout.write(
            "PRE-VISIT INTELLIGENCE PREPARATION"
        )

        self.stdout.write(
            "=" * 100
        )

        self.stdout.write(
            f"WINDOW: "
            f"{start_date} -> {end_date}"
        )

        self.stdout.write(
            ""
        )

        total_visits = 0

        total_salespersons = 0

        for salesperson in salespersons:

            result = (
                build_pre_visit_intelligence_window(
                    salesperson=(
                        salesperson
                    ),
                    start_date=(
                        start_date
                    ),
                    end_date=(
                        end_date
                    ),
                )
            )

            visit_count = (
                result[
                    "visit_count"
                ]
            )

            total_visits += (
                visit_count
            )

            total_salespersons += 1

            self.stdout.write(
                "-" * 100
            )

            self.stdout.write(
                f"{salesperson.employee_code} "
                f"| {salesperson.full_name} "
                f"| VISITS: {visit_count}"
            )

            for item in (
                result[
                    "items"
                ]
            ):

                visit = (
                    item[
                        "visit"
                    ]
                )

                customer = (
                    item[
                        "customer"
                    ]
                    or {}
                )

                primary = (
                    item[
                        "primary_recommendation"
                    ]
                    or {}
                )

                decision = (
                    item[
                        "commercial_decision"
                    ]
                    or {}
                )

                self.stdout.write(
                    "  "
                    f"{visit['visit_date']} "
                    f"| Visit {visit['id']} "
                    f"| {customer.get('customer_code')} "
                    f"| {primary.get('product_code')} "
                    f"| Commercial "
                    f"{decision.get('commercial_priority')} "
                    f"{decision.get('commercial_score')}"
                )

        self.stdout.write(
            ""
        )

        self.stdout.write(
            "=" * 100
        )

        self.stdout.write(
            "SUMMARY"
        )

        self.stdout.write(
            "=" * 100
        )

        self.stdout.write(
            f"SALESPERSONS PROCESSED: "
            f"{total_salespersons}"
        )

        self.stdout.write(
            f"VISITS PREPARED: "
            f"{total_visits}"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Pre-visit intelligence "
                "preparation completed."
            )
        )