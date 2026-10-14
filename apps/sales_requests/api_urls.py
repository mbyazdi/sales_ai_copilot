from django.urls import path

from .api_views import VisitQuoteAPIView
from .basket_views import BasketAPIView, BasketAddAPIView, BasketLineAPIView, BasketQuoteAPIView, BasketCommandStatusAPIView


urlpatterns = [
    path("v1/visits/<int:visit_id>/basket/", BasketAPIView.as_view(), name="visit-basket-v1"),
    path("v1/visits/<int:visit_id>/basket/quote/", BasketQuoteAPIView.as_view(), name="visit-basket-quote-v1"),
    path("v1/visits/<int:visit_id>/lines/", BasketAddAPIView.as_view(), name="visit-basket-add-v1"),
    path("v1/requests/<int:request_id>/lines/<int:line_id>/", BasketLineAPIView.as_view(), name="request-basket-line-v1"),
    path("v1/visits/<int:visit_id>/commands/<uuid:command_uuid>/", BasketCommandStatusAPIView.as_view(), name="visit-basket-command-v1"),
    path("v1/visits/<int:visit_id>/quote/", VisitQuoteAPIView.as_view(), name="visit-quote-v1"),
]
