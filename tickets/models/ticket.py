# tickets/models/ticket.py
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from .category import TicketCategory
from tickets.utils.choices import TicketStatus, TicketPriority


class Ticket(BaseModel):
    # Centralized choices (keep nested access pattern)
    Status = TicketStatus
    Priority = TicketPriority

    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="tickets",
        verbose_name=_("کاربر")
    )
    assigned_staff = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        verbose_name=_("کارشناس مسئول"),
    )
    category = models.ForeignKey(
        TicketCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
        verbose_name=_("دسته‌بندی")
    )

    title = models.CharField(max_length=200, verbose_name=_("عنوان"))

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN,
        verbose_name=_("وضعیت")
    )
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.NORMAL,
        verbose_name=_("اولویت")
    )

    class Meta:
        verbose_name = _("تیکت")
        verbose_name_plural = _("تیکت‌ها")
        indexes = [
            models.Index(fields=["user", "status", "priority"]),
        ]

    def __str__(self):
        return f"#{self.pk} · {self.title}"
