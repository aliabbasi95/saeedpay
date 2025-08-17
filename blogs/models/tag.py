# blogs/models/tag.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify

from lib.erp_base.models import BaseModel


class Tag(BaseModel):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("نام برچسب")
    )
    
    slug = models.SlugField(
        max_length=100,
        unique=True,
        blank=True,
        verbose_name=_("نامک")
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("توضیحات")
    )
    
    color = models.CharField(
        max_length=7,
        default="#007bff",
        verbose_name=_("رنگ برچسب"),
        help_text=_("کد رنگ هگز (مثال: #007bff)")
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("فعال")
    )

    class Meta:
        verbose_name = _("برچسب")
        verbose_name_plural = _("برچسب‌ها")
        ordering = ['name']
        indexes = [
            models.Index(fields=['name'], name='tag_name_idx'),
            models.Index(fields=['is_active'], name='tag_active_idx'),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    @property
    def article_count(self):
        """Return the number of published articles with this tag"""
        return self.articles.filter(status='published').count()
