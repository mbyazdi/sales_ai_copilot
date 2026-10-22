"""Small V1 transport contracts; business validation stays in strategy services."""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.recommendations.feedback_serializers import StrictIntegerField
from .strategy_serialization import normalize_config


class StrictSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"non_field_errors": ["ساختار درخواست معتبر نیست."]}, code="invalid_fields")
        return super().to_internal_value(data)


class CommandUUIDField(serializers.UUIDField):
    def to_internal_value(self, data):
        if type(data) is not str:
            raise serializers.ValidationError("شناسهٔ فرمان باید متن باشد.", code="invalid")
        return super().to_internal_value(data)


class CommandSerializer(StrictSerializer):
    command_uuid = CommandUUIDField()
    expected_revision = StrictIntegerField(min_value=0, max_value=2**63 - 2)


class DraftSerializer(CommandSerializer):
    config = serializers.JSONField()

    def validate_config(self, value):
        try:
            return normalize_config(value)
        except DjangoValidationError:
            raise serializers.ValidationError("تنظیمات سیاست معتبر نیست.", code="invalid_configuration") from None


class ComparisonSerializer(CommandSerializer):
    customer_id = StrictIntegerField(min_value=1, max_value=2**63 - 1)
    salesperson_id = StrictIntegerField(min_value=1, max_value=2**63 - 1)
    proposed_version_id = StrictIntegerField(min_value=1, max_value=2**63 - 1)
    evaluation_date = serializers.DateField(input_formats=["%Y-%m-%d"])
    accepted_source_fingerprint = serializers.RegexField(r"\A[0-9a-f]{64}\Z", max_length=64, trim_whitespace=False)


class PublishSerializer(CommandSerializer):
    draft_version_id = StrictIntegerField(min_value=1, max_value=2**63 - 1)
    comparison_id = StrictIntegerField(min_value=1, max_value=2**63 - 1)
    accepted_comparison_digest = serializers.RegexField(r"\A[0-9a-f]{64}\Z", max_length=64, trim_whitespace=False)


class PrepareRollbackSerializer(CommandSerializer):
    action = serializers.ChoiceField(choices=["PREPARE"])
    target_version_id = StrictIntegerField(min_value=1, max_value=2**63 - 1, allow_null=True)


class ActivateRollbackSerializer(PublishSerializer):
    action = serializers.ChoiceField(choices=["ACTIVATE"])


class PageSerializer(StrictSerializer):
    after_id = serializers.IntegerField(min_value=0, max_value=2**63 - 1, default=0)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=50)


class OptionsSerializer(PageSerializer):
    kind = serializers.ChoiceField(choices=["products", "brands", "categories", "promotions", "salespersons", "customers"], required=False)
    customer_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1, required=False)
    salesperson_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1, required=False)
    proposed_version_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1, required=False)
    expected_revision = serializers.IntegerField(min_value=0, max_value=2**63 - 2, required=False)
    evaluation_date = serializers.DateField(input_formats=["%Y-%m-%d"], required=False)

    def validate(self, data):
        context = {"customer_id", "salesperson_id", "proposed_version_id", "expected_revision", "evaluation_date"}
        if {"customer_id", "proposed_version_id", "expected_revision"} & data.keys() and not context <= data.keys():
            raise serializers.ValidationError("زمینهٔ مقایسه باید کامل باشد.", code="incomplete_context")
        if data.get("kind") == "customers" and not {"salesperson_id", "evaluation_date"} <= data.keys():
            raise serializers.ValidationError("فروشنده و تاریخ تخصیص لازم است.", code="assignment_required")
        return data


class VersionResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    parent_id = serializers.IntegerField(allow_null=True)
    author_id = serializers.IntegerField()
    algorithm_version = serializers.CharField()
    config_hash = serializers.CharField()
    config = serializers.JSONField()
    created_at = serializers.DateTimeField()
    published = serializers.BooleanField()


class CommandResponseSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    operation = serializers.CharField()
    result = serializers.JSONField()


class ComparisonResponseSerializer(serializers.Serializer):
    comparison_id = serializers.IntegerField()
    policy_revision = serializers.IntegerField()
    customer_id = serializers.IntegerField()
    salesperson_id = serializers.IntegerField()
    evaluation_date = serializers.CharField()
    before_version_id = serializers.IntegerField(allow_null=True)
    after_version_id = serializers.IntegerField()
    input_digest = serializers.CharField()
    output_digest = serializers.CharField()
    source_fingerprint = serializers.CharField()
    outputs = serializers.JSONField()
    quotes = serializers.JSONField()
    availability_scope = serializers.CharField()
    labels = serializers.JSONField()


class OverviewResponseSerializer(serializers.Serializer):
    schema_version = serializers.IntegerField()
    policy_id = serializers.IntegerField()
    revision = serializers.IntegerField()
    active_version_id = serializers.IntegerField(allow_null=True)
    draft_version_id = serializers.IntegerField(allow_null=True)
    active_config = serializers.JSONField()
    algorithm_version = serializers.CharField()
    version_count = serializers.IntegerField()
    comparison_count = serializers.IntegerField()
    selling_context_integration = serializers.BooleanField()
    impact_available = serializers.BooleanField()
    limitations_fa = serializers.CharField()


class OptionsResponseSerializer(serializers.Serializer):
    schema_version = serializers.IntegerField()
    algorithm_version = serializers.CharField()
    priority_scopes = serializers.ListField(child=serializers.CharField())
    priority_bounds = serializers.ListField(child=serializers.IntegerField())
    target_weight_bounds = serializers.ListField(child=serializers.IntegerField())
    promotion_points_bounds = serializers.ListField(child=serializers.IntegerField())
    adjustment_cap = serializers.IntegerField()
    rollback_actions = serializers.ListField(child=serializers.CharField())
    limitations_fa = serializers.CharField()
    kind = serializers.CharField(required=False)
    results = serializers.ListField(child=serializers.DictField(), required=False)
    next_after_id = serializers.IntegerField(allow_null=True, required=False)
    preview_context = serializers.JSONField(required=False)
