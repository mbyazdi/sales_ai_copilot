from django.core.management.base import BaseCommand, CommandError

from apps.customers.models import Customer
from apps.customers.services import (
    build_all_customer_360,
    build_customer_360,
)


class Command(BaseCommand):

    help = "Build or refresh Customer 360."

    def add_arguments(self, parser):

        parser.add_argument(
            "--customer",
            type=str,
            help="Customer code to process.",
        )

    def handle(self, *args, **options):

        customer_code = options.get("customer")

        # -----------------------------------------
        # Process one customer
        # -----------------------------------------

        if customer_code:

            try:
                customer = Customer.objects.get(
                    customer_code=customer_code,
                    is_active=True,
                )

            except Customer.DoesNotExist:

                raise CommandError(
                    f"Customer '{customer_code}' "
                    "does not exist."
                )

            self.stdout.write(
                f"Building Customer 360 for "
                f"{customer_code}..."
            )

            build_customer_360(customer)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Customer 360 successfully built "
                    f"for {customer_code}."
                )
            )

            return

        # -----------------------------------------
        # Process all customers
        # -----------------------------------------

        self.stdout.write(
            "Building Customer 360 for "
            "all active customers..."
        )

        count = build_all_customer_360()

        self.stdout.write(
            self.style.SUCCESS(
                f"Customer 360 successfully built "
                f"for {count} customers."
            )
        )