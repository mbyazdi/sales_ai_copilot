"""Versioned salesperson catalog reads. No mutation endpoints."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.recommendations.catalog_context import CatalogContextUnavailable

from .catalog import build_catalog


class CatalogAPIView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        try:
            data = build_catalog(
                request.user, request.query_params.get("customer_code", ""),
                request.query_params.get("visit_id", ""), request.query_params,
            )
        except PermissionDenied:
            return Response({"code": "ACCESS_DENIED", "detail": "دسترسی به فهرست محصولات مجاز نیست."}, status=403)
        except ValidationError as error:
            return Response({"code": "INVALID_INPUT", "errors": error.message_dict}, status=400)
        except Http404:
            return Response({"code": "NOT_FOUND", "detail": "زمینه مشتری یا ویزیت در دسترس نیست."}, status=404)
        except CatalogContextUnavailable:
            return Response({"code": "CATALOG_CONTEXT_UNAVAILABLE", "detail": "زمینه پیشنهادها معتبر نیست یا تغییر کرده است؛ بازگشت به ویزیت لازم است."}, status=409)
        return Response(data)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        return response
