"""Sales Request persistence only; amounts are supplied snapshots, never calculated."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models

from .model_guards import AppendOnlyModel, GuardedModel, RequestQuerySet, assert_visit_not_closed, validate_snapshot


class SalesRequest(GuardedModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "پیش‌نویس"
        SUBMITTED = "SUBMITTED", "ثبت‌شده"

    visit = models.OneToOneField("visits.Visit", on_delete=models.PROTECT, related_name="sales_request")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    revision = models.PositiveBigIntegerField(default=0)
    number = models.CharField(max_length=64, unique=True, null=True, blank=True)
    submission_key = models.UUIDField(unique=True, null=True, blank=True)
    submission_intent_hash = models.CharField(
        max_length=64, null=True, blank=True,
        validators=[RegexValidator(r"^[0-9a-f]{64}$", "Expected a SHA256 intent fingerprint.")],
    )
    note = models.CharField(max_length=500, blank=True)
    base_total = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    discount_total = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    final_total = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    currency = models.CharField(max_length=10, choices=[("TOMAN", "تومان")], null=True, blank=True)
    customer_snapshot = models.JSONField(default=dict, blank=True)
    salesperson_snapshot = models.JSONField(default=dict, blank=True)
    pricing_snapshot = models.JSONField(default=dict, blank=True)
    prepared_message_snapshot = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = RequestQuerySet.as_manager()

    class Meta:
        verbose_name = "درخواست فروش"
        verbose_name_plural = "درخواست‌های فروش"
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=["DRAFT", "SUBMITTED"]), name="sr_valid_status"),
            models.CheckConstraint(condition=models.Q(revision__gte=0), name="sr_nonnegative_revision"),
            models.CheckConstraint(condition=models.Q(number__isnull=True) | ~models.Q(number=""), name="sr_number_not_empty"),
            models.CheckConstraint(condition=models.Q(currency__isnull=True) | models.Q(currency="TOMAN"), name="sr_currency_toman"),
            models.CheckConstraint(condition=models.Q(base_total__isnull=True) | models.Q(base_total__gte=0), name="sr_base_nonnegative"),
            models.CheckConstraint(condition=models.Q(discount_total__isnull=True) | models.Q(discount_total__gte=0), name="sr_discount_nonnegative"),
            models.CheckConstraint(condition=models.Q(final_total__isnull=True) | models.Q(final_total__gte=0), name="sr_final_nonnegative"),
            models.CheckConstraint(
                condition=(models.Q(status="DRAFT", submitted_at__isnull=True) | models.Q(
                    status="SUBMITTED", submitted_at__isnull=False, number__isnull=False,
                    submission_key__isnull=False, submission_intent_hash__isnull=False,
                    base_total__isnull=False, discount_total__isnull=False,
                    final_total__isnull=False, currency="TOMAN",
                )), name="sr_submission_fields",
            ),
        ]

    @property
    def customer(self):
        return self.visit.customer

    @property
    def customer_id(self):
        return self.visit.customer_id

    @property
    def salesperson(self):
        return self.visit.salesperson

    @property
    def salesperson_id(self):
        return self.visit.salesperson_id

    def save(self, *args, **kwargs):
        # Validation must describe every field persisted when submission freezes it.
        if self.status == self.Status.SUBMITTED and kwargs.get("update_fields") is not None:
            raise ValidationError("A submitted Sales Request requires a full guarded save; update_fields is not allowed.")
        return super().save(*args, **kwargs)

    def _assert_writable(self, using):
        if isinstance(self.revision, bool) or not isinstance(self.revision, int):
            raise ValidationError({"revision": "Revision must be an integer."})
        if self.pk:
            previous = type(self).objects.using(using).select_for_update().filter(pk=self.pk).first()
            if previous and previous.status == self.Status.SUBMITTED:
                raise ValidationError("Submitted requests are immutable.")
        assert_visit_not_closed(self.visit_id, using)

    def clean_fields(self, exclude=None):
        if "revision" not in (exclude or ()) and (isinstance(self.revision, bool) or not isinstance(self.revision, int)):
            raise ValidationError({"revision": "Revision must be an integer."})
        return super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        for field in ("customer_snapshot", "salesperson_snapshot", "pricing_snapshot"):
            validate_snapshot(getattr(self, field), field)
        if self.pk:
            previous_visit = type(self).objects.filter(pk=self.pk).values_list("visit_id", flat=True).first()
            if previous_visit is not None and previous_visit != self.visit_id:
                raise ValidationError({"visit": "A request cannot move to another visit."})
        if self.number is not None and not self.number.strip():
            raise ValidationError({"number": "Use NULL until a number exists."})
        if self.status != self.Status.SUBMITTED:
            return
        required = ("number", "submission_key", "submission_intent_hash", "submitted_at", "currency", "prepared_message_snapshot")
        missing = [field for field in required if not getattr(self, field)]
        missing += [field for field in ("base_total", "discount_total", "final_total") if getattr(self, field) is None]
        missing += [field for field in ("customer_snapshot", "salesperson_snapshot", "pricing_snapshot") if not getattr(self, field)]
        if missing:
            raise ValidationError({field: "Required for a submitted snapshot." for field in missing})
        visit_model = self._meta.get_field("visit").remote_field.model
        visit = visit_model.objects.filter(pk=self.visit_id).first()
        if visit is None:
            raise ValidationError({"visit": "The authoritative visit must exist."})
        if self.customer_snapshot.get("id") != visit.customer_id:
            raise ValidationError({"customer_snapshot": "Customer must match the visit."})
        if self.salesperson_snapshot.get("id") != visit.salesperson_id:
            raise ValidationError({"salesperson_snapshot": "Salesperson must match the visit owner."})
        for field, keys in (("customer_snapshot", ("code", "name")), ("salesperson_snapshot", ("employee_code", "name"))):
            if any(not getattr(self, field).get(key) for key in keys):
                raise ValidationError({field: "Preserve the submitted identity labels as well as its ID."})
        selected = list(self.lines.filter(is_selected=True)) if self.pk else []
        if not selected:
            raise ValidationError("A submitted request must have selected line snapshots.")
        for line in selected:
            line.validate_submission_snapshot()
            if line.currency != self.currency:
                raise ValidationError("Line and request snapshot currencies must match.")

    def __str__(self):
        return self.number or f"پیش‌نویس ویزیت {self.visit_id}"


class SalesRequestLine(GuardedModel):
    class SelectionSource(models.TextChoices):
        ORDINARY = "ORDINARY", "انتخاب عادی"
        RECOMMENDATION = "RECOMMENDATION", "پیشنهاد اولویت‌دار"

    sales_request = models.ForeignKey(SalesRequest, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey("products.Product", on_delete=models.PROTECT, related_name="sales_request_lines")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    is_selected = models.BooleanField(default=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    selection_source = models.CharField(max_length=20, choices=SelectionSource.choices, default=SelectionSource.ORDINARY)
    recommendation = models.ForeignKey("recommendations.CustomerRecommendation", on_delete=models.PROTECT, null=True, blank=True, related_name="sales_request_lines")
    product_snapshot = models.JSONField(default=dict, blank=True)
    lineage_snapshot = models.JSONField(default=dict, blank=True)
    eligibility_snapshot = models.JSONField(default=dict, blank=True)
    pricing_snapshot = models.JSONField(default=dict, blank=True)
    base_unit_price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))])
    discount_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    final_unit_price = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    line_total = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))])
    currency = models.CharField(max_length=10, choices=[("TOMAN", "تومان")], null=True, blank=True)
    pricing_source = models.CharField(max_length=100, null=True, blank=True)
    pricing_version = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "قلم درخواست فروش"
        verbose_name_plural = "اقلام درخواست فروش"
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="srl_positive_quantity"),
            models.UniqueConstraint(fields=["sales_request", "product"], condition=models.Q(is_selected=True), name="srl_unique_selected_product"),
            models.CheckConstraint(condition=models.Q(is_selected=True, removed_at__isnull=True) | models.Q(is_selected=False, removed_at__isnull=False), name="srl_removal_fields"),
            models.CheckConstraint(condition=models.Q(selection_source="ORDINARY", recommendation__isnull=True) | models.Q(selection_source="RECOMMENDATION", recommendation__isnull=False), name="srl_lineage_source"),
            models.CheckConstraint(condition=models.Q(currency__isnull=True) | models.Q(currency="TOMAN"), name="srl_currency_toman"),
            models.CheckConstraint(condition=models.Q(base_unit_price__isnull=True) | models.Q(base_unit_price__gte=0), name="srl_base_nonnegative"),
            models.CheckConstraint(condition=models.Q(discount_percentage__isnull=True) | models.Q(discount_percentage__gte=0, discount_percentage__lte=100), name="srl_discount_percent_range"),
            models.CheckConstraint(condition=models.Q(discount_amount__isnull=True) | models.Q(discount_amount__gte=0), name="srl_discount_nonnegative"),
            models.CheckConstraint(condition=models.Q(final_unit_price__isnull=True) | models.Q(final_unit_price__gte=0), name="srl_final_nonnegative"),
            models.CheckConstraint(condition=models.Q(line_total__isnull=True) | models.Q(line_total__gte=0), name="srl_total_nonnegative"),
        ]

    def _assert_writable(self, using):
        if isinstance(self.quantity, bool) or not isinstance(self.quantity, int):
            raise ValidationError({"quantity": "Quantity must be an integer, without truncation."})
        request_ids = {self.sales_request_id}
        if self.pk:
            previous = type(self).objects.using(using).filter(pk=self.pk).first()
            if previous:
                request_ids.add(previous.sales_request_id)
        parents = SalesRequest.objects.using(using).select_for_update().filter(pk__in=request_ids).order_by("pk")
        for parent in parents:
            if parent.status == SalesRequest.Status.SUBMITTED:
                raise ValidationError("Submitted request lines are immutable.")
            assert_visit_not_closed(parent.visit_id, using)

    def clean(self):
        super().clean()
        for field in ("product_snapshot", "lineage_snapshot", "eligibility_snapshot", "pricing_snapshot"):
            validate_snapshot(getattr(self, field), field)
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).first()
            identity = ("sales_request_id", "product_id", "selection_source", "recommendation_id")
            if previous and any(getattr(previous, field) != getattr(self, field) for field in identity):
                raise ValidationError("Existing line identity/selection lineage cannot be reassigned.")
            if previous and previous.lineage_snapshot != self.lineage_snapshot:
                raise ValidationError({"lineage_snapshot": "Selection evidence cannot be rewritten."})
        if self.product_snapshot and self.product_snapshot.get("id") != self.product_id:
            raise ValidationError({"product_snapshot": "Product snapshot identity mismatch."})
        if self.recommendation_id and self.sales_request_id:
            recommendation_model = self._meta.get_field("recommendation").remote_field.model
            recommendation = recommendation_model.objects.filter(pk=self.recommendation_id).first()
            request = SalesRequest.objects.select_related("visit").filter(pk=self.sales_request_id).first()
            if recommendation is None or request is None:
                raise ValidationError("The authoritative request and recommendation must exist.")
            request_customer = request.visit.customer_id
            if recommendation.customer_id != request_customer or recommendation.product_id != self.product_id:
                raise ValidationError({"recommendation": "Recommendation must match request customer and product."})
            if self.lineage_snapshot.get("recommendation_id") != self.recommendation_id:
                raise ValidationError({"lineage_snapshot": "Preserve the linked recommendation identity."})

    def clean_fields(self, exclude=None):
        if "quantity" not in (exclude or ()) and (isinstance(self.quantity, bool) or not isinstance(self.quantity, int)):
            raise ValidationError({"quantity": "Quantity must be an integer, without truncation."})
        return super().clean_fields(exclude=exclude)

    def validate_submission_snapshot(self):
        required = ("base_unit_price", "discount_percentage", "discount_amount", "final_unit_price", "line_total", "currency", "pricing_source", "pricing_version")
        missing = [field for field in required if getattr(self, field) is None or (isinstance(getattr(self, field), str) and not getattr(self, field).strip())]
        if any(not self.product_snapshot.get(key) for key in ("id", "code", "name", "unit")):
            missing.append("product_snapshot")
        if missing:
            raise ValidationError({field: "Required for a submitted line snapshot." for field in missing})

    def __str__(self):
        return f"درخواست {self.sales_request_id} · محصول {self.product_id}"


class SalesRequestAcknowledgement(AppendOnlyModel):
    sales_request = models.OneToOneField(SalesRequest, on_delete=models.PROTECT, related_name="acknowledgement")
    actor = models.ForeignKey("visits.Salesperson", on_delete=models.PROTECT, related_name="sales_request_acknowledgements")
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "تأیید مشاهده درخواست فروش"
        verbose_name_plural = "تأییدهای مشاهده درخواست فروش"

    def clean(self):
        super().clean()
        validate_snapshot(self.metadata, "metadata")
        if self.sales_request_id:
            request = SalesRequest.objects.select_related("visit").filter(pk=self.sales_request_id).first()
            if request is None:
                raise ValidationError({"sales_request": "The request must exist."})
            if request.status != SalesRequest.Status.SUBMITTED:
                raise ValidationError({"sales_request": "Only submitted requests can be acknowledged."})
            if self.actor_id != request.salesperson_id:
                raise ValidationError({"actor": "Acknowledgement actor must be the visit owner."})


class SalesRequestMutationReceipt(AppendOnlyModel):
    """Successful command evidence; replay/authorization belongs to later services.

    Create together with the successful effects in the caller's atomic transaction.
    result preserves the prior canonical response, not a projection of current state.
    """

    class Operation(models.TextChoices):
        ADD_PRODUCT = "ADD_PRODUCT", "افزودن محصول"
        SET_QUANTITY = "SET_QUANTITY", "تغییر تعداد"
        REMOVE_PRODUCT = "REMOVE_PRODUCT", "حذف محصول"
        REJECT_RECOMMENDATION = "REJECT_RECOMMENDATION", "رد پیشنهاد"

    visit = models.ForeignKey("visits.Visit", on_delete=models.PROTECT, related_name="mutation_receipts")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales_request_mutation_receipts")
    command_uuid = models.UUIDField()
    operation = models.CharField(max_length=24, choices=Operation.choices)
    intent_fingerprint = models.CharField(
        max_length=64, validators=[RegexValidator(r"\A[0-9a-f]{64}\Z", "Expected a SHA256 intent fingerprint.")],
    )
    sales_request = models.ForeignKey(SalesRequest, on_delete=models.PROTECT, null=True, blank=True, related_name="mutation_receipts")
    applied_revision = models.PositiveBigIntegerField(null=True, blank=True)
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "رسید اجرای فرمان درخواست فروش"
        verbose_name_plural = "رسیدهای اجرای فرمان درخواست فروش"
        ordering = ["created_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["visit", "command_uuid"], name="srmr_unique_visit_command"),
            models.CheckConstraint(
                condition=models.Q(operation__in=["ADD_PRODUCT", "SET_QUANTITY", "REMOVE_PRODUCT", "REJECT_RECOMMENDATION"]),
                name="srmr_valid_operation",
            ),
            models.CheckConstraint(condition=~models.Q(intent_fingerprint=""), name="srmr_intent_not_empty"),
            models.CheckConstraint(
                condition=(models.Q(sales_request__isnull=True, applied_revision__isnull=True) | models.Q(
                    sales_request__isnull=False, applied_revision__isnull=False, applied_revision__gte=0,
                )), name="srmr_revision_request_pair",
            ),
        ]

    def clean_fields(self, exclude=None):
        if "applied_revision" not in (exclude or ()) and self.applied_revision is not None:
            if isinstance(self.applied_revision, bool) or not isinstance(self.applied_revision, int):
                raise ValidationError({"applied_revision": "Revision must be an integer."})
        return super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        validate_snapshot(self.result, "result")
        if not self.result:
            raise ValidationError({"result": "Preserve the canonical successful result."})
        if self.visit_id and self.actor_id:
            visit_model = self._meta.get_field("visit").remote_field.model
            owner_user = visit_model.objects.filter(pk=self.visit_id).values_list("salesperson__user_id", flat=True).first()
            if owner_user != self.actor_id:
                raise ValidationError({"actor": "Receipt actor must be the visit owner's authenticated user."})
        if self.sales_request_id:
            request = SalesRequest.objects.filter(pk=self.sales_request_id).values("visit_id", "revision").first()
            if request is None or request["visit_id"] != self.visit_id:
                raise ValidationError({"sales_request": "Receipt request must belong to the same visit."})
            # Existing receipts retain historical revisions as the request advances.
            if self._state.adding and self.applied_revision != request["revision"]:
                raise ValidationError({"applied_revision": "Capture the request revision when the command is applied."})
        elif self.applied_revision is not None:
            raise ValidationError({"applied_revision": "A revision requires a request."})

    def __str__(self):
        return f"ویزیت {self.visit_id} · {self.command_uuid}"
