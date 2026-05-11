# saeedpay/settings/base.py
import sys
from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab
from corsheaders.defaults import default_headers

from . import admin_reorder as _admin_reorder

# ───────────────────────── Paths ─────────────────────────
# BASE_DIR points to the inner 'saeedpay' package directory.
BASE_DIR = Path(__file__).resolve().parent.parent
# PROJECT_ROOT points to the repository root directory (outer).
PROJECT_ROOT = BASE_DIR.parent


env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DJANGO_TIME_ZONE=(str, "Asia/Tehran"),
)

# Load .env from repo root to work both inside/outside docker-compose
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    environ.Env.read_env(str(ENV_FILE))

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
TIME_ZONE = env("DJANGO_TIME_ZONE")
USE_TZ = True

# ───────────────────────── Service Meta ─────────────────────────
SERVICE_NAME = env("SERVICE_NAME", default="SAEEDPAY")
SERVICE_NAME_FA = env("SERVICE_NAME_FA", default="سعید پی")
AUTH_USER_MODEL = "cas_auth.User"
AUTHENTICATION_BACKENDS = ["lib.cas_auth.backend.CASBackend"]

DATA_UPLOAD_MAX_NUMBER_FIELDS = 1024 * 8

# Global URL prefix (without leading/trailing slash)
URL_PREFIX = env("URL_PREFIX", default="saeedpay").strip("/")

DEFAULT_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "django_admin_listfilter_dropdown",
    "admin_searchable_dropdown",
    "corsheaders",
    "django_celery_beat",
    "import_export",
    "drf_spectacular",
    "django_filters",
    "sweetify",
    "tinymce",
    "lib.cas_auth",
    "lib.erp_base",
]

LOCAL_APPS = [
    "apps.customers",
    "apps.profiles",
    "apps.auth_api",
    "apps.wallets",
    "apps.merchants",
    "apps.store",
    "apps.chatbot",
    "apps.banking",
    "apps.tickets",
    "apps.credit",
    "apps.blogs",
    "apps.contact",
    "apps.kyc",
]

INSTALLED_APPS = DEFAULT_APPS + LOCAL_APPS

# ───────────────────────── Middleware ─────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "saeedpay.middleware.RequestIDMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "lib.cas_auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "admin_reorder.middleware.ModelAdminReorder",
]

ROOT_URLCONF = "saeedpay.urls"
WSGI_APPLICATION = "saeedpay.wsgi.application"
ASGI_APPLICATION = "saeedpay.asgi.application"

# ───────────────────────── Database ─────────────────────────
# Defaults are container-friendly (db service / redis service)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="saeedpay"),
        "USER": env("POSTGRES_USER", default="saeedpay"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="saeedpay"),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ───────────────────────── Templates ─────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [PROJECT_ROOT / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "lib.cas_auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Ensure lib/ is importable without installing as a package
LIB_PATH = PROJECT_ROOT / "lib"
if LIB_PATH.exists() and str(LIB_PATH) not in sys.path:
    sys.path.insert(0, str(LIB_PATH))


# ───────────────────────── Redis/Celery ─────────────────────────

REDIS_HOST = env("REDIS_HOST", default="localhost")
REDIS_PORT = env("REDIS_PORT", default=6379, cast=int)
REDIS_PASSWORD = env("REDIS_PASSWORD", default="")

REDIS_BROKER_DB = env("REDIS_BROKER_DB", default=0, cast=int)
REDIS_BACKEND_DB = env("REDIS_BACKEND_DB", default=1, cast=int)
REDIS_CACHE_DB = env("REDIS_CACHE_DB", default=2, cast=int)


def _redis_url(db: int) -> str:
    pwd = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
    return f"redis://{pwd}{REDIS_HOST}:{REDIS_PORT}/{db}"


REDIS_URL = _redis_url(REDIS_BROKER_DB)
REDIS_CACHE_URL = _redis_url(REDIS_CACHE_DB)
CELERY_BROKER_URL = _redis_url(REDIS_BROKER_DB)
CELERY_RESULT_BACKEND = _redis_url(REDIS_BACKEND_DB)

CELERY_TIMEZONE = "Asia/Tehran"
CELERY_ENABLE_UTC = True
CELERY_TASK_DEFAULT_QUEUE = "saeedpay"

CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"

CELERY_TASK_ROUTES = {
    "apps.credit.tasks.statement_tasks.*": {"queue": "statements"},
    "apps.credit.tasks.credit_tasks.*": {"queue": "credit"},
}

CELERY_BEAT_SCHEDULE = {
    # wallet
    "expire-pending-payment-requests-every-minute": {
        "task": "apps.wallets.tasks.task_expire_pending_payment_requests",
        "schedule": crontab(minute="*/1"),
    },
    "cleanup-cancelled-and-expired-requests-every-hour": {
        "task": "apps.wallets.tasks.task_cleanup_cancelled_and_expired_requests",
        "schedule": crontab(minute=0, hour="*/1"),
    },
    "expire-pending-transfer-every-minute": {
        "task": "apps.wallets.tasks.task_expire_pending_transfer_requests",
        "schedule": crontab(minute="*/1"),
    },
    # banking
    "reenqueue-stale-pending-cards-every-minute": {
        "task": "apps.banking.tasks.reenqueue_stale_pending_cards",
        "schedule": crontab(minute="*/1"),
        "kwargs": {"limit": 200, "older_than_minutes": 1},
    },
    # credit
    # Credit: safe daily run; idempotent—only acts when month has rolled over
    "credit-month-end-rollover-daily-0010": {
        "task": "apps.credit.tasks.task_month_end_rollover",
        "schedule": crontab(minute=10, hour=0),
    },
    # Credit: finalize due windows hourly
    "credit-finalize-due-windows-hourly-0015": {
        "task": "apps.credit.tasks.task_finalize_due_windows",
        "schedule": crontab(minute=15, hour="*"),
    },
    # profile
    "rehydrate-shahkar-checks-every-15m": {
        "task": "apps.profiles.tasks.rehydrate_shahkar_checks",
        "schedule": 15 * 60,
    },
    "rehydrate-video-kyc-checks-every-15m": {
        "task": "apps.profiles.tasks.rehydrate_video_auth_checks",
        "schedule": 15 * 60,
    },
    # profiles / KYC videos GC
    "purge-expired-kyc-videos-daily-0330": {
        "task": "apps.profiles.tasks.purge_expired_kyc_videos",
        "schedule": crontab(minute=30, hour=3),
    },
}


# ───────────────────────── Static & media ─────────────────────────
if URL_PREFIX:
    STATIC_URL = f"/{URL_PREFIX}/static/"
    MEDIA_URL = f"/{URL_PREFIX}/media/"
else:
    STATIC_URL = "/static/"
    MEDIA_URL = "/media/"

STATIC_ROOT = env("STATIC_ROOT", default=str(PROJECT_ROOT / "staticfiles"))

MEDIA_ROOT = Path(
    env("MEDIA_ROOT", default=str(PROJECT_ROOT / "media"))
)
STATICFILES_DIRS = [
    PROJECT_ROOT / "static",
]
# WhiteNoise tuning for efficient static delivery in both dev/prod images.
WHITENOISE_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def whitenoise_immutable_file_test(path, url):
    """Return True for static URLs so WhiteNoise can mark them immutable."""
    return bool(url and STATIC_URL and url.startswith(STATIC_URL))


# WhiteNoise expects a callable assigned to this name
WHITENOISE_IMMUTABLE_FILE_TEST = whitenoise_immutable_file_test


REST_FRAMEWORK = {
    # ── Auth / Permissions / Schema ───────────────────────────────────────────
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "lib.cas_auth.authentication.PublicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # ── Pagination ────────────────────────────────────────────────────────────
    "DEFAULT_PAGINATION_CLASS": "lib.erp_base.utils.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    # ── Throttling ────────────────────────────────────────────────────────────
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # ── Coarse limits ─────────────────────────────────────────────────────
        "anon": "100/hour",
        "user": "1000/hour",
        # ── Auth ─────────────────────────────────────────────────────────────
        "auth-login": "20/hour",
        "auth-logout": "60/hour",
        "auth-refresh": "120/hour",
        "auth-register": "10/hour",
        "auth-change-password": "30/hour",
        "auth-reset-password": "10/hour",
        "auth-otp": "60/hour",
        "otp-by-phone": "100/hour",
        # ── Blogs / Comments ─────────────────────────────────────────────────
        "comments": "300/hour",
        "comment-create": "60/hour",
        "comment-like": "60/minute",
        # ── Banking / Cards ──────────────────────────────────────────────────
        "bank-cards-read": "300/hour",
        "bank-cards-write": "30/minute",
        # ── Credit (Statements) ──────────────────────────────────────────────
        "credit-statements-read": "300/hour",
        "credit-statement-lines-read": "600/hour",
        "credit-statements-write": "60/min",
        # ── Wallets / Payment Requests ───────────────────────────────────────
        "payment-requests-read": "300/hour",
        "payment-requests-write": "30/minute",
        "payment-confirm": "10/minute",
        "merchant-pos-payment-read": "120/min",
        "merchant-pos-payment-write": "60/min",
        # ── Wallets / Balances & History ────────────────────────────────────
        "wallets-read": "300/hour",
        # ── Wallets / Credit Limits ─────────────────────────────────────────
        "credit-limits-read": "300/hour",
        # ── Wallets / Installments ──────────────────────────────────────────
        "installments-read": "300/hour",
        "installment-plans-read": "300/hour",
        "installments-apply": "30/hour",
        # ── Wallets / Transfers ─────────────────────────────────────────────
        "wallet-transfers-read": "300/hour",
        "wallet-transfers-write": "60/minute",
        # ── Partner (Store API Key) ─────────────────────────────────────────
        "partner-payment-read": "600/hour",
        "partner-payment-write": "60/minute",
        "store-apikey-regen": "5/hour",
        # ── Store (Backoffice) ──────────────────────────────────────────────
        "stores-read": "200/hour",
        "stores-write": "30/hour",
        "public-stores-read": "500/hour",
        "store-contract-read": "100/hour",
        "store-contract-write": "20/hour",
        # ── Chatbot ─────────────────────────────────────────────────────────
        "chat-sessions": "300/hour",
        "chat-start": "20/hour",
        "chat-talk": "60/minute",
        "chat-messages": "300/hour",
        # ── Contact / Tickets ───────────────────────────────────────────────
        "contact-create": "10/hour",
        "tickets-read": "300/hour",
        "tickets-write": "30/hour",
        "ticket-message-add": "60/hour",
        "ticket-categories-read": "500/hour",
        # ── Credit · Loan Risk (NEW) ────────────────────────────────────────
        # collection actions (OTP request/verify)
        "loan-risk-otp": "30/hour",
        # list/retrieve/latest/check
        "loan-risk-reports": "300/hour",
        # optional coarse grouping if needed elsewhere
        "loan-risk": "300/hour",
    },
}


def spectacular_preprocess_hook(endpoints):
    from drf_spectacular.openapi import AutoSchema

    def is_compatible(view):
        try:
            return isinstance(getattr(view.cls, "schema", None), AutoSchema)
        except Exception:
            return False

    return [
        (path, path_regex, method, callback)
        for (path, path_regex, method, callback) in endpoints
        if is_compatible(callback)
    ]


SPECTACULAR_SETTINGS = {
    "TITLE": "SaeedPay API",
    "DESCRIPTION": "SaeedPay public API documentation",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": True,
    "SORT_OPERATION_PARAMETERS": True,
    "TAGS_SORTER": "alpha",
    "OPERATION_ID_METHOD_POSITION": "POST",
    "SECURITY": [{"PublicAuth": []}],
    "COMPONENTS": {
        "securitySchemes": {
            "PublicAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
    "PREPROCESSING_HOOKS": ["saeedpay.settings.base.spectacular_preprocess_hook"],
    "ENUM_NAME_OVERRIDES": {
        "PaymentStatusEnum": "wallets.models.payment.PaymentStatus",
        "PaymentRequestStatusEnum": "wallets.models.payment_request.PaymentRequestStatus",
        "LoanRiskReportStatusEnum": "credit.utils.choices.LoanReportStatus",
    },
}

# ───────────────────────── SimpleJWT ─────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=24),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}
REFRESH_COOKIE_NAME = "sp_refresh"
REFRESH_COOKIE_PATH = "/"
REFRESH_COOKIE_SECURE = True
REFRESH_COOKIE_HTTPONLY = True
REFRESH_COOKIE_SAMESITE = "Strict"

MAX_SESSION_LIFETIME = timedelta(hours=24)


# ───────────────────────── Security baselines (tightened in prod) ─────────────────────────
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"


REQUEST_ID_HEADER = "X-Request-ID"
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOG_JSON = env("LOG_JSON", default=False, cast=bool)

# ───────────────────────── Logging ─────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured_console": {
            "()": "saeedpay.logging.KeyValueLogFormatter",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "structured_json": {
            "()": "saeedpay.logging.JsonLogFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured_json" if LOG_JSON else "structured_console",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "saeedpay": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "saeedpay.wallets.payment": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}

# ───────────────────────── Admin Reorder ─────────────────────────
ADMIN_REORDER = _admin_reorder.ADMIN_REORDER

# ────────────────────────────── Cas ──────────────────────────────
CAS_PUBLICKEY_URL = env("CAS_PUBLICKEY_URL", default="")
CAS_URL = env("CAS_URL", default="")
CAS_DEBUG = env.bool("CAS_DEBUG", default=False)
CAS_SAME_ORIGIN = env.bool("CAS_SAME_ORIGIN", default=False)

# OTP Configuration
OTP_EXPIRY_MINUTES = int(env("OTP_EXPIRY_MINUTES", default=5))
OTP_RESEND_COOLDOWN_SEC = int(env("OTP_RESEND_COOLDOWN_SEC", default=60))
OTP_MAX_ATTEMPTS = int(env("OTP_MAX_ATTEMPTS", default=5))
OTP_DAILY_ISSUE_CAP_PER_IDENTITY = int(
    env("OTP_DAILY_ISSUE_CAP_PER_IDENTITY", default=10)
)
OTP_CODE_LENGTH = int(env("OTP_CODE_LENGTH", default=6))


FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="http://localhost:3000")

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

# Card Validator Configuration
CARD_VALIDATOR_MOCK = env.bool("CARD_VALIDATOR_MOCK", default=True)

# KYC Configuration
KYC_IDENTITY_BASE_URL = env(
    "KYC_IDENTITY_BASE_URL", default="https://sandbox.vidaverify.ir:9091"
)
KYC_IDENTITY_TIMEOUT = env("KYC_IDENTITY_TIMEOUT", default=30, cast=int)
KYC_IDENTITY_TOKEN_SKEW_SECONDS = env(
    "KYC_IDENTITY_TOKEN_SKEW_SECONDS", default=30, cast=int
)

# KYC Retry Configuration
KYC_VIDEO_SUBMIT_MAX_RETRIES = env("KYC_VIDEO_SUBMIT_MAX_RETRIES", default=3, cast=int)
KYC_VIDEO_SUBMIT_RETRY_DELAY = env("KYC_VIDEO_SUBMIT_RETRY_DELAY", default=60, cast=int)
KYC_VIDEO_CHECK_MAX_RETRIES = env("KYC_VIDEO_CHECK_MAX_RETRIES", default=6, cast=int)
KYC_VIDEO_CHECK_RETRY_DELAY = env("KYC_VIDEO_CHECK_RETRY_DELAY", default=30, cast=int)
KYC_SHAHKAR_MAX_RETRIES = env("KYC_SHAHKAR_MAX_RETRIES", default=3, cast=int)
KYC_SHAHKAR_RETRY_DELAY = env("KYC_SHAHKAR_RETRY_DELAY", default=60, cast=int)
CREDIT_DEFAULT_APPROVED_LIMIT = env(
    "CREDIT_DEFAULT_APPROVED_LIMIT", default=5000000, cast=int
)
CREDIT_LIMIT_BY_RISK_LEVEL = {
    "A1": 50_000_000,
    "A2": 50_000_000,
    "A3": 50_000_000,
    "B1": 50_000_000,
    "B2": 50_000_000,
    "B3": 50_000_000,
    "C3": 50_000_000,
}
CREDIT_LIMIT_FALLBACK = 0

# KYC Identity Service Credentials
KIAHOOSHAN_USERNAME = env("KIAHOOSHAN_USERNAME", default="")
KIAHOOSHAN_PASSWORD = env("KIAHOOSHAN_PASSWORD", default="")
KIAHOOSHAN_ORGNAME = env("KIAHOOSHAN_ORGNAME", default="")
KIAHOOSHAN_ORGNATIONALCODE = env("KIAHOOSHAN_ORGNATIONALCODE", default="")

KYC_VIDEO_RETENTION_MODE = env("KYC_VIDEO_RETENTION_MODE", default="approved_only")
KYC_VIDEO_RETENTION_DAYS_APPROVED = env(
    "KYC_VIDEO_RETENTION_DAYS_APPROVED", default="permanent"
)
KYC_VIDEO_RETENTION_DAYS_REJECTED = env(
    "KYC_VIDEO_RETENTION_DAYS_REJECTED", default="7"
)
KYC_VIDEO_STORAGE_PREFIX = env("KYC_VIDEO_STORAGE_PREFIX", default="kyc_videos/")
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "lib.erp_base.validators.UppercaseValidator",
    },
    {
        "NAME": "lib.erp_base.validators.LowercaseValidator",
    },
    {
        "NAME": "lib.erp_base.validators.HasNumberValidator",
    },
    {
        "NAME": "lib.erp_base.validators.SymbolValidator",
    },
    {"NAME": "lib.erp_base.validators.LengthValidator", "OPTIONS": {"min_length": 8}},
]

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "en-us"

USE_I18N = True

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field


CORS_ALLOW_HEADERS = list(default_headers) + [
    "cas-authorization",
]

# reCAPTCHA Configuration
RECAPTCHA_SECRET_KEY = env(
    "RECAPTCHA_SECRET_KEY", default="6LfseasrAAAAAPFD-ZLZPLOco46yvgickFkRR-gs"
)
RECAPTCHA_V3 = False  # Set to False for reCAPTCHA v2
RECAPTCHA_V3_THRESHOLD = 0.5  # Score threshold for v3 (ignored when v2)
RECAPTCHA_ACTION = "submit"  # Default action name for v3 (ignored when v2)


# -----------------------------------------------------------------------------
# Chatbot
# -----------------------------------------------------------------------------
LLM_BASE_URL = env("LLM_BASE_URL", default="http://localhost:8001")
CHATBOT_HISTORY_LIMIT = env("CHATBOT_HISTORY_LIMIT", cast=int, default=4)
CHATBOT_SESSION_LIMIT = env("CHATBOT_SESSION_LIMIT", cast=int, default=2)

OTP_SMS_BACKEND = env(
    "OTP_SMS_BACKEND",
    default="lib.erp_base.otp.sms.dummy.DummySMSBackend",
)