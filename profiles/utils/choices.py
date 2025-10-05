# profiles/utils/choices.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class AuthenticationStage(models.IntegerChoices):
    SIGNUP = 1, _("Signup")
    IDENTITY_VERIFIED = 2, _("Identity Verified")
    VIDEO_VERIFIED = 3, _("Video Authentication Verified")


class KYCStatus(models.TextChoices):
    ACCEPTED = "accepted", _("Accepted")
    FAILED = "failed", _("Failed")
    # More granular statuses for better tracking
    PROCESSING = "processing", _("Processing")
    REJECTED = "rejected", _("Rejected")
