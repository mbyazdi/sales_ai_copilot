from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.customers.models import Customer
from apps.visits.models import (
    CustomerAssignment,
    Salesperson,
    Visit,
)


class Command(BaseCommand):

    help = (
        "Safely create future demo visits for "
        "pre-visit intelligence validation."
    )

    SALESPERSON_CODE = "SP001"

    CUSTOMER_CODES = [
        "C0003",
        "C0005",
        "C0014",
    ]

    def handle(
        self,
        *args,
        **options,
    ):

        today = timezone.localdate()

        visit_date = (
            today
            + timedelta(days=1)
        )

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

        self.stdout.write("")
        self.stdout.write("=" * 100)

        self.stdout.write(
            "PRE-VISIT INTELLIGENCE DEMO SEED"
        )

        self.stdout.write("=" * 100)

        self.stdout.write(
            f"SALESPERSON: "
            f"{salesperson.employee_code} "
            f"{salesperson.full_name}"
        )

        self.stdout.write(
            f"VISIT DATE: {visit_date}"
        )

        self.stdout.write("")

        assignments_created = 0
        visits_created = 0
        visits_existing = 0

        for customer_code in (
            self.CUSTOMER_CODES
        ):

            customer = (
                Customer.objects
                .filter(
                    customer_code=customer_code,
                    is_active=True,
                )
                .first()
            )

            if customer is None:

                self.stderr.write(
                    self.style.WARNING(
                        f"{customer_code}: "
                        "customer not found."
                    )
                )

                continue

            conflicting_assignment = (
                CustomerAssignment.objects
                .filter(
                    customer=customer,
                    is_active=True,
                )
                .exclude(
                    salesperson=salesperson,
                )
                .first()
            )

            if conflicting_assignment:

                self.stderr.write(
                    self.style.WARNING(
                        f"{customer_code}: skipped because "
                        "it is actively assigned to "
                        f"{conflicting_assignment.salesperson.employee_code}."
                    )
                )

                continue

            assignment, assignment_created = (
                CustomerAssignment.objects
                .get_or_create(
                    salesperson=salesperson,
                    customer=customer,
                    is_active=True,
                    defaults={
                        "start_date": today,
                        "end_date": None,
                    },
                )
            )

            if assignment_created:
                assignments_created += 1

            visit, visit_created = (
                Visit.objects
                .get_or_create(
                    salesperson=salesperson,
                    customer=customer,
                    visit_date=visit_date,
                    defaults={
                        "status":
                            Visit.VisitStatus.PLANNED,

                        "customer_request":
                            "",

                        "customer_feedback":
                            "",

                        "competitor_information":
                            "",

                        "notes": (
                            "V2 Pre-Visit Intelligence "
                            "Demo visit."
                        ),

                        "order_created":
                            False,

                        "order_amount":
                            0,

                        "follow_up_required":
                            False,

                        "follow_up_date":
                            None,
                    },
                )
            )

            if visit_created:

                visits_created += 1

            else:

                visits_existing += 1

            self.stdout.write(
                "  "
                f"{customer.customer_code} "
                f"| assignment="
                f"{'created' if assignment_created else 'existing'} "
                f"| visit="
                f"{'created' if visit_created else 'existing'}"
            )

        self.stdout.write("")
        self.stdout.write("=" * 100)
        self.stdout.write("SUMMARY")
        self.stdout.write("=" * 100)

        self.stdout.write(
            f"Assignments created: "
            f"{assignments_created}"
        )

        self.stdout.write(
            f"Visits created: "
            f"{visits_created}"
        )

        self.stdout.write(
            f"Visits already existing: "
            f"{visits_existing}"
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Pre-visit intelligence "
                "demo seed completed."
            )
        )