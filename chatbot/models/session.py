from django.conf import settings
from django.db import models
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
        verbose_name=_("فعال است"),
    )

    def __str__(self):
        return (
            f"ChatSession #{self.pk} "
            f"({self.user or self.session_key or self.ip_address})"
        )

    class Meta:
        verbose_name = _("نشست گفتگو")
        verbose_name_plural = _("نشست‌های گفتگو")
