# blogs/models/article.py
from django.contrib.auth import get_user_model
from django.db import models, IntegrityError, transaction
from django.db.models import F, Max
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from blogs.utils.choices import ArticleStatus, SectionType
from lib.erp_base.models import BaseModel


class ArticleManager(models.Manager):
    def published(self):
        """Return only published articles whose publication time has passed."""
        return self.filter(
            status="published", published_at__lte=timezone.now()
        )

    def draft(self):
        """Return only draft articles."""
        return self.filter(status="draft")

    def featured(self):
        """Return only featured & published articles."""
        return self.published().filter(is_featured=True)


class Article(BaseModel):
    title = models.CharField(max_length=200, verbose_name=_("عنوان"))

    slug = models.SlugField(
        max_length=200,
        unique=True,
        blank=True,
        verbose_name=_("نامک"),
        help_text=_("Left blank to auto-generate from title."),
    )

    author = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="articles",
        verbose_name=_("نویسنده"),
    )

    excerpt = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("خلاصه")
    )

    featured_image = models.ImageField(
        upload_to="articles/featured/",
        blank=True,
        null=True,
        verbose_name=_("تصویر شاخص"),
    )

    status = models.CharField(
        max_length=20,
        choices=ArticleStatus.choices,
        default=ArticleStatus.DRAFT,
        verbose_name=_("وضعیت"),
    )

    tags = models.ManyToManyField(
        "Tag",
        blank=True,
        related_name="articles",
        verbose_name=_("برچسب‌ها")
    )

    is_featured = models.BooleanField(
        default=False,
        verbose_name=_("مقاله ویژه")
    )

    published_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name=_("زمان انتشار")
    )

    view_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("تعداد بازدید")
    )

    objects = ArticleManager()

    class Meta:
        verbose_name = _("مقاله")
        verbose_name_plural = _("مقالات")
        ordering = ["-is_featured", "-published_at", "-created_at"]
        indexes = [
            models.Index(
                fields=["status", "published_at"],
                name="article_status_pub_idx"
            ),
            models.Index(
                fields=["is_featured", "published_at"],
                name="article_feat_pub_idx"
            ),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        - Ensure unique slug on first creation or when slug is blank.
        - Auto-set published_at when status is PUBLISHED and field is empty.
        - Avoid heavy cross-relations here (e.g., do not query sections); use signals if needed.
        """
        # Auto-generate slug if blank and we have a title
        if not self.slug and self.title:
            base = slugify(self.title, allow_unicode=True)
            candidate = base or "article"
            suffix = 1
            # Attempt to save with unique slug; on collision, add numeric suffix.
            while True:
                try:
                    with transaction.atomic():
                        self.slug = candidate
                        # If published & no timestamp, set it before initial save
                        if self.status == self.Status.PUBLISHED and not self.published_at:
                            self.published_at = timezone.now()
                        return super().save(*args, **kwargs)
                except IntegrityError:
                    suffix += 1
                    candidate = f"{base}-{suffix}"
        else:
            # Keep published_at consistent if transitioning to published without a timestamp
            if self.status == self.Status.PUBLISHED and not self.published_at:
                self.published_at = timezone.now()
            return super().save(*args, **kwargs)

    def get_absolute_url(self):
        """Return the canonical URL for this article."""
        return reverse("blog:article_detail", kwargs={"slug": self.slug})

    @property
    def is_published(self):
        """True if status is published and time has passed."""
        return (
                self.status == self.Status.PUBLISHED
                and self.published_at is not None
                and self.published_at <= timezone.now()
        )

    @property
    def comment_count(self):
        """Number of approved comments (use annotated count in views for performance)."""
        return self.comments.filter(is_approved=True).count()

    def increment_view_count(self):
        """
        Atomically increment view_count without updating updated_at timestamp.
        Use queryset update to avoid race conditions.
        """
        Article.objects.filter(pk=self.pk).update(
            view_count=F("view_count") + 1
        )
        # Keep in-memory object in sync (optional)
        self.view_count += 1

    def render_content(self):
        """
        Render article content from sections in order.
        Assumes sections are prefetch'ed in views to avoid N+1 queries.
        """
        html_parts = []
        for section in self.sections.all().order_by("order"):
            html_parts.append(section.render_html())
        return "\n".join(html_parts)


class ArticleSection(BaseModel):
    """Model for structured article content sections."""
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="sections",
        verbose_name=_("مقاله")
    )

    section_type = models.CharField(
        max_length=20,
        choices=SectionType.choices,
        verbose_name=_("نوع بخش")
    )

    content = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("محتوا"),
        help_text=_("Text content for headings, paragraphs, and quotes."),
    )

    image = models.ImageField(
        upload_to="articles/sections/",
        blank=True,
        null=True,
        verbose_name=_("تصویر"),
        help_text=_("Image file for image sections."),
    )

    image_alt = models.CharField(
        max_length=200, blank=True, null=True,
        verbose_name=_("متن جایگزین تصویر")
    )

    order = models.PositiveIntegerField(
        default=0, verbose_name=_("ترتیب نمایش")
    )

    class Meta:
        verbose_name = _("بخش مقاله")
        verbose_name_plural = _("بخش‌های مقاله")
        ordering = ["article", "order"]
        indexes = [models.Index(
            fields=["article", "order"], name="article_section_order_idx"
        )]
        constraints = [
            # Ensure each (article, order) is unique
            models.UniqueConstraint(
                fields=["article", "order"], name="uniq_article_order"
            ),
        ]

    def __str__(self):
        return f"{self.article.title} - {self.get_section_type_display()} ({self.order})"

    def save(self, *args, **kwargs):
        """
        Assign next order for the article when order=0.
        Use short retry loop to avoid race on concurrent inserts.
        """
        if self.order == 0 and self.article_id:
            for _ in range(3):
                last = (
                        ArticleSection.objects.filter(article=self.article)
                        .aggregate(m=Max("order"))
                        .get("m")
                        or 0
                )
                self.order = last + 1
                try:
                    with transaction.atomic():
                        return super().save(*args, **kwargs)
                except IntegrityError:
                    # Another concurrent insert grabbed the same order; retry.
                    continue
        return super().save(*args, **kwargs)

    def clean(self):
        """Validate section fields consistency based on section type."""
        from django.core.exceptions import ValidationError

        if self.section_type == self.SectionType.IMAGE:
            if not self.image:
                raise ValidationError(_("تصویر برای بخش تصویری الزامی است"))
        else:
            if not self.content:
                raise ValidationError(_("محتوا برای این نوع بخش الزامی است"))

    def render_html(self):
        """
        Render section as minimal HTML snippet.
        NOTE: If content originates from untrusted users, sanitize before rendering.
        """
        if self.section_type in [self.SectionType.H1, self.SectionType.H2,
                                 self.SectionType.H3, self.SectionType.H4]:
            return f"<{self.section_type}>{self.content}</{self.section_type}>"
        elif self.section_type == self.SectionType.PARAGRAPH:
            return f"<p>{self.content}</p>"
        elif self.section_type == self.SectionType.IMAGE and self.image:
            alt_text = self.image_alt or ""
            return f'<img src="{self.image.url}" alt="{alt_text}" class="article-image" />'
        elif self.section_type == self.SectionType.CITE:
            return f"<blockquote>{self.content}</blockquote>"
        return ""
