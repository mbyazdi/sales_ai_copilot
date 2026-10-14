"""Strict command inputs: absolute quantities, never client monetary values."""
from rest_framework import serializers
from apps.customers.models import Customer
from apps.products.quotes import MAX_QUANTITY
from apps.recommendations.feedback_serializers import StrictIntegerField, StrictTextField


class BasketCommandSerializer(serializers.Serializer):
    customer_code = StrictTextField(max_length=Customer._meta.get_field("customer_code").max_length)
    command_uuid = serializers.UUIDField()
    expected_request_revision = StrictIntegerField(min_value=0, max_value=9223372036854775806, allow_null=True)
    catalog_context = StrictTextField(max_length=100000)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["ساختار فرمان یا فیلدهای آن معتبر نیست."]})
        return super().to_internal_value(data)


class PricedBasketCommandSerializer(BasketCommandSerializer):
    quantity = StrictIntegerField(min_value=1, max_value=MAX_QUANTITY)
    accepted_quote_fingerprint = serializers.RegexField(r"\A[0-9a-f]{64}\Z", max_length=64)


class AddBasketCommandSerializer(PricedBasketCommandSerializer):
    product_id = StrictIntegerField(min_value=1, max_value=999999999999999999)
