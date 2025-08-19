# tickets/models/message.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel, BaseAttachment
from tickets.utils.choices import TicketMessageSender
from .ticket import Ticket


class TicketMessage(BaseModel):
    Sender = TicketMessageSender

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("تیکت")
    )
    sender = models.CharField(
        max_length=8,
        choices=Sender.choices,
        verbose_name=_("فرستنده")
    )
    content = models.TextField(verbose_name=_("متن پیام"))
    reply_to = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replies",
        verbose_name=_("پاسخ به")
    )

    def __str__(self):
        return f"Msg#{self.pk} on Ticket#{self.ticket_id} by {self.sender}"

    class Meta:
        verbose_name = _("پیام تیکت")
        verbose_name_plural = _("پیام‌های تیکت")
        ordering = ["id"]


class TicketMessageAttachment(BaseAttachment):
    message = models.ForeignKey(
        TicketMessage,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name=_("پیام")
    )

    class Meta:
        verbose_name = _("پیوست پیام تیکت")
        verbose_name_plural = _("پیوست‌های پیام تیکت")
