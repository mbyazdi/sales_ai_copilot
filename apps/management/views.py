from django.shortcuts import render


def recommendation_performance_dashboard(request):
    return render(
        request,
        "management/recommendation_performance.html",
    )