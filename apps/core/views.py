from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import (
    redirect,
    get_object_or_404,
)
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.models import Customer
from apps.products.models import Product

from .commercial_context import (
    build_product_commercial_context,
)

@login_required
def role_home(request):
    """
    Route authenticated users to the correct
    workspace based on their application role.
    """

    if (
        request.user.is_staff
        or request.user.is_superuser
    ):
        return redirect(
            "recommendation-performance-dashboard"
        )

    salesperson = getattr(
        request.user,
        "salesperson_profile",
        None,
    )

    if (
        salesperson
        and salesperson.is_active
    ):
        return redirect(
            "salesperson-dashboard"
        )

    return HttpResponseForbidden(
        "No active Sales AI Copilot role is assigned "
        "to this user."
    )

class ProductCommercialContextAPIView(APIView):
    """
    Read-only commercial context for one
    Customer + Product pair.
    """

    permission_classes = [
        IsAuthenticated,
    ]

    def get(
        self,
        request,
        customer_code,
        product_code,
    ):
        customer = get_object_or_404(
            Customer,
            customer_code=customer_code,
            is_active=True,
        )

        product = get_object_or_404(
            Product,
            product_code=product_code,
            is_active=True,
        )

        commercial_context = (
            build_product_commercial_context(
                product=product,
                customer=customer,
                as_of_date=timezone.localdate(),
            )
        )

        return Response(
            {
                "customer": {
                    "customer_code":
                        customer.customer_code,
                    "name":
                        customer.name,
                    "grade": (
                        customer.grade.code
                        if customer.grade
                        else None
                    ),
                },
                "product": {
                    "product_code":
                        product.product_code,
                    "name":
                        product.name,
                },
                "commercial_context":
                    commercial_context,
            }
        )