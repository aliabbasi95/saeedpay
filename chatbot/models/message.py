# chatbot/models/message.py

from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from .session import ChatSession
from ..utils.choices import Sender


class ChatMessage(BaseModel):
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name=_("نشست گفتگو"),
    )
    sender = models.CharField(
        max_length=16,
        choices=Sender.choices,
        verbose_name=_("فرستنده"),
        db_index=True,
    )
    message = models.TextField(
        verbose_name=_("پیام"),
    )

    def __str__(self):
        preview = (self.message or "").replace("\n", " ").strip()[:30]
        return f"{self.sender} @ {self.created_at}: {preview}"

    class Meta:
        verbose_name = _("پیام گفتگو")
        verbose_name_plural = _("پیام‌های گفتگو")
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["session", "created_at"],
                name="chatmsg_session_created_idx"
            ),
        ]
