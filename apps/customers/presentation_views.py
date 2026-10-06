"""One recommendation per page; navigation is presentation state, never business state."""
import re
from urllib.parse import urlencode

from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from apps.core.commercial_context import build_product_commercial_context
from apps.recommendations.models import CustomerRecommendation
from apps.visits.models import Visit
from .access import customer_access_queryset


def recommendation_presentation(request, customer_code):
    customers = customer_access_queryset(request.user)
    if request.user.is_staff:
        return HttpResponseForbidden("نمایش عملیاتی پیشنهادها برای نماینده فروش است؛ از بررسی مشتری استفاده کنید.")
    try:
        customer = get_object_or_404(customers, customer_code=customer_code, is_active=True)
        salesperson = request.user.salesperson_profile
        visit = None
        raw_visit = request.GET.get("visit_id", "").strip()
        if raw_visit:
            if not raw_visit.isascii() or not raw_visit.isdecimal() or len(raw_visit) > 18:
                raise Http404
            visit = get_object_or_404(Visit, pk=int(raw_visit), customer=customer, salesperson=salesperson)
        recommendations = list(CustomerRecommendation.objects.filter(
            customer=customer, is_active=True,
        ).select_related("product", "product__brand", "product__category").order_by("rank"))
        selected_id = request.GET.get("recommendation_id", "").strip()
        position = 0
        if selected_id:
            if not selected_id.isascii() or not selected_id.isdecimal():
                raise Http404
            position = next((i for i, row in enumerate(recommendations) if str(row.pk) == selected_id), None)
            if position is None:
                raise Http404
    except Http404:
        return render(request, "customers/unavailable.html", status=404)

    selected = recommendations[position] if recommendations else None
    params = {"customer_code": customer.customer_code}
    if visit:
        params["visit_id"] = visit.pk
    customer_url = "/customers/?" + urlencode(params)
    end_url = customer_url
    if visit:
        end_url = reverse("visit-completion-review", args=[customer.customer_code, visit.pk])
        if selected:
            end_url += "?" + urlencode({"recommendation_id": selected.pk})
    base = reverse("recommendation-presentation", args=[customer.customer_code])

    def presentation_url(index):
        query = {"recommendation_id": recommendations[index].pk}
        if visit:
            query["visit_id"] = visit.pk
        return base + "?" + urlencode(query)

    group_next = None
    if selected:
        group_next = next((i for i in range(position + 1, len(recommendations))
                           if recommendations[i].recommendation_type != selected.recommendation_type), None)
    commercial = None
    if selected and selected.product.is_active:
        commercial = build_product_commercial_context(selected.product, customer, as_of_date=timezone.localdate())
    brief_url = None
    if commercial:
        brief_params = {**params, "return_to": "presentation"}
        brief_url = reverse("product-commercial-brief", args=[selected.product.product_code]) + "?" + urlencode(brief_params)
    # Select complete saved sentences only, without interpreting scores/signals.
    short_reason = " ".join(re.split(r"(?<=[.!؟])\s+", selected.reason.strip())[:2]) if selected and selected.reason.strip() else ""
    response = render(request, "customers/recommendation_presentation.html", {
        "customer": customer, "salesperson": salesperson, "current_visit": visit,
        "recommendation": selected, "commercial": commercial, "short_reason": short_reason,
        "position": position + 1 if selected else 0, "total": len(recommendations),
        "remaining": len(recommendations) - position - 1 if selected else 0,
        "previous_url": presentation_url(position - 1) if selected and position > 0 else None,
        "next_url": presentation_url(position + 1) if selected and position + 1 < len(recommendations) else None,
        "group_next_url": presentation_url(group_next) if group_next is not None else None,
        "customer_url": customer_url, "brief_url": brief_url, "end_url": end_url,
        "image_url": None,  # Reserved presentation adapter; no canonical media source exists yet.
    })
    response["Cache-Control"] = "no-store, private"
    return response
