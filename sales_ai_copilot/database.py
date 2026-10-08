"""Explicit environment database selection; no dotenv loading or connections."""
import os

from django.core.exceptions import ImproperlyConfigured


def _required(environ, name):
    value = environ.get(name, "")
    if not value.strip():
        # Name only: configuration errors must not disclose credential values.
        raise ImproperlyConfigured(f"{name} is required when DB_ENGINE=postgresql.")
    return value


def _positive_integer(environ, name, default, maximum):
    value = environ.get(name, str(default))
    if not value.isascii() or not value.isdecimal() or not 1 <= int(value) <= maximum:
        raise ImproperlyConfigured(f"{name} must be a positive integer within its supported range.")
    return int(value)


def database_configuration(base_dir, environ=None):
    """Preserve SQLite by default; PostgreSQL requires an explicit selector.

    TEST overrides/mirrors are deliberately absent: Django retains separate test
    database naming/creation. Credentials are supplied by the process environment.
    """
    environ = os.environ if environ is None else environ
    engine = environ.get("DB_ENGINE", "sqlite").strip().lower() or "sqlite"
    if engine == "sqlite":
        return {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": base_dir / "db.sqlite3"}}
    if engine != "postgresql":
        raise ImproperlyConfigured("DB_ENGINE must be sqlite or postgresql.")

    name = _required(environ, "POSTGRES_DB")
    user = _required(environ, "POSTGRES_USER")
    password = _required(environ, "POSTGRES_PASSWORD")
    host = environ.get("POSTGRES_HOST", "127.0.0.1").strip()
    if not host:
        raise ImproperlyConfigured("POSTGRES_HOST must not be empty.")
    sslmode = environ.get("POSTGRES_SSLMODE", "prefer").strip().lower()
    if sslmode not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
        raise ImproperlyConfigured("POSTGRES_SSLMODE is not supported.")
    return {
        "default": {
            "ENGINE": "django.db.backends.postgresql", "NAME": name,
            "USER": user, "PASSWORD": password, "HOST": host,
            "PORT": _positive_integer(environ, "POSTGRES_PORT", 5432, 65535),
            "OPTIONS": {
                "sslmode": sslmode,
                "connect_timeout": _positive_integer(environ, "POSTGRES_CONNECT_TIMEOUT", 5, 2147483647),
            },
        },
    }
