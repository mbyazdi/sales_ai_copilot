"""Thin session/CSRF V1 transport over approved strategy command services."""
import re

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import DatabaseError, IntegrityError
from django.http import Http404
from rest_framework import exceptions, serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import JSONParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from . import strategy_api_reads as reads
from .strategy_access import can_manage_strategy, can_view_strategy
from .strategy_api_serializers import (
    ActivateRollbackSerializer, CommandResponseSerializer, ComparisonResponseSerializer, ComparisonSerializer,
    DraftSerializer, OptionsResponseSerializer, OptionsSerializer, OverviewResponseSerializer, PageSerializer,
    PrepareRollbackSerializer, PublishSerializer, StrictSerializer, VersionResponseSerializer,
)
from .strategy_comparisons import create_strategy_comparison, get_strategy_comparison
from .strategy_persistence import StrategyConflict
from .strategy_services import (
    create_strategy_draft, prepare_strategy_rollback, publish_strategy, recover_strategy_command, rollback_strategy,
)


class StrategyCSRFError(exceptions.PermissionDenied):
    default_code = "CSRF_FAILED"
    default_detail = "اعتبارسنجی امنیتی درخواست انجام نشد؛ صفحه را دوباره باز کنید."


class StrategySessionAuthentication(SessionAuthentication):
    def authenticate_header(self, request):
        return "Session"  # Distinguish missing authentication (401) from denied capability (403).

    def enforce_csrf(self, request):
        try:
            super().enforce_csrf(request)
        except exceptions.PermissionDenied:
            raise StrategyCSRFError() from None  # Preserve the standard CSRF validator; redact its diagnostics.


class StrategyViewPermission(BasePermission):
    def has_permission(self, request, view):
        return can_view_strategy(request.user)


class StrategyManagePermission(BasePermission):
    def has_permission(self, request, view):
        return can_manage_strategy(request.user)


class StrategyAPIView(APIView):
    authentication_classes = [StrategySessionAuthentication]
    renderer_classes = [JSONRenderer]
    parser_classes = [JSONParser]

    def get_permissions(self):
        capability = StrategyViewPermission if self.request.method in ("GET", "HEAD", "OPTIONS") else StrategyManagePermission
        return [IsAuthenticated(), capability()]

    def validated(self, cls, *, query=False):
        data = self.request.query_params if query else self.request.data
        if query:
            if any(len(values) != 1 for _, values in data.lists()):
                raise serializers.ValidationError("پارامتر تکراری معتبر نیست.")
            data = data.dict()
        serializer = cls(data=data)
        serializer.is_valid(raise_exception=True)
        return dict(serializer.validated_data)

    def handle_exception(self, exc):
        fields = None
        if isinstance(exc, StrategyCSRFError):
            code, status, detail = "CSRF_FAILED", 403, str(exc.detail)
        elif isinstance(exc, exceptions.NotAuthenticated):
            code, status, detail = "AUTHENTICATION_REQUIRED", 401, "ابتدا وارد حساب کاربری شوید."
        elif isinstance(exc, (PermissionDenied, exceptions.PermissionDenied)):
            code, status, detail = "ACCESS_DENIED", 403, "دسترسی به این عملیات مدیریتی مجاز نیست."
        elif isinstance(exc, (ObjectDoesNotExist, Http404, exceptions.NotFound)):
            code, status, detail = "NOT_FOUND", 404, "اطلاعات درخواستی در دسترس نیست."
        elif isinstance(exc, StrategyConflict):
            candidate = exc.messages[0] if len(exc.messages) == 1 else "STRATEGY_CONFLICT"
            code = candidate if re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", candidate) else "STRATEGY_CONFLICT"
            status, detail = 409, "وضعیت سیاست یا داده‌های مقایسه تغییر کرده است؛ نتیجهٔ فرمان را بررسی و در صورت نیاز دوباره مرور کنید."
        elif isinstance(exc, exceptions.ValidationError):
            code, status, detail = "INVALID_INPUT", 400, "ساختار یا مقادیر درخواست معتبر نیست."
            fields = exc.get_codes()  # No English/internal model diagnostics or source values.
        elif isinstance(exc, ValidationError):
            evidence = (getattr(exc, "code", None) in {"INVALID_STRATEGY_EVIDENCE", "INVALID_COMPARISON_EVIDENCE", "INVALID_POLICY_VERSION"}
                        or bool(set(getattr(exc, "error_dict", {})) & {"input_digest", "output_digest", "intent_fingerprint", "config_hash"}))
            code, status = ("INVALID_STRATEGY_EVIDENCE", 409) if evidence else ("INVALID_INPUT", 400)
            detail = "شواهد سیاست معتبر نیست؛ عملیات انجام نشد." if evidence else "اطلاعات درخواست معتبر نیست."
        elif isinstance(exc, IntegrityError):
            code, status, detail = "STRATEGY_CONFLICT", 409, "عملیات به دلیل تعارض وضعیت انجام نشد."
        elif isinstance(exc, DatabaseError):
            code, status, detail = "STRATEGY_NOT_READY", 503, "زیرساخت راهبرد آماده نیست؛ عملیات انجام نشد."
        elif isinstance(exc, exceptions.MethodNotAllowed):
            code, status, detail = "METHOD_NOT_ALLOWED", 405, "این روش درخواست مجاز نیست."
        elif isinstance(exc, (exceptions.ParseError, exceptions.UnsupportedMediaType)):
            code, status, detail = "INVALID_INPUT", exc.status_code, "بدنهٔ درخواست باید JSON معتبر باشد."
        else:
            return super().handle_exception(exc)
        body = {"code": code, "detail": detail}
        if fields is not None:
            body["errors"] = fields
        response = Response(body, status=status)
        if status == 401:
            response["WWW-Authenticate"] = "Session"
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store, private"
        return response

    def command_response(self, result, *, created=False):
        body = CommandResponseSerializer({"event_id": result.event.pk, "operation": result.event.operation, "result": result.event.result}).data
        return Response(body, status=201 if created and not result.replayed else 200,
                        headers={"Idempotent-Replayed": "true" if result.replayed else "false"})


class StrategyOverviewView(StrategyAPIView):
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        self.validated(StrictSerializer, query=True)
        return Response(OverviewResponseSerializer(reads.overview(request.user)).data)


class StrategyOptionsView(StrategyAPIView):
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        return Response(OptionsResponseSerializer(reads.options(request.user, **self.validated(OptionsSerializer, query=True))).data)


class StrategyVersionsView(StrategyAPIView):
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        data = reads.versions(request.user, **self.validated(PageSerializer, query=True))
        data["results"] = VersionResponseSerializer(data["results"], many=True).data
        return Response(data)


class StrategyDraftView(StrategyAPIView):
    http_method_names = ["post", "options"]

    def post(self, request):
        return self.command_response(create_strategy_draft(actor=request.user, **self.validated(DraftSerializer)), created=True)


class StrategyComparisonsView(StrategyAPIView):
    http_method_names = ["post", "options"]

    def post(self, request):
        return self.command_response(create_strategy_comparison(actor=request.user, **self.validated(ComparisonSerializer)), created=True)


class StrategyComparisonView(StrategyAPIView):
    http_method_names = ["get", "head", "options"]

    def get(self, request, comparison_id):
        data = get_strategy_comparison(actor=request.user, comparison_id=comparison_id)
        data["source_fingerprint"] = data["inputs"]["source_fingerprint"]
        data["quotes"] = data["inputs"]["capture"]["quotes"]
        data["availability_scope"] = data["inputs"]["capture"]["availability_scope"]
        data["labels"] = reads.frozen_comparison_labels(data)
        return Response(ComparisonResponseSerializer(data).data)


class StrategyPublishView(StrategyAPIView):
    http_method_names = ["post", "options"]

    def post(self, request):
        return self.command_response(publish_strategy(actor=request.user, **self.validated(PublishSerializer)))


class StrategyRollbackView(StrategyAPIView):
    http_method_names = ["post", "options"]

    def post(self, request):
        cls = ActivateRollbackSerializer if isinstance(request.data, dict) and request.data.get("action") == "ACTIVATE" else PrepareRollbackSerializer
        data = self.validated(cls)
        action = data.pop("action")
        service = rollback_strategy if action == "ACTIVATE" else prepare_strategy_rollback
        return self.command_response(service(actor=request.user, **data), created=action == "PREPARE")


class StrategyCommandView(StrategyAPIView):
    http_method_names = ["get", "head", "options"]

    def get(self, request, command_uuid):
        command_uuid = serializers.UUIDField().run_validation(command_uuid)
        data = recover_strategy_command(actor=request.user, command_uuid=command_uuid)
        if data is None:
            raise Http404
        return Response(data)
