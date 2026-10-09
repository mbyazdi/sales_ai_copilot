from django.urls import path

from .api_views import VisitQuoteAPIView


urlpatterns = [
    path("v1/visits/<int:visit_id>/quote/", VisitQuoteAPIView.as_view(), name="visit-quote-v1"),
]
