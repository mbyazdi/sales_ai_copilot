"""Read-only static demo imagery; never product identity or business authority."""
import hashlib
import json
from functools import lru_cache
from pathlib import PurePosixPath
from urllib.parse import urlsplit

from django.conf import settings
from django.templatetags.static import static


@lru_cache(maxsize=1)
def _manifest():
    try:
        document = json.loads((settings.BASE_DIR / "static/demo/manifest.v2.json").read_text(encoding="utf-8"))
        return document if document.get("schema_version") == 2 else {}
    except (OSError, ValueError):
        return {}


def _public_url(value):
    parts = urlsplit(value or "")
    return value if parts.scheme == "https" and parts.netloc and not parts.username else None


@lru_cache(maxsize=128)
def _verified_file(relative_path, checksum):
    path = PurePosixPath(relative_path)
    if path.is_absolute() or ".." in path.parts or "\\" in relative_path:
        return False
    if not relative_path.startswith("static/demo/") or path.suffix != ".webp":
        return False
    root = (settings.BASE_DIR / "static/demo").resolve()
    file = (settings.BASE_DIR / relative_path).resolve()
    if not file.is_relative_to(root):
        return False
    try:
        return hashlib.sha256(file.read_bytes()).hexdigest() == checksum
    except OSError:
        return False


def demo_image(kind, code, variant="thumb"):
    """Fail closed to the existing fallback, with no database access or writes."""
    missing = {"url": None, "state": "MISSING"}
    entry = _manifest().get(kind, {}).get(str(code), {})
    if not entry.get("demo_enabled") or entry.get("status") not in {"A", "B"}:
        return missing
    file = entry.get("files", {}).get(variant, {})
    path, checksum = file.get("path", ""), file.get("sha256", "")
    if not path or not checksum or not _verified_file(path, checksum):
        return missing
    credit = entry.get("attribution") or {}
    generated = entry.get("image_type") == "AI_GENERATED_REPRESENTATIVE"
    label = ("تصویر نمونهٔ فروشگاه" if kind == "stores" else
             "تصویر نمونهٔ محصول؛ مدل دقیق تأیید نشده") if entry["status"] == "B" else ""
    return {
        "url": static(path.removeprefix("static/")),
        "state": "GENERATED_REPRESENTATIVE" if generated else ("REPRESENTATIVE" if entry["status"] == "B" else "VERIFIED"),
        "label": label,
        "description": entry.get("description", "") if generated else "",
        "credit": {
            "author": credit.get("author", ""),
            "source_url": _public_url(credit.get("source")),
            "licence": credit.get("licence", ""),
            "licence_url": _public_url(credit.get("licence_url")),
            "additional_source_url": _public_url(credit.get("additional_source_url")),
            "changes": "نمونهٔ تولیدشده؛ مدل یا محل واقعی تأیید نشده است." if generated else "اندازه و قالب تصویر تغییر کرده است.",
        },
    }
