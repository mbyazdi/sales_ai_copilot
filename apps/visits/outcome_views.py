"""Additive current-visit read contract; the outcome writer remains unchanged."""

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.access import customer_access_queryset

from .models import Visit
from .services import build_post_visit_intelligence


class VisitRecommendationOutcomesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, visit_id):
        salesperson = getattr(request.user, "salesperson_profile", None)
        if request.user.is_staff or salesperson is None or not salesperson.is_active:
            return Response({"detail": "دسترسی به زمینه عملیاتی ویزیت مجاز نیست."}, status=403)
        try:
            code = request.query_params.get("customer_code", "").strip()
            if not code:
                raise Http404
            customer = get_object_or_404(
                customer_access_queryset(request.user), customer_code=code, is_active=True,
            )
            visit = get_object_or_404(
                Visit.objects.select_related("customer", "salesperson"),
                pk=visit_id, customer=customer, salesperson=salesperson,
            )
        except Http404:
            return Response({"detail": "زمینه ویزیت در دسترس نیست."}, status=404)

        intelligence = build_post_visit_intelligence(visit)
        response = Response({
            "visit": {
                "id": visit.pk, "visit_date": visit.visit_date, "status": visit.status,
                "customer_code": customer.customer_code, "customer_name": customer.name,
            },
            "can_record": visit.status == Visit.VisitStatus.IN_PROGRESS,
            "recommendation_outcomes": intelligence["recommendation_outcomes"],
        })
        response["Cache-Control"] = "no-store, private"
        return response
