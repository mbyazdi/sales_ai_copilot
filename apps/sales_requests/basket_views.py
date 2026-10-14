"""Thin session-only basket boundary: every mutation requires Django CSRF."""
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.catalog import positive_id
from apps.products.pricing import PricingInputError
from apps.products.quotes import MAX_QUANTITY
from apps.recommendations.catalog_context import CatalogContextUnavailable
from .basket import BasketConflict, basket_quote, command_status, inspect_basket, mutate_basket
from .basket_serializers import AddBasketCommandSerializer, BasketCommandSerializer, PricedBasketCommandSerializer
from .models import SalesRequest


class BasketAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "options"]

    def run(self, callback):
        try:
            return callback()
        except PermissionDenied:
            return Response({"code": "ACCESS_DENIED", "detail": "دسترسی به درخواست این ویزیت مجاز نیست."}, status=403)
        except Http404:
            return Response({"code": "NOT_FOUND", "detail": "زمینه درخواست یا قلم در دسترس نیست."}, status=404)
        except BasketConflict as error:
            return Response({"code": error.code, "detail": error.detail}, status=409)
        except CatalogContextUnavailable:
            return Response({"code": "CATALOG_CONTEXT_UNAVAILABLE", "detail": "زمینه فروش معتبر نیست؛ زمینه ویزیت را بررسی کنید."}, status=409)
        except (ValidationError, ValueError, PricingInputError):
            return Response({"code": "INVALID_INPUT", "detail": "اطلاعات درخواست معتبر نیست یا بیش از محدوده مجاز است."}, status=400)

    def get(self, request, visit_id):
        return self.run(lambda: Response(inspect_basket(request.user, request.query_params.get("customer_code", ""), visit_id)))

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        return response

    def apply(self, request, visit_id, operation, serializer_type, **targets):
        serializer = serializer_type(data=request.data)
        if not serializer.is_valid():
            return Response({"code": "INVALID_INPUT", "detail": "اطلاعات فرمان معتبر نیست.", "errors": serializer.errors}, status=400)
        def mutation():
            body, status, replayed = mutate_basket(request.user, visit_id, operation, serializer.validated_data, **targets)
            return Response(body, status=status, headers={"Idempotent-Replayed": "true" if replayed else "false"})
        return self.run(mutation)


class BasketQuoteAPIView(BasketAPIView):
    def get(self, request, visit_id):
        def read():
            product_id = positive_id(request.query_params.get("product_id", ""), "product_id")
            quantity = positive_id(request.query_params.get("quantity", ""), "quantity")
            if quantity > MAX_QUANTITY:
                raise ValueError
            return Response(basket_quote(request.user, request.query_params.get("customer_code", ""), visit_id, product_id, quantity))
        return self.run(read)


class BasketAddAPIView(BasketAPIView):
    http_method_names = ["post", "options"]

    def post(self, request, visit_id):
        return self.apply(request, visit_id, "ADD_PRODUCT", AddBasketCommandSerializer)


class BasketLineAPIView(BasketAPIView):
    http_method_names = ["patch", "delete", "options"]

    def change(self, request, request_id, line_id, operation, serializer_type):
        # Only look up the parent identity; all access/disclosure is authorized in
        # the service, including replay. Never load a foreign line before access.
        parent = SalesRequest.objects.filter(pk=request_id).values("visit_id").first()
        if parent is None:
            return Response({"code": "NOT_FOUND", "detail": "درخواست در دسترس نیست."}, status=404)
        return self.apply(request, parent["visit_id"], operation, serializer_type, request_id=request_id, line_id=line_id)

    def patch(self, request, request_id, line_id):
        return self.change(request, request_id, line_id, "SET_QUANTITY", PricedBasketCommandSerializer)

    def delete(self, request, request_id, line_id):
        return self.change(request, request_id, line_id, "REMOVE_PRODUCT", BasketCommandSerializer)


class BasketCommandStatusAPIView(BasketAPIView):
    def get(self, request, visit_id, command_uuid):
        return self.run(lambda: Response(command_status(request.user, request.query_params.get("customer_code", ""), visit_id, UUID(str(command_uuid)))))
