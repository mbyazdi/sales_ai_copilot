from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required(
    login_url="/accounts/login/",
)
def recommendation_performance_dashboard(request):

    return render(
        request,
        "management/recommendation_performance.html",
    )