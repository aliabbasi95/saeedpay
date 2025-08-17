# blogs/admin/article.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django import forms
from django.db import models
from django.forms.widgets import Textarea
from django.utils import timezone

from lib.erp_base.admin.base import BaseAdmin, BaseInlineAdmin
from blogs.models import Article, ArticleSection


class ArticleSectionForm(forms.ModelForm):
    class Meta:
        model = ArticleSection
        fields = ['section_type', 'content', 'image', 'image_alt', 'order']
    
    def clean(self):
        cleaned_data = super().clean()
        section_type = cleaned_data.get('section_type')
        content = cleaned_data.get('content')
        image = cleaned_data.get('image')
        
        if section_type == 'image':
            if not image:
                self.add_error('image', _('تصویر برای بخش تصویری الزامی است'))
            if content:
                self.add_error('content', _('بخش تصویری نباید محتوای متنی داشته باشد'))
        else:
            if not content:
                self.add_error('content', _('محتوا برای این نوع بخش الزامی است'))
            if image:
                self.add_error('image', _('بخش متنی نباید تصویر داشته باشد'))
        
        return cleaned_data


class ArticleSectionInline(admin.TabularInline):
    model = ArticleSection
    form = ArticleSectionForm
    extra = 0
    fields = ('section_type', 'content', 'image', 'image_alt', 'order', 'image_preview')
    readonly_fields = ('image_preview',)
    ordering = ('order',)
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'content':
            field.widget.attrs.update({'rows': 3})
        elif db_field.name == 'order':
            # Make order field smaller and add help text
            field.widget.attrs.update({'style': 'width: 60px;'})
            field.help_text = 'ترتیب نمایش (خودکار اگر خالی باشد)'
        return field
    
    def get_queryset(self, request):
        """Ensure sections are ordered by order field"""
        return super().get_queryset(request).order_by('order')
    
    class Media:
        js = ('admin/js/jquery.init.js', 'admin/js/inlines.js', 'admin/js/article_section_ordering.js')
        css = {
            'all': ('admin/css/changelists.css',)
        }
    
    @admin.display(description=_("پیش‌نمایش تصویر"))
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 80px; max-height: 80px; border-radius: 4px;" />',
                obj.image.url
            )
        return "بدون تصویر"


@admin.register(Article)
class ArticleAdmin(BaseAdmin):
    list_display = [
        'title',
        'author',
        'status',
        'is_featured',
        'view_count',
        'image_count',
        'published_at',
        'jalali_creation_date_time'
    ]
    
    list_filter = [
        'status',
        'is_featured',
        'author',
        'tags',
        'published_at',
        'created_at'
    ]
    
    search_fields = [
        'title',
        'excerpt',
        'author__username',
        'author__first_name',
        'author__last_name'
    ]
    
    prepopulated_fields = {
        'slug': ('title',)
    }
    
    readonly_fields = [
        'view_count',
        'jalali_creation_date_time',
        'jalali_update_date_time',
        'featured_image_preview'
    ]
    
    filter_horizontal = ['tags']
    
    date_hierarchy = 'published_at'
    
    actions = ['make_published', 'make_draft', 'make_featured', 'remove_featured']
    
    inlines = [ArticleSectionInline]
    
    formfield_overrides = {
        models.TextField: {
            'widget': Textarea(attrs={
                'rows': 15,
                'cols': 80,
                'style': 'font-family: monospace; font-size: 14px;'
            })
        },
    }
    
    fieldsets = (
        (_('محتوا اصلی'), {
            'fields': ('title', 'slug', 'excerpt')
        }),
        (_('تصویر شاخص'), {
            'fields': ('featured_image', 'featured_image_preview'),
            'classes': ('collapse',)
        }),
        (_('تنظیمات انتشار'), {
            'fields': ('status', 'published_at', 'is_featured', 'tags')
        }),
        (_('آمار'), {
            'fields': ('view_count',),
            'classes': ('collapse',)
        }),
        (_('زمان‌بندی'), {
            'fields': ('jalali_creation_date_time', 'jalali_update_date_time'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author').prefetch_related('tags', 'sections')

    @admin.display(description='تعداد بخش‌ها')
    def image_count(self, obj):
        return obj.sections.count()

    @admin.display(description='پیش‌نمایش تصویر شاخص')
    def featured_image_preview(self, obj):
        if obj.featured_image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />',
                obj.featured_image.url
            )
        return "بدون تصویر شاخص"
    

    @admin.action(description='انتشار مقالات انتخاب شده')
    def make_published(self, request, queryset):
        updated = queryset.update(
            status='published',
            published_at=timezone.now()
        )
        self.message_user(request, f'{updated} مقاله منتشر شد.')

    @admin.action(description='تبدیل به پیش‌نویس')
    def make_draft(self, request, queryset):
        updated = queryset.update(status='draft')
        self.message_user(request, f'{updated} مقاله به پیش‌نویس تبدیل شد.')

    @admin.action(description='تبدیل به مقاله ویژه')
    def make_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} مقاله به عنوان ویژه انتخاب شد.')

    @admin.action(description='حذف از مقالات ویژه')
    def remove_featured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} مقاله از مقالات ویژه حذف شد.')

    def save_model(self, request, obj, form, change):
        if not change:  # New article
            obj.author = request.user
        super().save_model(request, obj, form, change)



@admin.register(ArticleSection)
class ArticleSectionAdmin(BaseAdmin):
    list_display = ['article', 'section_type', 'content_preview', 'order', 'jalali_creation_date_time']
    list_filter = ['section_type', 'article', 'created_at']
    search_fields = ['content', 'image_alt', 'article__title']
    ordering = ['article', 'order']
    
    @admin.display(description='پیش‌نمایش محتوا')
    def content_preview(self, obj):
        if obj.section_type == 'image' and obj.image:
            return format_html(
                '<img src="{}" style="max-width: 60px; max-height: 60px; border-radius: 4px;" />',
                obj.image.url
            )
        elif obj.content:
            return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
        return 'بدون محتوا'
