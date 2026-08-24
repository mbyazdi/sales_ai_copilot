from django.urls import path

from .views import (
    MySalesTargetProgressAPIView,
)


app_name = "targets"


urlpatterns = [

    path(
        "v1/my-progress/",
        MySalesTargetProgressAPIView.as_view(),
        name="my-target-progress",
    ),

]