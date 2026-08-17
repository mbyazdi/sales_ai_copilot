from django.contrib import admin
from django.urls import include, path


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
]