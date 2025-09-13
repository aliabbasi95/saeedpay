# saeedpay/local_settings.py
import os
from pathlib import Path

# Project-specific import (keep as-is if used in admin UI)
from .admin_reorder import ADMIN_REORDER  # noqa: F401

# ──────────────────────────────────────────────────────────────────────────────
# Base paths & optional .env loading in DEV (outside Docker)
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env only in development to ease local runs (no effect in prod)
if os.getenv("DEBUG", "True").lower() == "true":
    try:
        from dotenv import load_dotenv

        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        # python-dotenv is optional; safe to ignore if not installed
        pass


# ──────────────────────────────────────────────────────────────────────────────
# Helper readers
# ──────────────────────────────────────────────────────────────────────────────
def env_bool(name: str, default: str = "False") -> bool:
    """Read a boolean ENV var; supports: 1/true/yes/on (case-insensitive)."""
    return str(os.getenv(name, default)).lower() in ("1", "true", "yes", "on")


def env_list(name: str, default: str = "") -> list[str]:
    """Read a comma-separated ENV var into a trimmed Python list."""
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def env_str(name: str, default=None):
    """Read a string ENV var (or return default)."""
    val = os.getenv(name, default)
    if val is None:
        return default
    return val


# ──────────────────────────────────────────────────────────────────────────────
# Core
# ──────────────────────────────────────────────────────────────────────────────
SECRET_KEY = env_str(
    "SECRET_KEY", "dev-insecure-secret"
)  # MUST override in prod
DEBUG = env_bool("DEBUG", "True")

# Examples:
#   ALLOWED_HOSTS=example.com,api.example.com
#   CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")

# ──────────────────────────────────────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────────────────────────────────────
# Preferred: single DATABASE_URL across envs, e.g.:
#   postgres://USER:PASS@HOST:5432/DBNAME
DATABASE_URL = env_str("DATABASE_URL")
if DATABASE_URL:
    try:
        import dj_database_url

        CONN_AGE = int(env_str("DATABASE_CONN_MAX_AGE", "60") or "60")
        SSL_REQUIRE = env_bool("DATABASE_SSL_REQUIRE", "False")

        DATABASES = {
            "default": dj_database_url.parse(
                DATABASE_URL,
                conn_max_age=CONN_AGE,
                ssl_require=SSL_REQUIRE,
            )
        }
        # Keep long-lived connections healthy (Django 5+)
        DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
    except Exception as exc:
        raise RuntimeError(
            "Please install dj-database-url to use DATABASE_URL."
        ) from exc
else:
    # Dev-friendly default: SQLite
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
        }
    }

# ──────────────────────────────────────────────────────────────────────────────
# Cache / Redis
# ──────────────────────────────────────────────────────────────────────────────
# Put Redis password in the URL when needed:
#   redis://:PASSWORD@redis:6379/0   (no TLS)
#   rediss://:PASSWORD@host:6380/0   (with TLS)
REDIS_URL = env_str("REDIS_URL", "redis://redis:6379/0")

CACHE_DEFAULT_TIMEOUT = int(env_str("CACHE_DEFAULT_TIMEOUT", "300") or "300")

_is_rediss = REDIS_URL.startswith("rediss://")
redis_options = {"CLIENT_CLASS": "django_redis.client.DefaultClient"}
if _is_rediss:
    # Minimal SSL kwargs; adjust cert verification if needed.
    redis_options["CONNECTION_POOL_KWARGS"] = {"ssl_cert_reqs": None}

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "TIMEOUT": CACHE_DEFAULT_TIMEOUT,
        "OPTIONS": redis_options,
        "KEY_PREFIX": "saeedpay",
    }
}

# ──────────────────────────────────────────────────────────────────────────────
# Static & Media
# ──────────────────────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# ──────────────────────────────────────────────────────────────────────────────
# Celery
# ──────────────────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env_str("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = env_str("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TIMEZONE = env_str("CELERY_TIMEZONE", "UTC")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", "False")
# Optional tuning via ENV (read in your worker entrypoint if desired):
#   CELERY_CONCURRENCY=4
#   CELERY_QUEUES=default,payments,notifications

# ──────────────────────────────────────────────────────────────────────────────
# External Services / Project-specific
# ──────────────────────────────────────────────────────────────────────────────
CAS_PUBLICKEY_URL = env_str(
    "CAS_PUBLICKEY_URL", "http://erp.ag/cas/static/public_key.pem"
)
CAS_URL = env_str("CAS_URL", "http://erp.ag/cas")
CAS_DEBUG = env_bool("CAS_DEBUG", "False")
CAS_SAME_ORIGIN = env_bool("CAS_SAME_ORIGIN", "True")
CAS_TOKEN = env_str("CAS_TOKEN", "dev-cas-token")

KAVENEGAR_API_KEY = env_str("KAVENEGAR_API_KEY", "dev-kavenegar-key")
KAVENEGAR_NUMBER = env_str("KAVENEGAR_NUMBER", "")

# Normalize to always end with a single trailing slash
FRONTEND_BASE_URL = (env_str(
    "FRONTEND_BASE_URL", "http://localhost:3000/"
) or "").rstrip("/") + "/"
LLM_BASE_URL = env_str("LLM_BASE_URL", "http://localhost:8008/")

CARD_VALIDATOR_MOCK = env_bool("CARD_VALIDATOR_MOCK", "True")

# ──────────────────────────────────────────────────────────────────────────────
# Security (auto-enabled in production)
# ──────────────────────────────────────────────────────────────────────────────
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Consider enabling HSTS/CSP on the edge or via django-csp:
    # SECURE_HSTS_SECONDS = 31536000
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_HSTS_PRELOAD = True

# ──────────────────────────────────────────────────────────────────────────────
# reCAPTCHA Configuration
# ──────────────────────────────────────────────────────────────────────────────
# NOTE: Never commit real secrets here; keep a harmless placeholder.
RECAPTCHA_SECRET_KEY = env_str("RECAPTCHA_SECRET_KEY", "replace-me-in-env")

# ──────────────────────────────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(levelname)s %(name)s: %(message)s"},
        # "verbose": {"format": "%(asctime)s %(levelname)s %(name)s [%(process)d] %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"}
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
