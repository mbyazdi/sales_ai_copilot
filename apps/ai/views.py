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

        if (
            customer_360.segment
            == "HIGH_VALUE"
        ):

            customer_status = (
                "مشتری با ارزش بالا و دارای "
                "پتانسیل مناسب برای فروش مجدد"
            )

        else:

            customer_status = (
                "مشتری فعال با فرصت‌های فروش "
                "قابل بررسی"
            )

        days_since_last_purchase = (
            customer_360
            .days_since_last_purchase
        )

        if (
            days_since_last_purchase
            is not None
            and days_since_last_purchase >= 20
        ):

            sales_opportunity = (
                f"مشتری "
                f"{days_since_last_purchase} "
                "روز است که خریدی نداشته است. "
                "این موضوع می‌تواند یک فرصت "
                "مناسب برای پیگیری فروش باشد."
            )

        else:

            sales_opportunity = (
                "مشتری اخیراً خرید داشته است. "
                "تمرکز روی فروش مکمل و محصولات "
                "مرتبط پیشنهاد می‌شود."
            )

        if primary:

            product_name = (
                primary.product.name
            )

            product_code = (
                primary.product.product_code
            )

            recommendation_type = (
                primary.recommendation_type
            )

            if (
                recommendation_type
                == "REPEAT_PURCHASE"
            ):

                next_best_action = (
                    f"پیشنهاد خرید مجدد "
                    f"{product_name} "
                    "را مطرح کنید."
                )

                talking_point = (
                    "با توجه به سابقه خرید مشتری، "
                    f"درباره خرید مجدد "
                    f"{product_name} "
                    "با مشتری صحبت کنید."
                )

            elif (
                recommendation_type
                == "CROSS_SELL"
            ):

                next_best_action = (
                    f"محصول مکمل "
                    f"{product_name} "
                    "را مطرح کنید."
                )

                talking_point = (
                    "با توجه به خریدهای قبلی مشتری، "
                    f"{product_name} "
                    "را به عنوان محصول مکمل "
                    "معرفی کنید."
                )

            elif (
                recommendation_type
                == "CATEGORY"
            ):

                next_best_action = (
                    f"محصول "
                    f"{product_name} "
                    "را از دسته مورد علاقه "
                    "مشتری معرفی کنید."
                )

                talking_point = (
                    "با توجه به علاقه مشتری "
                    "به این دسته، "
                    f"{product_name} "
                    "را به عنوان گزینه جدید "
                    "مطرح کنید."
                )

            elif (
                recommendation_type
                == "SIMILAR_PRODUCT"
            ):

                next_best_action = (
                    f"{product_name} "
                    "را به عنوان گزینه مشابه "
                    "مطرح کنید."
                )

                talking_point = (
                    f"{product_name} "
                    "را به عنوان جایگزین یا "
                    "گزینه مشابه معرفی کنید."
                )

            else:

                next_best_action = (
                    f"{product_name} "
                    "را به عنوان پیشنهاد اصلی "
                    "مطرح کنید."
                )

                talking_point = (
                    f"محصول {product_name} "
                    "را به عنوان یکی از "
                    "گزینه‌های اصلی معرفی کنید."
                )

        else:

            product_name = None
            product_code = None
            recommendation_type = None

            next_best_action = (
                "در حال حاضر پیشنهاد مشخصی "
                "برای این مشتری وجود ندارد."
            )

            talking_point = (
                "ابتدا نیاز فعلی مشتری "
                "را بررسی کنید."
            )

        sales_session = {

            "customer_status":
                customer_status,

            "sales_opportunity":
                sales_opportunity,

            "primary_product":
                product_name,

            "primary_product_code":
                product_code,

            "recommendation_type":
                recommendation_type,

            "next_best_action":
                next_best_action,

            "talking_point":
                talking_point,
        }

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