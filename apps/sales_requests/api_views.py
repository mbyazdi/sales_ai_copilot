"""Read-only candidate quote API; no basket/request mutation behavior."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.pricing import PricingInputError
from apps.products.quotes import candidate_quote


class VisitQuoteAPIView(APIView):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def get(self, request, visit_id):
        try:
            data = candidate_quote(
                request.user, request.query_params.get("customer_code", ""),
                visit_id, request.query_params.get("items", ""),
            )
        except PermissionDenied:
            return Response({"code": "ACCESS_DENIED", "detail": "دسترسی به قیمت‌های این ویزیت مجاز نیست."}, status=403)
        except ValidationError as error:
            return Response({"code": "INVALID_INPUT", "errors": error.message_dict}, status=400)
        except PricingInputError as error:
            return Response({"code": error.code, "detail": "مقادیر درخواست قیمت در محدوده مجاز نیست."}, status=400)
        except Http404:
            return Response({"code": "NOT_FOUND", "detail": "زمینه مشتری، ویزیت یا محصول در دسترس نیست."}, status=404)
        return Response(data)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        return response
