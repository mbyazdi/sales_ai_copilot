from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.visits.models import (
    FollowUpTask,
    SalesOutcome,
    Salesperson,
    Visit,
    VisitCommercialSnapshot,
    VisitCustomerSnapshot,
)


class Command(BaseCommand):

    help = (
        "Safely reset today's Daily Workspace Demo "
        "for SP001 to a repeatable baseline."
    )

    SALESPERSON_CODE = "SP001"

    CUSTOMER_CODES = [
        "C0003",
        "C0005",
        "C0013",
        "C0014",
        "C0029",
    ]

    DEMO_VISIT_NOTES = (
        "V2 Daily Workspace Demo visit."
    )

    @transaction.atomic
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

        visits = (
            Visit.objects
            .filter(
                salesperson=salesperson,
                customer__customer_code__in=(
                    self.CUSTOMER_CODES
                ),
                visit_date=today,
            )
            .select_related(
                "customer",
            )
            .order_by(
                "customer__customer_code",
                "id",
            )
        )

        visit_ids = list(
            visits.values_list(
                "id",
                flat=True,
            )
        )

        self.stdout.write(
            f"Resetting Daily Workspace Demo "
            f"for {salesperson.employee_code} "
            f"on {today}..."
        )

        if not visit_ids:
            self.stderr.write(
                self.style.WARNING(
                    "No demo visits were found. "
                    "Run seed_daily_workspace_demo first."
                )
            )
            return

        sales_outcomes_deleted, _ = (
            SalesOutcome.objects
            .filter(
                visit_id__in=visit_ids,
            )
            .delete()
        )

        follow_up_tasks_deleted, _ = (
            FollowUpTask.objects
            .filter(
                visit_id__in=visit_ids,
            )
            .delete()
        )

        customer_snapshots_deleted, _ = (
            VisitCustomerSnapshot.objects
            .filter(
                visit_id__in=visit_ids,
            )
            .delete()
        )

        commercial_snapshots_deleted, _ = (
            VisitCommercialSnapshot.objects
            .filter(
                visit_id__in=visit_ids,
            )
            .delete()
        )

        visits_reset = (
            Visit.objects
            .filter(
                id__in=visit_ids,
            )
            .update(
                status=Visit.VisitStatus.PLANNED,
                customer_request="",
                customer_feedback="",
                competitor_information="",
                notes=self.DEMO_VISIT_NOTES,
                order_created=False,
                order_amount=0,
                follow_up_required=False,
                follow_up_date=None,
            )
        )

        self.stdout.write("")

        for visit in (
            Visit.objects
            .filter(
                id__in=visit_ids,
            )
            .select_related(
                "customer",
            )
            .order_by(
                "customer__customer_code",
                "id",
            )
        ):
            self.stdout.write(
                "  "
                f"Visit {visit.id} "
                f"| {visit.customer.customer_code} "
                f"| {visit.status}"
            )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "Daily Workspace Demo reset completed."
            )
        )

        self.stdout.write(
            f"Visits reset: "
            f"{visits_reset}"
        )

        self.stdout.write(
            f"Sales outcomes deleted: "
            f"{sales_outcomes_deleted}"
        )

        self.stdout.write(
            f"Follow-up tasks deleted: "
            f"{follow_up_tasks_deleted}"
        )

        self.stdout.write(
            f"Customer snapshots deleted: "
            f"{customer_snapshots_deleted}"
        )

        self.stdout.write(
            f"Commercial snapshots deleted: "
            f"{commercial_snapshots_deleted}"
        )
