from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views

urlpatterns = [

    path(
        "admin/",
        admin.site.urls,
    ),

    path(
        "customers/",
        include(
            "apps.customers.urls"
        ),
    ),

    path(
        "api/customers/",
        include(
            "apps.customers.urls"
        ),
    ),

    path(
        "api/recommendations/",
        include(
            "apps.recommendations.urls"
        ),
    ),

    path(
        "api/visits/",
        include(
            "apps.visits.urls"
        ),
    ),
    path(
        "management/",
        include("apps.management.urls"),
    ),
    path(
        "api/sales/",
        include("apps.sales.urls"),
    ),
    path(
        "api/ai/",
        include("apps.ai.urls"),
    ),
    path(
        "api/targets/",
        include("apps.targets.urls"),
    ),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="core/login.html"
        ),
        name="login",
    ),
    path(
        "",
        include(
            "apps.core.urls"
        ),
    ),
]