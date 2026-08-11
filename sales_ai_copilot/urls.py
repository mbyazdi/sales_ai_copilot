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
        "recommendations/",
        include(
            "apps.recommendations.urls"
        ),
    ),

]