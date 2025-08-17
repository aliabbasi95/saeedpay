# chatbot/models/session.py

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel


class ChatSession(BaseModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="chat_sessions",
        verbose_name=_("کاربر"),
    )
    session_key = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        db_index=True,
        verbose_name=_("کلید نشست"),
        help_text=_("برای کاربران غیر احراز هویت شده"),
    )
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name=_("آی‌پی آدرس"),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("فعال است"),
    )

    @property
    def last_message_at(self):
        last = self.messages.order_by("-created_at").only("created_at").first()
        return last.created_at if last else None

    def __str__(self):
        ident = self.user or self.session_key or self.ip_address or "unknown"
        return f"ChatSession #{self.pk} ({ident})"

    class Meta:
        verbose_name = _("نشست گفتگو")
        verbose_name_plural = _("نشست‌های گفتگو")
        constraints = [
            models.CheckConstraint(
                check=(
                        Q(user__isnull=False) |
                        Q(session_key__isnull=False)
                ),
                name="chat_session_has_some_identity",
                violation_error_message=_(
                    "حداقل یکی از کاربر یا کلید نشست باید تنظیم شود."
                ),
            ),
        ]
        indexes = [
            models.Index(
                fields=["created_at"], name="chatsession_created_idx"
            ),
        ]
