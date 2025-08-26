# blogs/models/comment.py
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from lib.erp_base.models import BaseModel


class CommentManager(models.Manager):
    def approved(self):
        """Return only approved comments"""
        return self.filter(is_approved=True)
    
    def pending(self):
        """Return only pending comments"""
        return self.filter(is_approved=False)


class Comment(BaseModel):
    article = models.ForeignKey(
        'Article',
        on_delete=models.CASCADE,
        related_name='comments',
        null=True,
        blank=True,
        verbose_name=_("مقاله"),
        help_text=_("مقاله مرتبط با نظر - می‌تواند خالی باشد")
    )
    
    author = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='blog_comments',
        verbose_name=_("نویسنده نظر"),
        null=True,
        blank=True
    )
    
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
        verbose_name=_("پاسخ به"),
        help_text=_("برای پاسخ به نظر دیگر")
    )
    
    content = models.TextField(
        verbose_name=_("محتوای نظر")
    )
    
    is_approved = models.BooleanField(
        default=False,
        verbose_name=_("تایید شده"),
        help_text=_("نظرات تایید نشده نمایش داده نمی‌شوند")
    )
    
    rating = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_("امتیاز"),
        help_text=_("امتیاز کاربر از 1 تا 5")
    )
    
    # Spam detection
    is_spam = models.BooleanField(
        default=False,
        verbose_name=_("اسپم")
    )
    
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
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_approved'], name='comment_approved_idx'),
            models.Index(fields=['created_at'], name='comment_created_idx'),
        ]

    def __str__(self):
        author_name = self.author.username if self.author else _("کاربر ناشناس")
        if self.article:
            return f"نظر {author_name} در {self.article.title}"
        else:
            return f"نظر عمومی {author_name}"

    @property
    def is_reply(self):
        """Check if this comment is a reply to another comment"""
        return self.reply_to is not None

    @property
    def reply_count(self):
        """Return the number of approved replies to this comment"""
        return self.replies.filter(is_approved=True).count()

    @property
    def total_replies(self):
        """Return the total number of replies (including nested)"""
        count = 0
        for reply in self.replies.filter(is_approved=True):
            count += 1 + reply.total_replies
        return count

    def get_replies(self):
        """Get all approved direct replies to this comment"""
        return self.replies.filter(is_approved=True).order_by('created_at')

    def approve(self):
        """Approve this comment"""
        self.is_approved = True
        self.save(update_fields=['is_approved'])

    def reject(self):
        """Reject this comment"""
        self.is_approved = False
        self.save(update_fields=['is_approved'])

    def mark_as_spam(self):
        """Mark this comment as spam"""
        self.is_spam = True
        self.is_approved = False
        self.save(update_fields=['is_spam', 'is_approved'])

    def can_be_replied_to(self):
        """Check if this comment can receive replies"""
        return self.is_approved and not self.is_spam

    def get_thread_comments(self):
        """Get all comments in this thread (for nested display)"""
        if self.reply_to:
            # If this is a reply, get the root comment's thread
            return self.reply_to.get_thread_comments()
        else:
            # This is a root comment, return all its descendants
            return Comment.objects.filter(
                models.Q(pk=self.pk) | models.Q(reply_to=self.pk)
            ).filter(is_approved=True).order_by('created_at')
