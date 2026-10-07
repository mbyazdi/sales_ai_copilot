from django.urls import path

from .api_views import CatalogAPIView


urlpatterns = [path("v1/catalog/", CatalogAPIView.as_view(), name="product-catalog-v1")]
