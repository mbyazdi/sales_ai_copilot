from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from apps.customers.access import customer_access_queryset

from .services import get_customer_sales_history


class CustomerSalesHistoryAPIView(APIView):

    def get(
        self,
        request,
        customer_code,
    ):

        get_object_or_404(
            customer_access_queryset(request.user),
            customer_code=customer_code, is_active=True,
        )
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
