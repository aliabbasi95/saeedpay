from django.db import models
from django.utils.translation import gettext_lazy as _
from lib.erp_base.models import BaseModel


class ChatLimit(BaseModel):
    session_key = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name=_("کلید نشست"),
    )
    date = models.DateField(
        verbose_name=_("تاریخ"),
    )
    message_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("تعداد پیام‌ها"),
    )
    max_messages = models.PositiveIntegerField(
        default=5,
        verbose_name=_("حداکثر پیام مجاز"),
    )

    def __str__(self):
        return (
            f"Limit for {self.session_key} on {self.date}: "
            f"{self.message_count}/{self.max_messages}"
        )

    class Meta:
        verbose_name = _("محدودیت گفتگو")
        verbose_name_plural = _("محدودیت‌های گفتگو")
