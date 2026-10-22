"""Canonical strategy evidence; no evaluation or commercial arithmetic."""
import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from django.core.exceptions import ValidationError


ALGORITHM_VERSION = "SAVED_RANK_OVERLAY_V1"


def canonical_value(value):
    if value is None or type(value) in (str, int, bool):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValidationError("Non-finite decimals are not evidence.")
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return "0" if value == 0 else text
    if isinstance(value, datetime):
        if value.utcoffset() is None:
            raise ValidationError("Evidence timestamps must be timezone-aware.")
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, (date, UUID)):
        return str(value)
    if isinstance(value, dict) and all(type(key) is str for key in value):
        return {key: canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    raise ValidationError("Evidence requires JSON values, exact decimals and aware timestamps; floats are forbidden.")


def canonical_json(value):
    return json.dumps(canonical_value(value), sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def fingerprint(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def neutral_config():
    return {"schema_version": 1, "priority_rules": [], "target_weight": 0, "promotion_rules": []}


def _integer(value, minimum, maximum):
    return type(value) is int and minimum <= value <= maximum


def normalize_config(config):
    """Typed, bounded V1 configuration. Rule arrays are sets, not precedence lists."""
    if not isinstance(config, dict) or set(config) != set(neutral_config()):
        raise ValidationError("Use exactly the V1 configuration fields.")
    if type(config["schema_version"]) is not int or config["schema_version"] != 1:
        raise ValidationError("Unsupported configuration schema.")
    if not _integer(config["target_weight"], 0, 5):
        raise ValidationError("Target weight must be an integer from 0 to 5.")
    normalized = neutral_config()
    normalized["target_weight"] = config["target_weight"]
    for field, keys in (("priority_rules", {"scope_type", "scope_id", "points"}),
                        ("promotion_rules", {"promotion_id", "points"})):
        rules = config[field]
        if not isinstance(rules, list):
            raise ValidationError("Rules must be arrays.")
        seen = set()
        for rule in rules:
            if not isinstance(rule, dict) or set(rule) != keys:
                raise ValidationError("Invalid rule fields.")
            if field == "priority_rules":
                scope = rule["scope_type"]
                if scope not in ("PRODUCT", "BRAND", "CATEGORY") or not _integer(rule["scope_id"], 1, 2**63 - 1):
                    raise ValidationError("Invalid priority scope.")
                identity, maximum = (scope, rule["scope_id"]), 20
            else:
                if not _integer(rule["promotion_id"], 1, 2**63 - 1):
                    raise ValidationError("Invalid promotion identity.")
                identity, maximum = (rule["promotion_id"],), 5
            if identity in seen or not _integer(rule["points"], 0, maximum):
                raise ValidationError("Duplicate rule or out-of-range integer points.")
            seen.add(identity)
            normalized[field].append(dict(rule))
        normalized[field].sort(key=lambda row: (row["scope_type"], row["scope_id"]) if field == "priority_rules" else row["promotion_id"])
    return normalized


def configuration_fingerprint(config, algorithm_version=ALGORITHM_VERSION):
    if algorithm_version != ALGORITHM_VERSION:
        raise ValidationError("Unsupported strategy algorithm.")
    return fingerprint({"algorithm_version": algorithm_version, "config": normalize_config(config)})
