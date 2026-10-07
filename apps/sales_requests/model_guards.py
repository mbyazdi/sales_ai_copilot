"""ORM persistence guards, without basket, pricing or submission operations."""
from django.core.exceptions import ValidationError
from django.db import models, router, transaction


class GuardedQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Use validated model saves for these records.")

    def bulk_create(self, objs, **kwargs):
        raise ValidationError("Bulk creation bypasses model integrity checks.")

    def bulk_update(self, objs, fields, **kwargs):
        raise ValidationError("Bulk updates bypass snapshot protection.")

    def delete(self):
        with transaction.atomic(using=self.db):
            # Lock where supported; SQLite concurrency also needs later revisions.
            records = list(self.select_for_update())
            for record in records:
                record._assert_writable(self.db)
            return super().delete()


class RequestQuerySet(GuardedQuerySet):
    def update(self, **kwargs):
        if not kwargs or not set(kwargs).issubset({"revision", "updated_at"}):
            return super().update(**kwargs)
        if self.filter(status="SUBMITTED").exists():
            raise ValidationError("Submitted requests are immutable.")
        if self.filter(visit__status__in=["COMPLETED", "CANCELLED"]).exists():
            raise ValidationError("Closed-visit drafts are read-only.")
        # The SQL predicate protects a row that becomes submitted after the read.
        # A future service must additionally supply its expected revision.
        return models.QuerySet.update(self.filter(status="DRAFT", visit__status__in=["PLANNED", "IN_PROGRESS"]), **kwargs)


class GuardedModel(models.Model):
    objects = GuardedQuerySet.as_manager()

    class Meta:
        abstract = True

    def _assert_writable(self, using):
        raise NotImplementedError

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            self._assert_writable(using)
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        using = using or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            self._assert_writable(using)
            return super().delete(using=using, keep_parents=keep_parents)


class AppendOnlyModel(GuardedModel):
    class Meta:
        abstract = True

    def _assert_writable(self, using):
        if self.pk and type(self).objects.using(using).filter(pk=self.pk).exists():
            raise ValidationError("Historical records cannot be updated or deleted.")


def validate_snapshot(value, field_name):
    if not isinstance(value, dict):
        raise ValidationError({field_name: "Snapshot must be a JSON object."})


def assert_visit_not_closed(visit_id, using):
    from apps.visits.models import Visit

    status = Visit.objects.using(using).filter(pk=visit_id).values_list("status", flat=True).first()
    if status in (Visit.VisitStatus.COMPLETED, Visit.VisitStatus.CANCELLED):
        raise ValidationError("A retained draft for a closed visit is read-only.")
