# blogs/models/tag.py

from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel


class Tag(BaseModel):
    name = models.CharField(
        max_length=100, unique=True, verbose_name=_("نام برچسب")
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        blank=True,
        verbose_name=_("نامک"),
        help_text=_("Left blank to auto-generate from name."),
    )
    description = models.TextField(
        blank=True, null=True, verbose_name=_("توضیحات")
    )
    color = models.CharField(
        max_length=7,
        default="#007bff",
        verbose_name=_("رنگ برچسب"),
        help_text=_("کد رنگ هگز (مثال: #007bff)"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("فعال"))

    @property
    def article_count(self):
        """
        Number of published articles (whose time has passed) having this tag.
        Kept consistent with ArticleManager.published().
        """
        return (
            self.articles.filter(
                status="published", published_at__lte=timezone.now()
            )
            .distinct()
            .count()
        )

    def save(self, *args, **kwargs):
        """Auto-generate unique slug if blank."""
        if not self.slug and self.name:
            self.slug = slugify(self.name, allow_unicode=True)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("برچسب")
        verbose_name_plural = _("برچسب‌ها")
        ordering = ["name"]
