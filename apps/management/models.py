"""Strategy persistence only. Nothing evaluates, publishes or refreshes on import."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, router
from django.db.models import F, Q

from .strategy_access import require_strategy_manager
from .strategy_serialization import (
    ALGORITHM_VERSION, canonical_value, configuration_fingerprint, fingerprint, normalize_config,
)


class StrategyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Use the strategy command/CAS boundary.")

    def delete(self):
        raise ValidationError("Strategy evidence and its head cannot be deleted.")

    def bulk_create(self, objs, **kwargs):
        raise ValidationError("Bulk creation bypasses strategy integrity.")

    def bulk_update(self, objs, fields, **kwargs):
        raise ValidationError("Bulk updates bypass strategy integrity.")


class StrategyRecord(models.Model):
    objects = StrategyQuerySet.as_manager()

    class Meta:
        abstract = True
        base_manager_name = "objects"
        default_manager_name = "objects"

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        if not self._state.adding or (self.pk and type(self).objects.using(using).filter(pk=self.pk).exists()):
            raise ValidationError("Strategy records cannot be overwritten; use a new immutable record or head CAS.")
        self._state.db = using
        for field in self._meta.fields:
            if isinstance(field, models.JSONField):
                setattr(self, field.attname, canonical_value(getattr(self, field.attname)))
        self.full_clean()
        kwargs["using"] = using
        kwargs["force_insert"] = True  # Never fall back to UPDATE on a colliding supplied PK.
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Strategy records cannot be deleted.")


def _object(value, field):
    if not isinstance(value, dict) or not value:
        raise ValidationError({field: "A nonempty evidence object is required."})
    return canonical_value(value)


def _digest(instance, field, expected):
    supplied = getattr(instance, field)
    if supplied and supplied != expected:
        raise ValidationError({field: "Evidence digest mismatch."})
    setattr(instance, field, expected)


def _same_policy(instance, *fields):
    for field in fields:
        identity = getattr(instance, field + "_id")
        if identity:
            target = instance._meta.get_field(field).remote_field.model
            policy_id = target.objects.using(instance._state.db or "default").filter(pk=identity).values_list("policy_id", flat=True).first()
            if policy_id != instance.policy_id:
                raise ValidationError({field: "Reference is missing or belongs to another policy."})


class StrategyPolicy(StrategyRecord):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    revision = models.PositiveBigIntegerField(default=0)
    active_version = models.ForeignKey("StrategyPolicyVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="active_heads")
    draft_version = models.ForeignKey("StrategyPolicyVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="draft_heads")

    class Meta(StrategyRecord.Meta):
        constraints = [models.CheckConstraint(condition=Q(pk=1), name="strategy_single_global_head")]

    def clean(self):
        if self._state.adding and (self.revision != 0 or self.active_version_id or self.draft_version_id):
            raise ValidationError("A new policy head must be empty at revision zero.")
        for field in ("active_version", "draft_version"):
            if getattr(self, field + "_id") and getattr(self, field).policy_id != self.pk:
                raise ValidationError({field: "Version belongs to another policy."})


class StrategyPolicyVersion(StrategyRecord):
    policy = models.ForeignKey(StrategyPolicy, on_delete=models.PROTECT, related_name="versions")
    config = models.JSONField()
    algorithm_version = models.CharField(max_length=64, default=ALGORITHM_VERSION)
    config_hash = models.CharField(max_length=64, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="strategy_versions")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(StrategyRecord.Meta):
        ordering = ["pk"]
        constraints = [models.CheckConstraint(condition=~Q(pk=F("parent_id")), name="strategy_version_not_self_parent")]

    def clean(self):
        self.config = normalize_config(self.config)
        _digest(self, "config_hash", configuration_fingerprint(self.config, self.algorithm_version))
        _same_policy(self, "parent")
        if self._state.adding:
            require_strategy_manager(self.author_id, self._state.db or "default")
            from apps.products.models import Brand, Category, Product
            from apps.promotions.models import Promotion
            using = self._state.db or "default"
            for scope, model in (("PRODUCT", Product), ("BRAND", Brand), ("CATEGORY", Category)):
                ids = {r["scope_id"] for r in self.config["priority_rules"] if r["scope_type"] == scope}
                if ids and set(model.objects.using(using).filter(pk__in=ids).values_list("pk", flat=True)) != ids:
                    raise ValidationError({"config": "Unknown priority reference."})
            ids = {r["promotion_id"] for r in self.config["promotion_rules"]}
            if ids and set(Promotion.objects.using(using).filter(pk__in=ids).values_list("pk", flat=True)) != ids:
                raise ValidationError({"config": "Unknown promotion reference."})


class StrategyComparison(StrategyRecord):
    policy = models.ForeignKey(StrategyPolicy, on_delete=models.PROTECT, related_name="comparisons")
    before_version = models.ForeignKey(StrategyPolicyVersion, null=True, blank=True, on_delete=models.PROTECT, related_name="before_comparisons")
    after_version = models.ForeignKey(StrategyPolicyVersion, on_delete=models.PROTECT, related_name="after_comparisons")
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="strategy_comparisons")
    salesperson = models.ForeignKey("visits.Salesperson", on_delete=models.PROTECT, related_name="strategy_comparisons")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="strategy_comparisons")
    evaluation_date = models.DateField()
    source_version = models.CharField(max_length=100)
    inputs = models.JSONField()
    outputs = models.JSONField()
    input_digest = models.CharField(max_length=64, blank=True)
    output_digest = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(StrategyRecord.Meta):
        ordering = ["pk"]

    def clean(self):
        _same_policy(self, "before_version", "after_version")
        self.inputs, self.outputs = _object(self.inputs, "inputs"), _object(self.outputs, "outputs")
        _digest(self, "input_digest", fingerprint({
            "policy": self.policy_id, "before_version": self.before_version_id, "after_version": self.after_version_id,
            "customer": self.customer_id, "salesperson": self.salesperson_id, "date": self.evaluation_date,
            "source_version": self.source_version, "inputs": self.inputs,
        }))
        _digest(self, "output_digest", fingerprint({"input_digest": self.input_digest, "outputs": self.outputs}))
        if self._state.adding:
            using = self._state.db or "default"
            require_strategy_manager(self.author_id, using)
            from apps.visits.models import CustomerAssignment
            if not CustomerAssignment.objects.using(using).filter(
                customer_id=self.customer_id, salesperson_id=self.salesperson_id, is_active=True,
                customer__is_active=True, salesperson__is_active=True, start_date__lte=self.evaluation_date,
            ).filter(Q(end_date__isnull=True) | Q(end_date__gte=self.evaluation_date)).exists():
                raise ValidationError("Comparison requires a genuine active assignment on its evaluation date.")


class StrategyPolicyEvent(StrategyRecord):
    class Operation(models.TextChoices):
        SAVE_DRAFT = "SAVE_DRAFT", "Save draft"
        PREVIEW = "PREVIEW", "Preview"
        PUBLISH = "PUBLISH", "Publish"
        ROLLBACK = "ROLLBACK", "Rollback"

    policy = models.ForeignKey(StrategyPolicy, on_delete=models.PROTECT, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="strategy_events")
    command_uuid = models.UUIDField()
    operation = models.CharField(max_length=20, choices=Operation.choices)
    expected_revision = models.PositiveBigIntegerField()
    applied_revision = models.PositiveBigIntegerField()
    intent = models.JSONField()
    intent_fingerprint = models.CharField(max_length=64, blank=True)
    version = models.ForeignKey(StrategyPolicyVersion, on_delete=models.PROTECT, related_name="events")
    comparison = models.ForeignKey(StrategyComparison, null=True, blank=True, on_delete=models.PROTECT, related_name="events")
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(StrategyRecord.Meta):
        ordering = ["pk"]
        constraints = [
            models.UniqueConstraint(fields=["policy", "command_uuid"], name="strategy_unique_command"),
            models.UniqueConstraint(fields=["policy", "applied_revision"], condition=~Q(operation="PREVIEW"), name="strategy_unique_write_revision"),
            models.CheckConstraint(condition=Q(operation__in=["SAVE_DRAFT", "PREVIEW", "PUBLISH", "ROLLBACK"]), name="strategy_valid_operation"),
            models.CheckConstraint(condition=Q(operation="PREVIEW", applied_revision=F("expected_revision")) | (~Q(operation="PREVIEW") & Q(applied_revision=F("expected_revision") + 1)), name="strategy_event_revision_step"),
            models.CheckConstraint(condition=Q(operation="SAVE_DRAFT") | Q(comparison__isnull=False), name="strategy_event_comparison_required"),
        ]

    def clean(self):
        _same_policy(self, "version", "comparison")
        if self.comparison_id and self.comparison.after_version_id != self.version_id:
            raise ValidationError("Event version must match the compared candidate.")
        self.intent, self.result = _object(self.intent, "intent"), _object(self.result, "result")
        _digest(self, "intent_fingerprint", fingerprint({
            "policy": self.policy_id, "actor": self.actor_id, "operation": self.operation,
            "expected_revision": self.expected_revision, "intent": self.intent,
        }))
        if self._state.adding:
            using = self._state.db or "default"
            require_strategy_manager(self.actor_id, using)
            # Exact creation revision; historical validation never requires equality.
            revision = StrategyPolicy.objects.using(using).filter(pk=self.policy_id).values_list("revision", flat=True).first()
            if self.applied_revision != revision:
                raise ValidationError("Event must record the head revision at creation.")
