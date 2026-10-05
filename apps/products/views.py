"""Read-only product presentation within the canonical customer boundary."""

from urllib.parse import urlencode
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_safe

from apps.core.commercial_context import build_product_commercial_context
from apps.customers.access import customer_access_queryset
from apps.recommendations.models import CustomerRecommendation
from apps.visits.models import Visit

from .models import Product


# Presentation labels only; all values and classifications remain stored values.
EVIDENCE_LABELS = {"HIGH": "شواهد قوی", "MEDIUM": "شواهد متوسط", "LOW": "شواهد محدود"}
SIGNAL_LABELS = {
    "group_affinity": "تناسب گروه محصول", "group_score": "تناسب گروه محصول",
    "repurchase": "چرخه خرید مجدد", "purchase_score": "چرخه خرید مجدد",
    "association": "هم‌خریدی و فروش مکمل", "association_score": "هم‌خریدی و فروش مکمل",
    "upsell": "فروش ارتقایی", "upsell_score": "فروش ارتقایی",
    "customer_grade": "رتبه مشتری", "grade_score": "رتبه مشتری",
    "promotion": "ترویج فروش", "promotion_score": "ترویج فروش",
    "similar_product": "شباهت محصول", "similar_score": "شباهت محصول",
    "historical_feedback": "بازخورد تاریخی", "feedback_score": "بازخورد تاریخی",
    "rule_score": "امتیاز قواعد", "final_score": "امتیاز نهایی",
}


def _has_nonzero_score(value):
    """Presentation eligibility only; never recompute a signal's score."""
    if value is None or isinstance(value, bool):
        return False
    try:
        score = Decimal(str(value))
        return score.is_finite() and score != 0
    except InvalidOperation:
        return False


@require_safe
def product_commercial_brief(request, product_code):
    try:
        # Resolve authorized customer before product, visit or commercial reads.
        customers = customer_access_queryset(request.user)
        customer_code = request.GET.get("customer_code", "").strip()
        if not customer_code:
            raise Http404
        customer = get_object_or_404(customers, customer_code=customer_code, is_active=True)

        visit = None
        visit_id = request.GET.get("visit_id", "").strip()
        if visit_id:
            # Staff inspection never carries operational visit context, including
            # dual-role accounts. Invalid combinations use one generic response.
            if request.user.is_staff or not visit_id.isascii() or not visit_id.isdecimal():
                raise Http404
            if len(visit_id) > 18:
                raise Http404
            visit = get_object_or_404(
                Visit.objects.filter(
                    customer=customer, salesperson=request.user.salesperson_profile,
                ), pk=int(visit_id),
            )

        product = get_object_or_404(
            Product.objects.select_related("brand", "category"),
            product_code=product_code, is_active=True,
        )
    except PermissionDenied:
        return render(request, "products/unavailable.html", status=403)
    except Http404:
        return render(request, "products/unavailable.html", status=404)

    today = timezone.localdate()
    commercial = build_product_commercial_context(product, customer, as_of_date=today)
    recommendation = CustomerRecommendation.objects.filter(
        customer=customer, product=product, is_active=True,
    ).first()
    snapshot = recommendation.explanation_snapshot if recommendation else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    stored_signals = snapshot.get("signals", [])
    signals = []
    if isinstance(stored_signals, list):
        for signal in stored_signals:
            if isinstance(signal, dict):
                signals.append({
                    "label": SIGNAL_LABELS.get(signal.get("name"), "شاهد ثبت‌شده"),
                    "score": signal.get("score"),
                    "active": signal.get("active") is True,
                    "state": "فعال" if signal.get("active") is True else (
                        "غیرفعال" if signal.get("active") is False else "وضعیت ثبت نشده"
                    ),
                })
    # Preserve source order and values; only select what is useful at first glance.
    active_signals = [signal for signal in signals if signal["active"] and _has_nonzero_score(signal["score"])]
    breakdown = recommendation.score_breakdown if recommendation else {}
    components = [
        {"label": SIGNAL_LABELS.get(key, "شاخص ثبت‌شده"), "value": value}
        for key, value in breakdown.items()
    ] if isinstance(breakdown, dict) else []
    return_query = {"customer_code": customer.customer_code}
    if visit:
        return_query["visit_id"] = visit.pk
    return render(request, "core/product_detail.html", {
        "product": product, "customer": customer, "commercial": commercial,
        "as_of_date": today, "recommendation": recommendation,
        "evidence_label": EVIDENCE_LABELS.get(
            recommendation.evidence_quality if recommendation else None, "کیفیت شواهد ثبت نشده",
        ),
        "signals": signals, "components": components,
        "active_signals": active_signals,
        "show_product_description": bool(product.description.strip()) and (
            " ".join(product.description.split()).casefold() != " ".join(product.name.split()).casefold()
        ),
        "active_signal_count": snapshot.get("active_signal_count"),
        "visit": visit, "manager_inspection": request.user.is_staff,
        # The legacy customer URL name is included under both HTML and API
        # prefixes; use the canonical HTML entry rather than its ambiguous reverse.
        "return_url": "/customers/?" + urlencode(return_query) + "#workspace-recommendations",
    })
