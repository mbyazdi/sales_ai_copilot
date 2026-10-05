from django.contrib.admin.views.decorators import (
    staff_member_required,
)
from django.shortcuts import render

from apps.visits.services import (
    build_management_dashboard_contract,
    build_management_kpi_trend_contract,
    build_management_decision_support_context,
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

    return render(
        request,
        "management/recommendation_performance.html",
    )
