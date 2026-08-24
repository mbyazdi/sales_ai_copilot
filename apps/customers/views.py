from django.shortcuts import get_object_or_404, render

from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from .models import Customer
from .services import (
    get_customer_360,
    build_sales_ai_context,
)
from apps.recommendations.models import CustomerRecommendation
from apps.visits.models import (
    CustomerAssignment,
    Visit,
    FollowUpTask,
)
from apps.sales.services import get_customer_sales_history

from apps.visits.services import (
    build_pre_visit_briefs,
    resolve_recommendation_outcome,
)

from apps.targets.services import (
    get_salesperson_target_progress,
)
from apps.core.commercial_decision import (
    build_base_sales_session,
)

def customer_search(request):

    customer_code = request.GET.get(
        "customer_code",
        ""
    ).strip()
        
    visit_id = request.GET.get(
        "visit_id",
        ""
    ).strip()

    context = {
        "customer_code": customer_code,
        "visit_id": visit_id,

        "customer": None,
        "customer_360": None,

        "recommendations": [],

        "sales_session": None,

        "commercial_decision": None,

        "assignment": None,

        "latest_visit": None,

        "current_visit": None,

        "sales_outcome": None,

        "sales_history": None,

        "not_found": False,

        "sales_ai_context": None,

        "current_follow_up_task": None,

        "current_follow_up_time_state": None,
    }

    if customer_code:

        try:

            result = get_customer_360(
                customer_code
            )

            customer = result["customer"]
            customer_360 = result["customer_360"]

            context["customer"] = customer
            context["customer_360"] = customer_360

            # -----------------------------------------
            # CURRENT VISIT CONTEXT
            # -----------------------------------------

            if visit_id:

                try:

                    current_visit_id = int(
                        visit_id
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    current_visit_id = None


                if current_visit_id:

                    current_visit = (
                        Visit.objects
                        .filter(
                            id=current_visit_id,
                            customer=customer,
                        )
                        .select_related(
                            "salesperson",
                        )
                        .first()
                    )

                    if current_visit:

                        context["current_visit"] = (
                            current_visit
                        )

                    else:

                        context["visit_not_found"] = True

            context["assignment"] = result.get(
                "assignment"
            )

            context["latest_visit"] = result.get(
                "latest_visit"
            )
            sales_history = get_customer_sales_history(
                customer_code=customer_code,
            )

            context["sales_history"] = {
                "summary": sales_history["summary"],
                "sales": sales_history["sales"],
            }
            
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
                .order_by("rank")
            )

            context["recommendations"] = recommendations

            # -----------------------------------------
            # SALES SESSION
            # -----------------------------------------

            primary_recommendation = (
                recommendations[0]
                if recommendations
                else None
            )

            if customer_360:

                current_visit = context.get(
                    "current_visit"
                )

                target_relevance = []
                commercial_context = None

                # -------------------------------------
                # VISIT-SCOPED COMMERCIAL DECISION
                # -------------------------------------

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

                    context[
                        "commercial_decision"
                    ] = (
                        current_brief.get(
                            "commercial_decision"
                        )
                    )

                # -------------------------------------
                # CANONICAL SALES SESSION
                # -------------------------------------

                context["sales_session"] = (
                    build_base_sales_session(
                        customer=customer,
                        customer_360=customer_360,
                        primary_recommendation=(
                            primary_recommendation
                        ),
                        target_relevance=(
                            target_relevance
                        ),
                        commercial_context=(
                            commercial_context
                        ),
                    )
                )

                # -------------------------------------
                # AI CONTEXT
                # -------------------------------------

                context["sales_ai_context"] = (
                    build_sales_ai_context(
                        customer=customer,
                        customer_360=customer_360,
                        current_visit=current_visit,
                        sales_session=context.get(
                            "sales_session"
                        ),
                        recommendations=recommendations,
                    )
                )

                # -----------------------------------------
                # VISIT SUMMARY
                # -----------------------------------------

                visit_summary = None

                current_visit = context.get(
                    "current_visit"
                )

                if (
                    current_visit
                    and current_visit.status
                    == Visit.VisitStatus.COMPLETED
                ):

                    recommendation_ids = (
                        current_visit.sales_outcomes
                        .exclude(
                            recommendation_id__isnull=True
                        )
                        .values_list(
                            "recommendation_id",
                            flat=True,
                        )
                        .distinct()
                    )

                    resolved_outcomes = []

                    for recommendation_id in recommendation_ids:

                        resolved = (
                            resolve_recommendation_outcome(
                                visit_id=current_visit.id,
                                recommendation_id=recommendation_id,
                            )
                        )

                        if resolved:
                            resolved_outcomes.append(
                                resolved
                            )

                    visit_summary = {
                        "evaluated_recommendations": (
                            len(resolved_outcomes)
                        ),
                        "resolved_outcomes": (
                            resolved_outcomes
                        ),
                        "order_created": (
                            current_visit.order_created
                        ),
                        "order_amount": (
                            current_visit.order_amount
                        ),
                        "follow_up_required": (
                            current_visit.follow_up_required
                        ),
                        "follow_up_date": (
                            current_visit.follow_up_date
                        ),
                    }

                context["visit_summary"] = (
                    visit_summary
                )
                # -----------------------------------------
                # CURRENT FOLLOW-UP TASK
                # -----------------------------------------

                current_follow_up_task = (
                    FollowUpTask.objects
                    .filter(
                        customer=customer,
                        status=FollowUpTask.Status.OPEN,
                    )
                    .select_related(
                        "visit",
                        "salesperson",
                    )
                    .order_by(
                        "due_date",
                        "id",
                    )
                    .first()
                )

                context["current_follow_up_task"] = (
                    current_follow_up_task
                )

                current_follow_up_time_state = None

                if current_follow_up_task:

                    today = timezone.localdate()

                    if current_follow_up_task.due_date < today:

                        current_follow_up_time_state = (
                            "OVERDUE"
                        )

                    elif current_follow_up_task.due_date == today:

                        current_follow_up_time_state = (
                            "TODAY"
                        )

                    else:

                        current_follow_up_time_state = (
                            "UPCOMING"
                        )

                context["current_follow_up_time_state"] = (
                    current_follow_up_time_state
                )

        except Customer.DoesNotExist:

            context["not_found"] = True

    return render(
        request,
        "core/customer_360.html",
        context,
    )
class Customer360APIView(APIView):

    def get(self, request, customer_code):

        customer = get_object_or_404(
            Customer.objects.select_related(
                "grade"
            ),
            customer_code=customer_code,
            is_active=True,
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
                status=404,
            )

        # =========================================
        # SALES CONTEXT
        # =========================================

        assignment = (
            CustomerAssignment.objects
            .filter(
                customer=customer,
                is_active=True,
            )
            .select_related("salesperson")
            .order_by(
                "-start_date",
                "-id",
            )
            .first()
        )

        latest_visit = (
            Visit.objects
            .filter(
                customer=customer,
            )
            .select_related(
                "salesperson",
            )
            .prefetch_related(
                "sales_outcomes__recommendation__product",
            )
            .order_by(
                "-visit_date",
                "-id",
            )
            .first()
        )

        # =========================================
        # ASSIGNMENT DATA
        # =========================================

        assignment_data = None
        salesperson_data = None

        if assignment:

            salesperson = assignment.salesperson

            salesperson_data = {

                "employee_code": (
                    salesperson.employee_code
                ),

                "first_name": (
                    salesperson.first_name
                ),

                "last_name": (
                    salesperson.last_name
                ),

                "full_name": (
                    f"{salesperson.first_name} "
                    f"{salesperson.last_name}"
                ),

                "phone": (
                    salesperson.phone
                ),

                "is_active": (
                    salesperson.is_active
                ),
            }

            assignment_data = {

                "start_date": (
                    assignment.start_date
                ),

                "end_date": (
                    assignment.end_date
                ),

                "is_active": (
                    assignment.is_active
                ),
            }

        # =========================================
        # LATEST VISIT DATA
        # =========================================

        latest_visit_data = None
        sales_outcome_data = []

        if latest_visit:

            latest_visit_data = {

                "id": (
                    latest_visit.id
                ),

                "date": (
                    latest_visit.visit_date
                ),

                "status": (
                    latest_visit.status
                ),

                "customer_request": (
                    latest_visit.customer_request
                ),

                "customer_feedback": (
                    latest_visit.customer_feedback
                ),

                "competitor_information": (
                    latest_visit.competitor_information
                ),

                "notes": (
                    latest_visit.notes
                ),

                "order_created": (
                    latest_visit.order_created
                ),

                "order_amount": (
                    latest_visit.order_amount
                ),

                "follow_up_required": (
                    latest_visit.follow_up_required
                ),

                "follow_up_date": (
                    latest_visit.follow_up_date
                ),
            }

            # =====================================
            # SALES OUTCOMES
            # =====================================

            for outcome in (
                latest_visit.sales_outcomes.all()
            ):

                recommendation = (
                    outcome.recommendation
                )

                product = (
                    recommendation.product
                    if recommendation
                    else None
                )

                sales_outcome_data.append({

                    "id": (
                        outcome.id
                    ),

                    "outcome": (
                        outcome.outcome
                    ),

                    "quantity": (
                        outcome.quantity
                    ),

                    "sales_amount": (
                        outcome.sales_amount
                    ),

                    "notes": (
                        outcome.notes
                    ),

                    "product_code": (
                        product.product_code
                        if product
                        else None
                    ),

                    "product_name": (
                        product.name
                        if product
                        else None
                    ),

                    "recommendation_type": (
                        recommendation.recommendation_type
                        if recommendation
                        else None
                    ),

                    "created_at": (
                        outcome.created_at
                    ),
                })

        # =========================================
        # RECOMMENDATIONS
        # =========================================

        recommendations = (
            customer.recommendations
            .filter(
                is_active=True,
            )
            .select_related(
                "product",
                "product__category",
            )
            .order_by("rank")
        )

        recommendation_data = []

        for recommendation in recommendations:

            product = recommendation.product

            recommendation_data.append({

                "rank": (
                    recommendation.rank
                ),

                "product_code": (
                    product.product_code
                ),

                "product_name": (
                    product.name
                ),

                "category": str(
                    product.category
                ),

                "score": (
                    recommendation.score
                ),

                "recommendation_type": (
                    recommendation.recommendation_type
                ),

                "reason": (
                    recommendation.reason
                ),
            })

        # =========================================
        # RESPONSE
        # =========================================

        return Response({

            "customer": {

                "code": (
                    customer.customer_code
                ),

                "name": (
                    customer.name
                ),

                "type": (
                    customer.customer_type
                ),

                "city": (
                    customer.city
                ),

                "address": (
                    customer.address
                ),

                "phone": (
                    customer.phone
                ),

                "grade": {

                    "code": (
                        customer.grade.code
                    )
                    if customer.grade
                    else None,

                    "name": (
                        customer.grade.name
                    )
                    if customer.grade
                    else None,
                },
            },

            "customer_360": {

                "total_orders": (
                    customer_360.total_orders
                ),

                "total_items": (
                    customer_360.total_items
                ),

                "total_sales_amount": (
                    customer_360.total_sales_amount
                ),

                "average_order_value": (
                    customer_360.average_order_value
                ),

                "first_purchase_date": (
                    customer_360.first_purchase_date
                ),

                "last_purchase_date": (
                    customer_360.last_purchase_date
                ),

                "days_since_last_purchase": (
                    customer_360.days_since_last_purchase
                ),

                "recency_score": (
                    customer_360.recency_score
                ),

                "frequency_score": (
                    customer_360.frequency_score
                ),

                "monetary_score": (
                    customer_360.monetary_score
                ),

                "rfm_score": (
                    customer_360.rfm_score
                ),

                "segment": (
                    customer_360.segment
                ),

                "top_category": (
                    customer_360.top_category
                ),

                "top_product_code": (
                    customer_360.top_product_code
                ),

                "purchase_frequency": (
                    customer_360.purchase_frequency
                ),

                "sales_30d": (
                    customer_360.sales_30d
                ),

                "sales_90d": (
                    customer_360.sales_90d
                ),

                "sales_30d_change_percent": (
                    customer_360.sales_30d_change_percent
                ),

                "sales_90d_change_percent": (
                    customer_360.sales_90d_change_percent
                ),

                "calculated_at": (
                    customer_360.calculated_at
                ),
            },

            "sales_context": {

                "salesperson": (
                    salesperson_data
                ),

                "assignment": (
                    assignment_data
                ),

                "latest_visit": (
                    latest_visit_data
                ),

                "sales_outcomes": (
                    sales_outcome_data
                ),

                "sales_outcome_count": (
                    len(sales_outcome_data)
                ),
            },

            "recommendations": (
                recommendation_data
            ),

            "recommendation_count": (
                len(recommendation_data)
            ),
        })