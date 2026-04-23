# saeedpay/settings/dev.py

from .base import *  # noqa: F401,F403  # isort: skip_file

from .base import CSRF_TRUSTED_ORIGINS as BASE_CSRF_TRUSTED_ORIGINS
from .base import env

# ───────────────────────── Core dev toggles ─────────────────────────
DEBUG = True
ALLOWED_HOSTS = ["*"]

# ───────────────────────── CAS (dev defaults, overridable via .env) ─────────────────────────
CAS_PUBLICKEY_URL = env(
    "CAS_PUBLICKEY_URL",
    default="http://erp.ag/cas/static/public_key.pem",
)
CAS_URL = env("CAS_URL", default="http://erp.ag/cas")
CAS_DEBUG = env.bool("CAS_DEBUG", default=True)
CAS_SAME_ORIGIN = env.bool("CAS_SAME_ORIGIN", default=True)

# ───────────────────────── CORS (dev-friendly) ─────────────────────────
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=True)
CORS_ALLOW_CREDENTIALS = True


# ───────────────────────── Cache ─────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ───────────────────────── Email (console in dev) ─────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ───────────────────────── CSRF / Cookies (relaxed for dev) ─────────────────────────
CSRF_TRUSTED_ORIGINS = [
    *BASE_CSRF_TRUSTED_ORIGINS,
    "http://localhost:8088",
    "http://127.0.0.1:8088",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Refresh cookie should not be secure in dev (HTTP)
REFRESH_COOKIE_SECURE = False

# ───────────────────────── SMS / OTP (dev uses dummy backend) ─────────────────────────

OTP_SMS_BACKEND = "lib.erp_base.otp.sms.dummy.DummySMSBackend"
KAVENEGAR_API_KEY = env("KAVENEGAR_API_KEY", default="")
KAVENEGAR_NUMBER = env("KAVENEGAR_NUMBER", default="")

# ───────────────────────── Feature flags ─────────────────────────
CARD_VALIDATOR_MOCK = True
