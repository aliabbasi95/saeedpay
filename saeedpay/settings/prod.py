# saeedpay/settings/prod.py

from copy import deepcopy

from .base import *  # noqa: F401,F403  # isort: skip_file
from .base import LOG_JSON, LOG_LEVEL, env
from .base import LOGGING as BASE_LOGGING
from .base import MIDDLEWARE as BASE_MIDDLEWARE
from .base import SPECTACULAR_SETTINGS as BASE_SPECTACULAR_SETTINGS

# ───────────────────────── Core production toggles ─────────────────────────
DEBUG = False

# Must be provided in production
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# ───────────────────────── Middleware / static files ─────────────────────────
# Keep base middleware intact and add WhiteNoise right after SecurityMiddleware
MIDDLEWARE = deepcopy(BASE_MIDDLEWARE)
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")


# ───────────────────────── HTTPS / cookies / proxy ─────────────────────────
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=True,
)
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=True)

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# ───────────────────────── CORS ─────────────────────────
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True

# ───────────────────────── CAS ─────────────────────────
CAS_PUBLICKEY_URL = env(
    "CAS_PUBLICKEY_URL",
    default="http://erp.ag/cas/static/public_key.pem",
)
CAS_URL = env("CAS_URL", default="http://erp.ag/cas")
CAS_DEBUG = env.bool("CAS_DEBUG", default=False)
CAS_SAME_ORIGIN = env.bool("CAS_SAME_ORIGIN", default=False)

# ───────────────────────── SMS / OTP ─────────────────────────
KAVENEGAR_API_KEY = env("KAVENEGAR_API_KEY")
KAVENEGAR_NUMBER = env("KAVENEGAR_NUMBER")

# ───────────────────────── Feature flags ─────────────────────────
CARD_VALIDATOR_MOCK = env.bool("CARD_VALIDATOR_MOCK", default=False)

# ───────────────────────── OpenAPI / Spectacular ─────────────────────────
SPECTACULAR_SETTINGS = deepcopy(BASE_SPECTACULAR_SETTINGS)
SPECTACULAR_SETTINGS["SERVE_INCLUDE_SCHEMA"] = False

# ───────────────────────── Logging ─────────────────────────
LOGGING = deepcopy(BASE_LOGGING)
LOGGING["root"]["level"] = LOG_LEVEL
LOGGING["handlers"]["console"]["formatter"] = (
    "structured_json" if LOG_JSON else "structured_console"
)
