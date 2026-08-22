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
    resolve_recommendation_outcome,
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

                # Customer status
                if customer_360.segment == "HIGH_VALUE":
                    customer_status = (
                        "مشتری با ارزش بالا و دارای "
                        "پتانسیل مناسب برای فروش مجدد"
                    )
                else:
                    customer_status = (
                        "مشتری فعال با فرصت‌های فروش قابل بررسی"
                    )

                # Sales opportunity
                if (
                    customer_360.days_since_last_purchase
                    and customer_360.days_since_last_purchase >= 20
                ):
                    sales_opportunity = (
                        f"مشتری {customer_360.days_since_last_purchase} "
                        "روز است که خریدی نداشته است. "
                        "این موضوع می‌تواند یک فرصت مناسب "
                        "برای پیگیری فروش باشد."
                    )
                else:
                    sales_opportunity = (
                        "مشتری اخیراً خرید داشته است. "
                        "تمرکز روی فروش مکمل و محصولات مرتبط "
                        "پیشنهاد می‌شود."
                    )

                # Primary product
                if primary_recommendation:

                    primary_product = (
                        primary_recommendation.product.name
                    )

                    primary_product_code = (
                        primary_recommendation.product.product_code
                    )

                    primary_reason = (
                        primary_recommendation.reason
                    )

                    recommendation_type = (
                        primary_recommendation.recommendation_type
                    )

                else:

                    primary_product = None
                    primary_product_code = None
                    primary_reason = None
                    recommendation_type = None

                # Salesperson talking point
                if primary_recommendation:

                    if (
                        recommendation_type
                        == "REPEAT_PURCHASE"
                    ):

                        talking_point = (
                            f"با توجه به سابقه خرید مشتری، "
                            f"در مورد تمدید یا خرید مجدد "
                            f"{primary_product} "
                            "با مشتری صحبت کنید."
                        )

                    elif (
                        recommendation_type
                        == "CROSS_SELL"
                    ):

                        talking_point = (
                            f"با توجه به خریدهای قبلی مشتری، "
                            f"محصول مکمل {primary_product} "
                            "را به عنوان پیشنهاد جانبی مطرح کنید."
                        )

                    elif (
                        recommendation_type
                        == "CATEGORY"
                    ):

                        talking_point = (
                            f"با توجه به علاقه مشتری به این دسته، "
                            f"محصول {primary_product} "
                            "را به عنوان گزینه جدید معرفی کنید."
                        )

                    elif (
                        recommendation_type
                        == "SIMILAR_PRODUCT"
                    ):

                        talking_point = (
                            f"محصول {primary_product} "
                            "را به عنوان جایگزین یا گزینه مشابه "
                            "معرفی کنید."
                        )

                    else:

                        talking_point = (
                            f"محصول {primary_product} "
                            "را به عنوان یکی از گزینه‌های اصلی "
                            "پیشنهاد دهید."
                        )

                else:

                    talking_point = (
                        "در حال حاضر پیشنهاد مشخصی برای "
                        "این مشتری ثبت نشده است."
                    )

                # -----------------------------------------
                # NEXT BEST ACTION
                # -----------------------------------------

                if primary_recommendation:

                    if (
                        recommendation_type
                        == "REPEAT_PURCHASE"
                    ):

                        next_best_action = (
                            f"پیشنهاد خرید مجدد "
                            f"{primary_product} "
                            "را در ابتدای گفتگو مطرح کنید."
                        )

                    elif (
                        recommendation_type
                        == "CROSS_SELL"
                    ):

                        next_best_action = (
                            f"بعد از مرور خرید قبلی، "
                            f"{primary_product} "
                            "را به عنوان محصول مکمل پیشنهاد دهید."
                        )

                    elif (
                        recommendation_type
                        == "UP_SELL"
                    ):

                        next_best_action = (
                            f"مشتری را به گزینه بالاتر "
                            f"{primary_product} "
                            "هدایت کنید."
                        )

                    elif (
                        recommendation_type
                        == "CATEGORY"
                    ):

                        next_best_action = (
                            f"محصول "
                            f"{primary_product} "
                            "را از دسته مورد علاقه مشتری معرفی کنید."
                        )

                    elif (
                        recommendation_type
                        == "SIMILAR_PRODUCT"
                    ):

                        next_best_action = (
                            f"محصول "
                            f"{primary_product} "
                            "را به عنوان گزینه جایگزین معرفی کنید."
                        )

                    else:

                        next_best_action = (
                            f"محصول "
                            f"{primary_product} "
                            "را به عنوان پیشنهاد اصلی مطرح کنید."
                        )

                else:

                    next_best_action = (
                        "در حال حاضر اقدام پیشنهادی مشخصی "
                        "برای این مشتری وجود ندارد."
                    )

                context["sales_session"] = {

                    "customer_status": customer_status,

                    "sales_opportunity": (
                        sales_opportunity
                    ),

                    "primary_product": (
                        primary_product
                    ),

                    "primary_product_code": (
                        primary_product_code
                    ),

                    "primary_reason": (
                        primary_reason
                    ),

                    "next_best_action": (
                        next_best_action
                    ),
                    
                    "talking_point": (
                        talking_point
                    ),

                    "recommendation_type": (
                        recommendation_type
                    ),
                }

                context["sales_ai_context"] = (
                    build_sales_ai_context(
                        customer=customer,
                        customer_360=customer_360,
                        current_visit=context.get(
                            "current_visit"
                        ),
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