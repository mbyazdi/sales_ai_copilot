"""Session/CSRF protected review and submission, separate from basket recovery."""
from rest_framework import serializers
from rest_framework.response import Response

from apps.recommendations.feedback_serializers import StrictIntegerField
from .basket_serializers import BasketCommandSerializer
from .basket_views import BasketAPIView
from .submission import SubmissionConflict, review_request, submit_request


class SubmitCommandSerializer(BasketCommandSerializer):
    expected_request_revision = StrictIntegerField(min_value=0, max_value=9223372036854775806)
    accepted_review_fingerprint = serializers.RegexField(r"\A[0-9a-f]{64}\Z", max_length=64)


class RequestReviewAPIView(BasketAPIView):
    def get(self, request, visit_id):
        return self.run(lambda: Response(review_request(request.user, request.query_params.get("customer_code", ""), visit_id)))


class RequestSubmitAPIView(BasketAPIView):
    http_method_names = ["post", "options"]

    def post(self, request, visit_id):
        serializer = SubmitCommandSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"code": "INVALID_INPUT", "detail": "اطلاعات تأیید درخواست معتبر نیست.",
                             "errors": serializer.errors}, status=400)

        def apply():
            try:
                body, status, replayed = submit_request(request.user, visit_id, serializer.validated_data)
            except SubmissionConflict as error:
                return Response({"code": error.code, "detail": error.detail, "review": error.review}, status=409)
            return Response(body, status=status, headers={"Idempotent-Replayed": "true" if replayed else "false"})
        return self.run(apply)
