from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views
from apps.customers.presentation_views import recommendation_presentation
from apps.visits.review_views import visit_completion_review

urlpatterns = [

    path("customers/<str:customer_code>/visits/<int:visit_id>/review/", visit_completion_review, name="visit-completion-review"),

    path("customers/<str:customer_code>/recommendations/presentation/", recommendation_presentation, name="recommendation-presentation"),

    path("products/", include("apps.products.urls")),

    path("api/products/", include("apps.products.api_urls")),

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
        "api/management/",
        include("apps.management.api_urls"),
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
