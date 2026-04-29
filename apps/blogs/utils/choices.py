# blogs/utils/choices.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class ArticleStatus(models.TextChoices):
    DRAFT = "draft", _("پیش‌نویس")
    PUBLISHED = "published", _("منتشر شده")
    ARCHIVED = "archived", _("آرشیو شده")


class SectionType(models.TextChoices):
    H1 = "h1", _("عنوان اصلی (H1)")
    H2 = "h2", _("عنوان فرعی (H2)")
    H3 = "h3", _("عنوان سطح سوم (H3)")
    H4 = "h4", _("عنوان سطح چهارم (H4)")
    PARAGRAPH = "paragraph", _("پاراگراف")
    IMAGE = "image", _("تصویر")
    CITE = "cite", _("نقل قول")
