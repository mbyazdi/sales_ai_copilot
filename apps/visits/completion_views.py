"""Session-only completion API; legacy /complete/ remains unchanged."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.models import Customer
from apps.recommendations.feedback_serializers import StrictTextField
from .completion import CompletionConflict, complete_visit, completion_state


class CompletionCommandSerializer(serializers.Serializer):
    customer_code = StrictTextField(max_length=Customer._meta.get_field("customer_code").max_length)
    command_uuid = serializers.UUIDField()

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["ساختار فرمان یا فیلدهای آن معتبر نیست."]})
        return super().to_internal_value(data)


class VisitCompletionAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "head", "post", "options"]

    def run(self, callback):
        try:
            return callback()
        except PermissionDenied:
            return Response({"code": "ACCESS_DENIED", "detail": "دسترسی به پایان این ویزیت مجاز نیست."}, status=403)
        except Http404:
            return Response({"code": "NOT_FOUND", "detail": "زمینه مشتری یا ویزیت در دسترس نیست."}, status=404)
        except CompletionConflict as error:
            return Response({"code": error.code, "detail": error.detail}, status=409)
        except ValidationError:
            return Response({"code": "INVALID_INPUT", "detail": "اطلاعات پایان ویزیت معتبر نیست."}, status=400)

    def get(self, request, visit_id):
        return self.run(lambda: Response(completion_state(
            request.user, request.query_params.get("customer_code", ""), visit_id,
        )))

    def post(self, request, visit_id):
        serializer = CompletionCommandSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"code": "INVALID_INPUT", "detail": "اطلاعات فرمان پایان معتبر نیست.",
                             "errors": serializer.errors}, status=400)

        def apply():
            body, status, replayed = complete_visit(request.user, visit_id, serializer.validated_data)
            return Response(body, status=status, headers={"Idempotent-Replayed": "true" if replayed else "false"})
        return self.run(apply)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        return response
