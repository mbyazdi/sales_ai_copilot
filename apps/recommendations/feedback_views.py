"""Thin, session-authenticated feedback API. POST always requires CSRF."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.products.catalog import positive_id
from .catalog_context import CatalogContextUnavailable
from .feedback import FeedbackConflict, feedback_history, record_feedback
from .feedback_serializers import FeedbackCommandSerializer


class RecommendationFeedbackAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "post", "options"]

    def _run(self, callback):
        try:
            return callback()
        except PermissionDenied:
            return Response({"code": "ACCESS_DENIED", "detail": "دسترسی به بازخورد این ویزیت مجاز نیست."}, status=403)
        except Http404:
            return Response({"code": "NOT_FOUND", "detail": "زمینه مشتری، ویزیت یا پیشنهاد در دسترس نیست."}, status=404)
        except FeedbackConflict as error:
            return Response({"code": error.code, "detail": error.detail}, status=409)
        except CatalogContextUnavailable:
            return Response({"code": "CATALOG_CONTEXT_UNAVAILABLE", "detail": "زمینه پیشنهادها تغییر کرده یا منقضی شده است؛ زمینه ویزیت را بررسی کنید."}, status=409)
        except ValidationError:
            return Response({"code": "INVALID_INPUT", "detail": "اطلاعات فرمان معتبر نیست."}, status=400)

    def get(self, request, visit_id):
        def read():
            query = request.query_params
            recommendation_id = positive_id(query["recommendation_id"], "recommendation_id") if "recommendation_id" in query else None
            page = positive_id(query.get("page", "1"), "page")
            return Response(feedback_history(request.user, query.get("customer_code", "").strip(), visit_id, recommendation_id=recommendation_id, page=page))
        return self._run(read)

    def post(self, request, visit_id):
        serializer = FeedbackCommandSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"code": "INVALID_INPUT", "detail": "اطلاعات فرمان معتبر نیست.", "errors": serializer.errors}, status=400)
        def apply():
            body, status, replayed = record_feedback(request.user, visit_id, serializer.validated_data)
            return Response(body, status=status, headers={"Idempotent-Replayed": "true" if replayed else "false"})
        return self._run(apply)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        return response
