# saeedpay/settings/__init__.py
import os

_env = os.getenv("DJANGO_ENV", "dev").lower()
if _env == "prod":
    from .prod import *  # noqa
elif _env == "test":
    from .test import *  # noqa
else:
    from .dev import *  # noqa
