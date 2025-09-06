# store/models/store.py

import os
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from lib.erp_base.models import dynamic_cardboard
from merchants.models import Merchant


def validate_image_extension(value):
    """Validate that the uploaded file has an allowed image extension."""
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(
            _('فقط فایل‌های تصویری با فرمت‌های jpg, jpeg, png, gif, bmp, webp مجاز هستند.')
        )


def store_logo_upload_path(instance, filename):
    """Generate a unique filename for store logo uploads."""
    ext = os.path.splitext(filename)[1].lower()
    # Use instance.pk if available, otherwise generate a UUID
    store_id = instance.pk if instance.pk else uuid.uuid4().hex[:8]
    filename = f"store_{store_id}_{uuid.uuid4().hex[:8]}{ext}"
    return os.path.join('store_logos', filename)


class Store(
    dynamic_cardboard(
        [("store_reviewer", "کارشناس بررسی فروشگاه"), ],
        'store',
    )
):
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="stores",
        verbose_name=_("فروشنده")
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_("نام فروشگاه")
    )
    code = models.CharField(
        null=True,
        blank=True,
        max_length=20,
        verbose_name=_("کد فروشگاه")
    )
    address = models.TextField(
        blank=True,
        verbose_name=_("آدرس")
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name=_("طول جغرافیایی")
    )
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True,
        verbose_name=_("عرض جغرافیایی")
    )
    website_url = models.URLField(
        blank=True,
        verbose_name=_("لینک وب‌سایت فروشگاه")
    )
    
    logo = models.ImageField(
        upload_to=store_logo_upload_path,
        null=True,
        blank=True,
        validators=[validate_image_extension],
        verbose_name=_("لوگو فروشگاه")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("فعال است؟")
    )

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        verbose_name = _("فروشگاه")
        verbose_name_plural = _("فروشگاه‌ها")
