"""Reference-row locking capability boundary; never grants or installs anything.

PostgreSQL requires the separately installed REFERENCE_LOCKS_V1 functions.
SQLite keeps its existing transaction/CAS behavior (row locking is unavailable).
"""
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import connections
from django.db.transaction import TransactionManagementError

MAX_PRODUCTS = 50
MAX_ID = 9223372036854775807


def _id(value):
    if type(value) is not int or not 0 < value <= MAX_ID:
        raise ValidationError("Invalid reference lock identity.")
    return value


def _connection(using):
    connection = connections[using]
    if not connection.in_atomic_block:
        raise TransactionManagementError("Reference locks require an outer atomic transaction.")
    if connection.vendor not in {"postgresql", "sqlite"}:
        raise ImproperlyConfigured("Reference locking is not configured for this database backend.")
    return connection


def lock_feedback_references(customer_id, recommendation_id, *, using="default"):
    customer_id, recommendation_id = _id(customer_id), _id(recommendation_id)
    connection = _connection(using)
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT sales_ai_locks.lock_feedback_references(%s::bigint, %s::bigint)",
                           [customer_id, recommendation_id])


def lock_submission_references(customer_id, product_ids, *, using="default"):
    customer_id = _id(customer_id)
    if not isinstance(product_ids, (list, tuple)) or len(product_ids) > MAX_PRODUCTS:
        raise ValidationError("Invalid reference lock product list.")
    product_ids = sorted({_id(value) for value in product_ids})
    connection = _connection(using)
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT sales_ai_locks.lock_submission_references(%s::bigint, %s::bigint[])",
                           [customer_id, product_ids])
