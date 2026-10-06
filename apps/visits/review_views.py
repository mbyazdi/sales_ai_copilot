"""Read-only customer-context review; completion remains a separate explicit API action."""
from urllib.parse import urlencode

from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_safe

from apps.customers.access import customer_access_queryset
from apps.recommendations.models import CustomerRecommendation
from .models import Visit
from .services import build_post_visit_intelligence


@require_safe
def visit_completion_review(request, customer_code, visit_id):
    customers = customer_access_queryset(request.user)
    if request.user.is_staff:
        return HttpResponseForbidden("مرور عملیاتی و پایان ویزیت برای نماینده فروش است؛ از بررسی مشتری استفاده کنید.")
    try:
        customer = get_object_or_404(customers, customer_code=customer_code, is_active=True)
        visit = get_object_or_404(
            Visit.objects.select_related("customer", "salesperson"),
            pk=visit_id, customer=customer, salesperson=request.user.salesperson_profile,
        )
    except Http404:
        return render(request, "customers/unavailable.html", status=404)
    intelligence = build_post_visit_intelligence(visit)
    query = {"visit_id": visit.pk}
    selected = request.GET.get("recommendation_id", "").strip()
    if selected.isascii() and selected.isdecimal() and len(selected) <= 18:
        recommendation = CustomerRecommendation.objects.filter(
            pk=int(selected), customer=customer, is_active=True,
        ).first()
        if recommendation:
            query["recommendation_id"] = recommendation.pk
    guided_url = reverse("recommendation-presentation", args=[customer.customer_code]) + "?" + urlencode(query)
    response = render(request, "visits/completion_review.html", {
        "customer": customer, "visit": visit, "summary": intelligence["summary"],
        "follow_up": intelligence["follow_up"], "guided_url": guided_url,
        "completed": visit.status == Visit.VisitStatus.COMPLETED,
        "can_finish": visit.status == Visit.VisitStatus.IN_PROGRESS,
        "unattributed_events": intelligence["unattributed_outcome_events"],
    })
    response["Cache-Control"] = "no-store, private"
    return response
