from django.core.management.base import BaseCommand, CommandError

from apps.customers.models import Customer
from apps.recommendations.engine import RecommendationEngine


class Command(BaseCommand):

    help = "Generate product recommendations for customers."

    def add_arguments(self, parser):

        parser.add_argument(
            "--customer",
            type=str,
            help="Customer code to process.",
        )

    def handle(self, *args, **options):

        customer_code = options.get("customer")

        # ==================================================
        # Process one customer
        # ==================================================

        if customer_code:

            try:

                customer = Customer.objects.select_related(
                    "grade",
                    "customer_360",
                ).get(
                    customer_code=customer_code,
                    is_active=True,
                )

            except Customer.DoesNotExist:

                raise CommandError(
                    f"Customer '{customer_code}' "
                    "does not exist or is inactive."
                )

            self.stdout.write(
                f"Generating recommendations for "
                f"{customer_code}..."
            )

            engine = RecommendationEngine(customer)

            recommendations = engine.generate()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Generated {len(recommendations)} "
                    f"recommendations for {customer_code}."
                )
            )

            for recommendation in recommendations:

                self.stdout.write(
                    f"{recommendation.rank}. "
                    f"{recommendation.product.product_code} | "
                    f"{recommendation.product.name} | "
                    f"Score: {recommendation.score}"
                )

            return

        # ==================================================
        # Process all active customers
        # ==================================================

        self.stdout.write(
            "Generating recommendations for "
            "all active customers..."
        )

        customers = Customer.objects.filter(
            is_active=True,
        ).select_related(
            "grade",
            "customer_360",
        )

        total_customers = 0
        total_recommendations = 0

        for customer in customers:

            engine = RecommendationEngine(customer)

            recommendations = engine.generate()

            total_customers += 1
            total_recommendations += len(
                recommendations
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {total_customers} customers. "
                f"Generated {total_recommendations} "
                f"recommendations."
            )
        )