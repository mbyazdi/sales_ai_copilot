from django.urls import path

from .views import (
    CustomerRecommendationAPIView,
    CustomerRecommendationPerformanceAPIView,
)


urlpatterns = [

    path(
        "v1/recommendations/<str:customer_code>/",
        CustomerRecommendationAPIView.as_view(),
        name="customer-recommendations",
    ),

    path(
        "v1/customers/<str:customer_code>/performance/",
        CustomerRecommendationPerformanceAPIView.as_view(),
        name="customer-recommendation-performance",
    ),

]