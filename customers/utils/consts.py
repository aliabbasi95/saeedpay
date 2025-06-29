from django.conf import settings

DEFAULT_LIFE_DURATION = 300
DEFAULT_OTP_SEND_PERIOD = 24 * 3600

DEFAULT_OTP_SEND_LIMIT = 100


def get_setting(name, default):
    return getattr(settings, name, default)


LIFE_DURATION = get_setting(
    "LIFE_DURATION",
    DEFAULT_LIFE_DURATION
)

OTP_SEND_PERIOD = get_setting(
    "OTP_SEND_PERIOD",
    DEFAULT_OTP_SEND_PERIOD
)

OTP_SEND_LIMIT = get_setting(
    "OTP_SEND_LIMIT",
    DEFAULT_OTP_SEND_LIMIT
)
