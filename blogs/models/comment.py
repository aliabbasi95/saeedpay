# blogs/models/comment.py

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from lib.erp_base.models import BaseModel


class CommentManager(models.Manager):
    def approved(self):
        """Return only approved comments."""
        return self.filter(is_approved=True)

    def pending(self):
        """Return only pending comments."""
        return self.filter(is_approved=False)
    
    def orphaned(self):
        """Return comments not linked to any article or store"""
        return self.filter(article__isnull=True, store__isnull=True)
    
    def for_article(self, article_id):
        """Return comments for a specific article"""
        return self.filter(article_id=article_id, store__isnull=True)
    
    def for_store(self, store_id):
        """Return comments for a specific store"""
        return self.filter(store_id=store_id, article__isnull=True)


class Comment(BaseModel):
    article = models.ForeignKey(
        "Article",
        on_delete=models.CASCADE,
        related_name="comments",
        null=True,
        blank=True,
        verbose_name=_("مقاله"),
        help_text=_("مقاله مرتبط با نظر - می‌تواند خالی باشد"),
    )
    
    store = models.ForeignKey(
        'store.Store',
        on_delete=models.CASCADE,
        related_name='comments',
        null=True,
        blank=True,
        verbose_name=_("فروشگاه"),
        help_text=_("فروشگاه مرتبط با نظر - می‌تواند خالی باشد")
    )
    
    author = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="blog_comments",
        verbose_name=_("نویسنده نظر"),
        null=True,
        blank=True,
    )

    reply_to = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
        verbose_name=_("پاسخ به"),
        help_text=_("برای پاسخ به نظر دیگر"),
    )

    content = models.TextField(verbose_name=_("محتوای نظر"))

    is_approved = models.BooleanField(
        default=False,
        verbose_name=_("تایید شده"),
        help_text=_("نظرات تایید نشده نمایش داده نمی‌شوند"),
    )

    rating = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("امتیاز"),
        help_text=_("امتیاز کاربر از 1 تا 5"),
    )

    # Spam detection
    is_spam = models.BooleanField(default=False, verbose_name=_("اسپم"))
    spam_score = models.FloatField(
        default=0.0,
        verbose_name=_("امتیاز اسپم"),
        help_text=_("امتیاز تشخیص اسپم (0.0 تا 1.0)")
    )

    # User interaction
    like_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("تعداد لایک")
    )
    dislike_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("تعداد دیسلایک")
    )

    objects = CommentManager()

    class Meta:
        verbose_name = _("نظر")
        verbose_name_plural = _("نظرات")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['article'], name='comment_article_idx'),
            models.Index(fields=['store'], name='comment_store_idx'),
        ]
        constraints = [
            models.CheckConstraint(
                check=~(models.Q(article__isnull=False) & models.Q(store__isnull=False)),
                name='comment_not_both_article_and_store'
            )
        ]

    def clean(self):
        """
        Validate comment relationships and thread consistency.
        """

        # Validate that comment is linked to either article or store, but not both
        if self.article and self.store:
            raise ValidationError({
                '__all__': _("نظر نمی‌تواند همزمان به مقاله و فروشگاه مرتبط باشد")
            })

        # Ensure reply_to has the same article/store for thread consistency
        if self.reply_to:
            if self.article_id != self.reply_to.article_id:
                raise ValidationError(
                    _("مقاله‌ی نظر پاسخ باید با مقاله‌ی نظر اصلی یکسان باشد.")
                )
            if self.store_id != self.reply_to.store_id:
                raise ValidationError(
                    _("فروشگاه نظر پاسخ باید با فروشگاه نظر اصلی یکسان باشد.")
                )
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        author_name = self.author.username if self.author else _(
            "کاربر ناشناس"
        )
        if self.article:
            return f"نظر {author_name} در {self.article.title}"
        elif self.store:
            return f"نظر {author_name} در {self.store.name}"
        else:
            return f"نظر عمومی {author_name}"

    @property
    def is_reply(self):
        """True if this comment is a reply to another comment."""
        return self.reply_to is not None
    
    @property
    def content_type(self):
        """Return the type of content this comment is linked to"""
        if self.article:
            return 'article'
        elif self.store:
            return 'store'
        else:
            return 'orphaned'

    @property
    def reply_count(self):
        """Number of approved direct replies."""
        return self.replies.filter(is_approved=True).count()

    @property
    def total_replies(self):
        """Total number of approved replies including nested ones (recursive)."""
        count = 0
        for reply in self.replies.filter(is_approved=True):
            count += 1 + reply.total_replies
        return count

    def get_replies(self):
        """Return approved direct replies ordered by creation time."""
        return self.replies.filter(is_approved=True).order_by("created_at")

    def approve(self):
        """Mark this comment approved."""
        self.is_approved = True
        self.save(update_fields=["is_approved"])

    def reject(self):
        """Mark this comment rejected."""
        self.is_approved = False
        self.save(update_fields=["is_approved"])

    def mark_as_spam(self):
        """Mark this comment as spam and unapprove it."""
        self.is_spam = True
        self.is_approved = False
        self.save(update_fields=["is_spam", "is_approved"])

    def can_be_replied_to(self):
        """Whether this comment is eligible for receiving replies."""
        return self.is_approved and not self.is_spam

    def get_thread_comments(self):
        """
        Get all comments in this thread (root + direct replies).
        NOTE: For deep nesting visualizations, prefer fetching via serializers with prefetch.
        """
        if self.reply_to:
            return self.reply_to.get_thread_comments()
        return Comment.objects.filter(
            models.Q(pk=self.pk) | models.Q(reply_to=self.pk)
        ).filter(
            is_approved=True
        ).order_by("created_at")
