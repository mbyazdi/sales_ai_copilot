"""Operator-only frozen demo configuration loading; no web entry point.

Callers must hold explicit write/rollback authorization for the named database.
DEMO-06B exercises writes only in isolated PostgreSQL databases. This module does
not change product master data, history, inventory, recommendations or requests.
"""
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from django.db import connection, transaction

from .models import Product, ProductDemoPrice


DATASET_PATH = Path(__file__).parent / "data/demo_prices_DEMO_06_V1.json"
DATASET_SHA256 = "1dfddd34582dc9d3194ae0083bc918ab41cc5dcd5ec5216d7b6d3c5762b51648"


class DemoPriceLoadError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DemoPriceLoadError("DUPLICATE_DATASET_KEY")
        result[key] = value
    return result


def read_frozen_dataset(path=DATASET_PATH):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, json.JSONDecodeError) as error:
        raise DemoPriceLoadError("INVALID_DATASET") from error
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if hashlib.sha256(canonical).hexdigest() != DATASET_SHA256:
        raise DemoPriceLoadError("DATASET_CHECKSUM_MISMATCH")
    return data


def _database(expected_database):
    if not isinstance(expected_database, str) or not expected_database or connection.vendor != "postgresql":
        raise DemoPriceLoadError("EXPLICIT_POSTGRESQL_TARGET_REQUIRED")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        actual = cursor.fetchone()[0]
    if actual != expected_database:
        raise DemoPriceLoadError("DATABASE_MISMATCH")
    return actual


def _snapshot(row, code):
    return {
        "id": row.pk, "product_id": row.product_id, "product_code": code,
        "base_price": format(row.base_price, ".2f"), "currency": row.currency,
        "source": row.source, "source_version": row.source_version,
        "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(),
    }


def _plan(data, *, lock=False):
    products = Product.objects.filter(product_code__in=data["prices"]).order_by("product_code")
    if lock:
        products = products.select_for_update()
    products = list(products)
    if {p.product_code for p in products} != set(data["prices"]):
        raise DemoPriceLoadError("PRODUCT_COVERAGE_MISMATCH")
    if any(not p.is_active or p.unit != data["unit"] or p.package_size != data["package_size"] for p in products):
        raise DemoPriceLoadError("PRODUCT_UNIT_OR_STATUS_MISMATCH")
    rows = ProductDemoPrice.objects.filter(product_id__in=[p.pk for p in products])
    if lock:
        rows = rows.select_for_update()
    by_product = {row.product_id: row for row in rows}
    create, skip = [], []
    for product in products:
        desired = (Decimal(data["prices"][product.product_code]), data["currency"], data["source"], data["source_version"])
        row = by_product.get(product.pk)
        if row is None:
            create.append(product)
        elif (row.base_price, row.currency, row.source, row.source_version) == desired:
            skip.append(product.product_code)
        else:
            # No implicit replacement even when the existing row uses our version.
            raise DemoPriceLoadError("EXISTING_PRICE_CONFLICT")
    return products, create, skip


def plan_demo_prices(*, expected_database):
    """Read-only preflight. No row locks, changes or automatic migrations."""
    data = read_frozen_dataset()
    database = _database(expected_database)
    products, create, skip = _plan(data)
    return {"database": database, "dataset_sha256": DATASET_SHA256,
            "source": data["source"], "source_version": data["source_version"],
            "create_codes": [p.product_code for p in create], "skip_codes": skip,
            "product_ids": {p.product_code: p.pk for p in products}}


def apply_demo_prices(*, expected_database):
    """Atomic create-or-skip only; caller supplies already-authorized DB identity."""
    data = read_frozen_dataset()
    database = _database(expected_database)
    with transaction.atomic():
        _, create, skip = _plan(data, lock=True)
        snapshots = []
        for product in create:
            row = ProductDemoPrice.objects.create(
                product=product, base_price=Decimal(data["prices"][product.product_code]),
                currency=data["currency"], source=data["source"], source_version=data["source_version"],
            )
            snapshots.append(_snapshot(row, product.product_code))
        return {"database": database, "dataset_sha256": DATASET_SHA256,
                "created_count": len(snapshots), "skipped_count": len(skip),
                "created": snapshots, "skipped_codes": skip}


def rollback_demo_prices(report, *, expected_database):
    """Rollback a trusted protected operator report; never overwrite later edits.

    Only matching rows CREATED by that load can be removed. Matching pre-existing
    rows skipped by the load are not in the write set. No price updates supported.
    """
    data = read_frozen_dataset()
    database = _database(expected_database)
    if report.get("database") != database or report.get("dataset_sha256") != DATASET_SHA256:
        raise DemoPriceLoadError("ROLLBACK_REPORT_MISMATCH")
    snapshots = report.get("created", [])
    codes = [s["product_code"] for s in snapshots]
    if len(codes) != len(set(codes)) or not set(codes) <= set(data["prices"]):
        raise DemoPriceLoadError("ROLLBACK_REPORT_MISMATCH")
    for snapshot in snapshots:
        if (snapshot.get("base_price"), snapshot.get("currency"), snapshot.get("source"), snapshot.get("source_version")) != (
            format(Decimal(data["prices"][snapshot["product_code"]]), ".2f"),
            data["currency"], data["source"], data["source_version"],
        ):
            raise DemoPriceLoadError("ROLLBACK_REPORT_MISMATCH")
    with transaction.atomic():
        products = list(Product.objects.select_for_update().filter(product_code__in=codes).order_by("product_code"))
        if {p.product_code for p in products} != set(codes):
            raise DemoPriceLoadError("ROLLBACK_CONFLICT")
        by_code = {p.product_code: p for p in products}
        rows = {row.product_id: row for row in ProductDemoPrice.objects.select_for_update().filter(product_id__in=[p.pk for p in products])}
        owned_ids, absent = [], []
        for snapshot in snapshots:
            product = by_code[snapshot["product_code"]]
            if product.pk != snapshot["product_id"]:
                raise DemoPriceLoadError("ROLLBACK_CONFLICT")
            row = rows.get(product.pk)
            if row is None:
                absent.append(product.product_code)
            elif _snapshot(row, product.product_code) != snapshot:
                raise DemoPriceLoadError("ROLLBACK_CONFLICT")
            else:
                owned_ids.append(row.pk)
        ProductDemoPrice.objects.filter(pk__in=owned_ids).delete()
        return {"deleted_count": len(owned_ids), "already_absent_codes": absent}
