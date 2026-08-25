from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.services import (
    generate_sales_copilot_response,
)
from apps.customers.models import Customer
from apps.customers.services import (
    build_sales_ai_context,
    get_customer_360,
)
from apps.recommendations.models import (
    CustomerRecommendation,
)
from apps.visits.models import Visit
from apps.core.commercial_decision import (
    build_base_sales_session,
)
from apps.targets.services import (
    get_salesperson_target_progress,
)

from apps.visits.services import (
    build_customer_outcome_history,
    build_pre_visit_briefs,
)

class SalesCopilotAPIView(APIView):

    def post(self, request):

        # =========================================
        # INPUT
        # =========================================

        customer_code = (
            request.data.get("customer_code", "")
            .strip()
        )

        visit_id = request.data.get(
            "visit_id"
        )

        message = (
            request.data.get("message", "")
            .strip()
        )

        # =========================================
        # VALIDATION
        # =========================================

        if not customer_code:

            return Response(
                {
                    "detail": (
                        "customer_code is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not message:

            return Response(
                {
                    "detail": (
                        "message is required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # =========================================
        # CUSTOMER
        # =========================================

        try:

            customer = (
                Customer.objects
                .select_related(
                    "grade",
                    "customer_360",
                )
                .get(
                    customer_code=customer_code,
                    is_active=True,
                )
            )

        except Customer.DoesNotExist:

            return Response(
                {
                    "detail": (
                        "Customer not found."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        customer_360 = getattr(
            customer,
            "customer_360",
            None,
        )

        if customer_360 is None:

            return Response(
                {
                    "detail": (
                        "Customer 360 snapshot "
                        "not found."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # =========================================
        # CURRENT VISIT
        # =========================================

        current_visit = None

        if visit_id:

            try:

                current_visit = (
                    Visit.objects
                    .select_related(
                        "salesperson",
                        "customer",
                    )
                    .get(
                        id=visit_id,
                        customer=customer,
                    )
                )

            except Visit.DoesNotExist:

                return Response(
                    {
                        "detail": (
                            "Visit not found "
                            "for this customer."
                        )
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

        # =========================================
        # RECOMMENDATIONS
        # =========================================

        recommendations = list(
            CustomerRecommendation.objects
            .filter(
                customer=customer,
                is_active=True,
            )
            .select_related(
                "product",
                "product__category",
            )
            .order_by(
                "rank"
            )
        )

        primary = (
            recommendations[0]
            if recommendations
            else None
        )

        # =========================================
        # SALES SESSION
        # =========================================

        target_relevance = []
        commercial_context = None

        # -----------------------------------------
        # VISIT-SCOPED COMMERCIAL CONTEXT
        # -----------------------------------------

        if current_visit:

            target_progress = (
                get_salesperson_target_progress(
                    salesperson=(
                        current_visit.salesperson
                    ),
                    as_of_date=(
                        current_visit.visit_date
                    ),
                )
            )

            visit_briefs = (
                build_pre_visit_briefs(
                    visits=[
                        current_visit,
                    ],
                    salesperson=(
                        current_visit.salesperson
                    ),
                    target_progress=(
                        target_progress
                    ),
                )
            )

            current_brief = (
                visit_briefs.get(
                    current_visit.id,
                    {},
                )
            )

            target_relevance = (
                current_brief.get(
                    "target_relevance",
                    [],
                )
            )

            commercial_context = (
                current_brief.get(
                    "commercial_context"
                )
            )

        # -----------------------------------------
        # CANONICAL SALES SESSION
        # -----------------------------------------

        sales_session = (
            build_base_sales_session(
                customer=customer,
                customer_360=customer_360,
                primary_recommendation=primary,
                target_relevance=(
                    target_relevance
                ),
                commercial_context=(
                    commercial_context
                ),
            )
        )

        outcome_history = (
            build_customer_outcome_history(
                customer=customer,
                limit=10,
            )
        )

        # =========================================
        # AI CONTEXT
        # =========================================

        sales_ai_context = (
            build_sales_ai_context(
                customer=customer,
                customer_360=customer_360,
                current_visit=current_visit,
                sales_session=sales_session,
                recommendations=recommendations,
                outcome_history=(
                    outcome_history
                ),
            )
        )

        # =========================================
        # OLLAMA
        # =========================================

        try:

            ai_result = (
                generate_sales_copilot_response(
                    sales_ai_context=
                        sales_ai_context,
                    user_message=message,
                )
            )

        except Exception as exc:

            return Response(
                {
                    "detail": (
                        "Sales AI Copilot "
                        "is currently unavailable."
                    ),
                    "error": str(exc),
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # =========================================
        # RESPONSE
        # =========================================

        return Response(
            {
                "success": True,

                "customer_code":
                    customer.customer_code,

                "visit_id": (
                    current_visit.id
                    if current_visit
                    else None
                ),

                "model":
                    ai_result.get("model"),

                "response":
                    ai_result.get("response"),

                "done":
                    ai_result.get("done", True),
            },
            status=status.HTTP_200_OK,
        )