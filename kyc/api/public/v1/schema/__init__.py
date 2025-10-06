# kyc/api/public/v1/schema/__init__.py

from .schema_identity import VERIFY_IDENTITY_SCHEMA
from .schema_video import SUBMIT_VIDEO_SCHEMA, POLL_VIDEO_SCHEMA

__all__ = [
    "VERIFY_IDENTITY_SCHEMA",
    "SUBMIT_VIDEO_SCHEMA",
    "POLL_VIDEO_SCHEMA",
]
