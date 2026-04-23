# saeedpay/settings/test.py

from copy import deepcopy

from .base import *  # noqa: F401,F403  # isort: skip_file
from .base import REST_FRAMEWORK as BASE_REST_FRAMEWORK
from .base import env

# ───────────────────────── Core test toggles ─────────────────────────
DEBUG = True
CAS_DEBUG = True

# ───────────────────────── Test speed / isolation ─────────────────────────
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ───────────────────────── Cookies / sessions ─────────────────────────
SESSION_COOKIE_DOMAIN = None
REFRESH_COOKIE_SECURE = False

# ───────────────────────── DRF (keep base shape, loosen for tests) ─────────────────────────
REST_FRAMEWORK = deepcopy(BASE_REST_FRAMEWORK)

REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = [
    "lib.cas_auth.authentication.PublicAuthentication",
]
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = [
    "rest_framework.permissions.IsAuthenticated",
]
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = [
    "rest_framework.throttling.AnonRateThrottle",
    "rest_framework.throttling.UserRateThrottle",
    "rest_framework.throttling.ScopedRateThrottle",
]

REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    **BASE_REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
    "anon": "100000/hour",
    "user": "100000/hour",
    "auth-login": "100000/hour",
    "auth-logout": "100000/hour",
    "auth-refresh": "100000/hour",
    "auth-register": "100000/hour",
    "auth-change-password": "100000/hour",
    "auth-reset-password": "100000/hour",
    "auth-otp": "100000/hour",
    "otp-by-phone": "100000/hour",
    "comments": "100000/hour",
    "comment-create": "100000/hour",
    "comment-like": "100000/hour",
    "bank-cards-read": "100000/hour",
    "bank-cards-write": "100000/hour",
    "credit-statements-read": "100000/hour",
    "credit-statement-lines-read": "100000/hour",
    "credit-statements-write": "100000/hour",
    "payment-requests-read": "100000/hour",
    "payment-requests-write": "100000/hour",
    "payment-confirm": "100000/hour",
    "merchant-pos-payment-read": "100000/hour",
    "merchant-pos-payment-write": "100000/hour",
    "wallets-read": "100000/hour",
    "credit-limits-read": "100000/hour",
    "installments-read": "100000/hour",
    "installment-plans-read": "100000/hour",
    "installments-apply": "100000/hour",
    "wallet-transfers-read": "100000/hour",
    "wallet-transfers-write": "100000/hour",
    "partner-payment-read": "100000/hour",
    "partner-payment-write": "100000/hour",
    "store-apikey-regen": "100000/hour",
    "stores-read": "100000/hour",
    "stores-write": "100000/hour",
    "public-stores-read": "100000/hour",
    "store-contract-read": "100000/hour",
    "store-contract-write": "100000/hour",
    "chat-sessions": "100000/hour",
    "chat-start": "100000/hour",
    "chat-talk": "100000/hour",
    "chat-messages": "100000/hour",
    "contact-create": "100000/hour",
    "tickets-read": "100000/hour",
    "tickets-write": "100000/hour",
    "ticket-message-add": "100000/hour",
    "ticket-categories-read": "100000/hour",
    "loan-risk-otp": "100000/hour",
    "loan-risk-reports": "100000/hour",
    "loan-risk": "100000/hour",
}

# ───────────────────────── Test-friendly service defaults ─────────────────────────
CARD_VALIDATOR_MOCK = True

KAVENEGAR_API_KEY = env("KAVENEGAR_API_KEY", default="")
KAVENEGAR_NUMBER = env("KAVENEGAR_NUMBER", default="")
