from django.urls import path

from .views import product_commercial_brief


urlpatterns = [
    path("<str:product_code>/", product_commercial_brief, name="product-commercial-brief"),
]
