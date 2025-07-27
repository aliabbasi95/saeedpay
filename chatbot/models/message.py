from django.db import models
from django.utils.translation import gettext_lazy as _
from lib.erp_base.models import BaseModel
from .session import ChatSession


class ChatMessage(BaseModel):
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("نشست گفتگو"),
    )
    sender = models.CharField(
        max_length=16,
        choices=[("user", _("کاربر")), ("ai", _("هوش مصنوعی"))],
        verbose_name=_("فرستنده"),
    )
    message = models.TextField(
        verbose_name=_("پیام"),
    )

    def __str__(self):
        return f"{self.sender} @ {self.created_at}: {self.message[:30]}"

    class Meta:
        verbose_name = _("پیام گفتگو")
        verbose_name_plural = _("پیام‌های گفتگو")
