# store/models/store_user.py

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel
from store.models.store import Store
from store.utils.choices import StoreUserRole


class StoreUser(BaseModel):
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="store_users",
        verbose_name=_("فروشگاه")
    )
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="store_roles",
        verbose_name=_("کاربر")
    )
    role = models.CharField(
        max_length=20,
        choices=StoreUserRole.choices,
        verbose_name=_("نقش")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("فعال؟")
    )

    class Meta:
        unique_together = ("store", "user")
        verbose_name = _("کاربر فروشگاه")
        verbose_name_plural = _("کاربران فروشگاه")

    def __str__(self):
        return f"{self.user.username} in {self.store.name} ({self.get_role_display()})"
