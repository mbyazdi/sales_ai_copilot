"""Strict command input; existing model codes remain authoritative."""
from rest_framework import serializers

from apps.customers.models import Customer
from .models import RecommendationFeedbackEvent


class StrictIntegerField(serializers.IntegerField):
    def to_internal_value(self, data):
        if type(data) is not int:
            raise serializers.ValidationError("مقدار باید عدد صحیح باشد.")
        return super().to_internal_value(data)


class StrictTextField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError("مقدار باید متن باشد.")
        return super().to_internal_value(data)


class FeedbackCommandSerializer(serializers.Serializer):
    customer_code = StrictTextField(max_length=Customer._meta.get_field("customer_code").max_length)
    recommendation_id = StrictIntegerField(min_value=1, max_value=999999999999999999)
    command_uuid = serializers.UUIDField()
    action = serializers.ChoiceField(choices=["REJECTED", "LATER"])
    reason_code = serializers.ChoiceField(choices=RecommendationFeedbackEvent.RejectionReason.values, required=False)
    note = StrictTextField(max_length=200, allow_blank=True, required=False, default="")
    catalog_context = StrictTextField(max_length=100000)
    expected_request_revision = StrictIntegerField(min_value=0, max_value=9223372036854775807, allow_null=True, required=False, default=None)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["ساختار فرمان یا فیلدهای آن معتبر نیست."]})
        return super().to_internal_value(data)

    def validate(self, data):
        if data["action"] == "REJECTED" and "reason_code" not in data:
            raise serializers.ValidationError({"reason_code": "دلیل رد پیشنهاد را انتخاب کنید."})
        if data["action"] == "LATER":
            if data.get("reason_code", "LATER") != "LATER":
                raise serializers.ValidationError({"reason_code": "برای تصمیم بعداً فقط دلیل LATER مجاز است."})
            data["reason_code"] = "LATER"
        return data
