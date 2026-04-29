"""
Defines central choices for the tickets app, mirroring project conventions.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class TicketStatus(models.TextChoices):
    OPEN = "open", _("باز")
    IN_PROGRESS = "in_progress", _("در حال رسیدگی")
    WAITING_ON_USER = "waiting_on_user", _("در انتظار کاربر")
    RESOLVED = "resolved", _("حل شد")
    CLOSED = "closed", _("بسته شد")
    REOPENED = "reopened", _("دوباره باز شد")


class TicketPriority(models.TextChoices):
    LOW = "low", _("کم")
    NORMAL = "normal", _("معمولی")
    HIGH = "high", _("زیاد")
    URGENT = "urgent", _("فوری")


class TicketMessageSender(models.TextChoices):
    USER = "user", _("کاربر")
    STAFF = "staff", _("کارشناس")
