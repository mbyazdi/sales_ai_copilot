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
        "Safely prepare demo assignments and "
        "today's visit plan for SP001."
    )

    SALESPERSON_CODE = "SP001"

    CUSTOMER_CODES = [
        "C0003",
        "C0005",
        "C0013",
        "C0014",
        "C0029",
    ]

    def handle(self, *args, **options):

        today = timezone.localdate()

        salesperson = (
            Salesperson.objects
            .filter(
                employee_code=self.SALESPERSON_CODE,
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

        self.stdout.write(
            f"Preparing Daily Workspace Demo "
            f"for {salesperson.employee_code} "
            f"on {today}..."
        )

        assignments_created = 0
        visits_created = 0
        visits_existing = 0

        for customer_code in self.CUSTOMER_CODES:

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
                        f"customer not found."
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
                        f"it is actively assigned to "
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
                    visit_date=today,
                    defaults={
                        "status":
                            Visit.VisitStatus.PLANNED,

                        "customer_request":
                            "",

                        "customer_feedback":
                            "",

                        "competitor_information":
                            "",

                        "notes":
                            "V2 Daily Workspace Demo visit.",

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

        self.stdout.write(
            self.style.SUCCESS(
                "Daily Workspace Demo seed completed."
            )
        )

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