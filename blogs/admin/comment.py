# blogs/admin/comment.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from blogs.models import Comment
from lib.erp_base.admin import BaseAdmin


@admin.register(Comment)
class CommentAdmin(BaseAdmin):
    list_display = [
        'content_preview',
        'author',
        'article',
        'rating',
        'is_approved',
        'is_spam',
        'is_reply',
        'like_count',
        'reply_count',
        'jalali_creation_date_time'
    ]
    
    list_filter = [
        'is_approved',
        'is_spam',
        'rating',
        'article',
        'created_at'
    ]
    
    search_fields = [
        'content',
        'author__username',
        'author__first_name',
        'author__last_name',
        'article__title'
    ]
    
    readonly_fields = [
        'like_count',
        'dislike_count',
        'reply_count',
        'spam_score',
        'jalali_creation_date_time',
        'jalali_update_date_time'
    ]
    
    actions = ['approve_comments', 'reject_comments', 'mark_as_spam']
    
    fieldsets = (
        (_('محتوا'), {
            'fields': ('article', 'author', 'reply_to', 'content', 'rating')
        }),
        (_('وضعیت'), {
            'fields': ('is_approved', 'is_spam')
        }),
        (_('آمار'), {
            'fields': ('like_count', 'dislike_count', 'reply_count', 'spam_score'),
            'classes': ('collapse',)
        }),
        (_('زمان‌بندی'), {
            'fields': ('jalali_creation_date_time', 'jalali_update_date_time'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'author', 'article', 'reply_to'
        ).prefetch_related('replies')

    @admin.display(description=_("محتوا"))
    def content_preview(self, obj):
        content = obj.content[:100] + "..." if len(obj.content) > 100 else obj.content
        if obj.is_spam:
            return format_html(
                '<span style="color: red; text-decoration: line-through;">{}</span>',
                content
            )
        elif not obj.is_approved:
            return format_html(
                '<span style="color: orange;">{}</span>',
                content
            )
        return content

    @admin.display(description=_("پاسخ"), boolean=True)
    def is_reply(self, obj):
        return obj.is_reply

    @admin.display(description=_("تعداد پاسخ"))
    def reply_count(self, obj):
        return obj.reply_count

    @admin.action(description=_("تایید نظرات انتخاب شده"))
    def approve_comments(self, request, queryset):
        updated = 0
        for comment in queryset:
            comment.approve()
            updated += 1
        self.message_user(request, f'{updated} نظر تایید شد.')

    @admin.action(description=_("رد نظرات انتخاب شده"))
    def reject_comments(self, request, queryset):
        updated = 0
        for comment in queryset:
            comment.reject()
            updated += 1
        self.message_user(request, f'{updated} نظر رد شد.')

    @admin.action(description=_("علامت‌گذاری به عنوان اسپم"))
    def mark_as_spam(self, request, queryset):
        updated = 0
        for comment in queryset:
            comment.mark_as_spam()
            updated += 1
        self.message_user(request, f'{updated} نظر به عنوان اسپم علامت‌گذاری شد.')

    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete comments
        return request.user.is_superuser
