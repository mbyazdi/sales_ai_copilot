from rest_framework.response import Response
from rest_framework.views import APIView

from .services import get_customer_sales_history


class CustomerSalesHistoryAPIView(APIView):

    def get(
        self,
        request,
        customer_code,
    ):

        result = get_customer_sales_history(
            customer_code=customer_code,
        )

        customer = result["customer"]
        summary = result["summary"]

        return Response({

            "customer": {

                "code": (
                    customer.customer_code
                ),

                "name": (
                    customer.name
                ),

            },

            "summary": summary,

            "sales": result["sales"],

        })