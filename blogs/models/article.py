# blogs/models/article.py
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.text import slugify
from django.urls import reverse

from lib.erp_base.models import BaseModel


class ArticleManager(models.Manager):
    def published(self):
        """Return only published articles"""
        return self.filter(status='published', published_at__lte=timezone.now())
    
    def draft(self):
        """Return only draft articles"""
        return self.filter(status='draft')
    
    def featured(self):
        """Return only featured published articles"""
        return self.published().filter(is_featured=True)


class Article(BaseModel):
    STATUS_CHOICES = [
        ('draft', _('پیش‌نویس')),
        ('published', _('منتشر شده')),
        ('archived', _('آرشیو شده')),
    ]

    title = models.CharField(
        max_length=200,
        verbose_name=_("عنوان")
    )
    
    slug = models.SlugField(
        max_length=200,
        unique=True,
        blank=True,
        verbose_name=_("نامک")
    )
    
    author = models.ForeignKey(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name='articles',
        verbose_name=_("نویسنده")
    )
    
    
    excerpt = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name=_("خلاصه")
    )
    
    featured_image = models.ImageField(
        upload_to='articles/featured/',
        blank=True,
        null=True,
        verbose_name=_("تصویر شاخص")
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name=_("وضعیت")
    )
    
    tags = models.ManyToManyField(
        'Tag',
        blank=True,
        related_name='articles',
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
        ordering = ['-is_featured', '-published_at', '-created_at']
        indexes = [
            models.Index(fields=['status', 'published_at'], name='article_status_pub_idx'),
            models.Index(fields=['author'], name='article_author_idx'),
            models.Index(fields=['is_featured'], name='article_featured_idx'),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Auto-generate slug from title if not provided
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)
        
        # Set published_at when status changes to published
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        
        # Auto-generate excerpt from first paragraph section if not provided
        if not self.excerpt:
            first_paragraph = self.sections.filter(section_type='paragraph').first()
            if first_paragraph and first_paragraph.content:
                self.excerpt = first_paragraph.content[:497] + "..." if len(first_paragraph.content) > 500 else first_paragraph.content
        
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """Return the canonical URL for this article"""
        return reverse('blog:article_detail', kwargs={'slug': self.slug})

    @property
    def is_published(self):
        """Check if article is published and publication time has passed"""
        return (
            self.status == 'published' and 
            self.published_at and 
            self.published_at <= timezone.now()
        )

    @property
    def comment_count(self):
        """Return the number of approved comments"""
        return self.comments.filter(is_approved=True).count()

    def increment_view_count(self):
        """Increment the view count for this article"""
        self.view_count += 1
        self.save(update_fields=['view_count'])

    def render_content(self):
        """Render article content from sections"""
        html_parts = []
        
        for section in self.sections.all().order_by('order'):
            html_parts.append(section.render_html())
        
        return '\n'.join(html_parts)


class ArticleSection(BaseModel):
    """Model for article content sections"""
    
    SECTION_TYPE_CHOICES = [
        ('h1', _('عنوان اصلی (H1)')),
        ('h2', _('عنوان فرعی (H2)')),
        ('h3', _('عنوان سطح سوم (H3)')),
        ('h4', _('عنوان سطح چهارم (H4)')),
        ('paragraph', _('پاراگراف')),
        ('image', _('تصویر')),
        ('cite', _('نقل قول')),
    ]
    
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='sections',
        verbose_name=_("مقاله")
    )
    
    section_type = models.CharField(
        max_length=20,
        choices=SECTION_TYPE_CHOICES,
        verbose_name=_("نوع بخش")
    )
    
    content = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("محتوا"),
        help_text=_("محتوای متنی برای عناوین، پاراگراف‌ها و نقل قول‌ها")
    )
    
    image = models.ImageField(
        upload_to='articles/sections/',
        blank=True,
        null=True,
        verbose_name=_("تصویر"),
        help_text=_("تصویر برای بخش‌های تصویری")
    )
    
    image_alt = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("متن جایگزین تصویر")
    )
    
    order = models.PositiveIntegerField(
        default=0,
        verbose_name=_("ترتیب نمایش")
    )

    class Meta:
        verbose_name = _("بخش مقاله")
        verbose_name_plural = _("بخش‌های مقاله")
        ordering = ['article', 'order']
        indexes = [
            models.Index(fields=['article', 'order'], name='article_section_order_idx'),
        ]

    def __str__(self):
        return f"{self.article.title} - {self.get_section_type_display()} ({self.order})"
    
    def save(self, *args, **kwargs):
        """Auto-assign order if not provided"""
        if self.order == 0 and self.article_id:
            # Get the highest order number for this article
            max_order = ArticleSection.objects.filter(
                article=self.article
            ).aggregate(
                max_order=models.Max('order')
            )['max_order']
            
            self.order = (max_order or 0) + 1
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate section based on type"""
        from django.core.exceptions import ValidationError
        
        if self.section_type == 'image':
            if not self.image:
                raise ValidationError(_("تصویر برای بخش تصویری الزامی است"))
        else:
            if not self.content:
                raise ValidationError(_("محتوا برای این نوع بخش الزامی است"))
    
    def render_html(self):
        """Render section as HTML"""
        if self.section_type in ['h1', 'h2', 'h3', 'h4']:
            level = self.section_type[1]  # Extract number from h1, h2, etc.
            return f'<{self.section_type}>{self.content}</{self.section_type}>'
        
        elif self.section_type == 'paragraph':
            return f'<p>{self.content}</p>'
        
        elif self.section_type == 'image' and self.image:
            alt_text = self.image_alt or ''
            return f'<img src="{self.image.url}" alt="{alt_text}" class="article-image" />'
        
        elif self.section_type == 'cite':
            return f'<blockquote>{self.content}</blockquote>'
        
        return ''
