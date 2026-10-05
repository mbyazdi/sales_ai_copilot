from django.contrib.admin.views.decorators import (
    staff_member_required,
)
from django.shortcuts import render

from apps.recommendations.models import RecommendationConfig
from apps.visits.services import (
    build_management_dashboard_contract,
    build_management_kpi_trend_contract,
    build_management_decision_support_context,
    build_recommendation_type_analytics,
)


@staff_member_required(
    login_url="/accounts/login/",
)
def management_dashboard(request):

    dashboard = build_management_dashboard_contract(customer=None)
    return render(
        request,
        "management/dashboard.html",
        {
            "dashboard": dashboard,
            "summary": dashboard.get("executive_summary") or {},
            "trend": build_management_kpi_trend_contract(customer=None),
            "decisions": build_management_decision_support_context(customer=None),
        },
    )


@staff_member_required(
    login_url="/accounts/login/",
)
def recommendation_performance_dashboard(request):

    # Canonical management values; legacy API and tuning snapshots stay intact.
    performance = build_recommendation_type_analytics(customer=None)
    active_config = RecommendationConfig.objects.filter(is_active=True).order_by(
        "-updated_at", "-id",
    ).first()
    config_fields = (
        ("min_recommendation_score", "حداقل امتیاز پیشنهاد"),
        ("max_recommendations", "حداکثر تعداد پیشنهاد"),
        ("promotion_score", "امتیاز ترویج فروش"),
        ("association_max_score", "سقف امتیاز فروش مکمل"),
        ("repurchase_no_cycle_score", "امتیاز خرید مجدد بدون چرخه"),
        ("similar_product_score", "امتیاز محصول مشابه"),
        ("grade_a_score", "امتیاز رتبه مشتری A"),
        ("grade_b_score", "امتیاز رتبه مشتری B"),
        ("grade_c_score", "امتیاز رتبه مشتری C"),
    )
    return render(
        request,
        "management/recommendation_performance.html",
        {
            "performance": performance,
            "summary": performance["summary"],
            "active_config": active_config,
            "config_values": [
                {"label": label, "value": getattr(active_config, field)}
                for field, label in config_fields
            ] if active_config else [],
        },
    )
