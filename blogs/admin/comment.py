# blogs/admin/comment.py

from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from blogs.models import Comment
from lib.erp_base.admin import BaseAdmin


@admin.register(Comment)
class CommentAdmin(BaseAdmin):
    """
    Optimized comment admin:
    - Annotates approved reply count to avoid per-row COUNT queries.
    - Bulk actions with single UPDATE for speed.
    - Visual cues for spam/pending.
    """
    list_display = [
        "content_preview",
        "author",
        "article",
        "rating",
        "is_approved",
        "is_spam",
        "is_reply_display",
        "approved_reply_count",
        "like_count",
        "dislike_count",
        "jalali_creation_date_time",
    ]
    list_filter = ["is_approved", "is_spam", "rating", "article", "created_at"]
    search_fields = [
        "content",
        "author__username",
        "author__first_name",
        "author__last_name",
        "article__title"
    ]
    readonly_fields = [
        "like_count",
        "dislike_count",
        "spam_score",
        "jalali_creation_date_time",
        "jalali_update_date_time"
    ]
    actions = [
        "approve_comments",
        "reject_comments",
        "mark_as_spam",
        "unmark_as_spam"
    ]
    list_select_related = ("author", "article", "reply_to")
    list_per_page = 50

    fieldsets = (
        (_("محتوا"),
         {"fields": ("article", "author", "reply_to", "content", "rating")}),
        (_("وضعیت"), {"fields": ("is_approved", "is_spam")}),
        (_("آمار"), {
            "fields": ("like_count", "dislike_count", "spam_score"),
            "classes": ("collapse",)
        }),
        (_("زمان‌بندی"), {
            "fields": ("jalali_creation_date_time", "jalali_update_date_time"),
            "classes": ("collapse",)
        }),
    )

    def get_queryset(self, request):
        """
        Prefetch relations and annotate approved replies count for display.
        """
        qs = (
            super()
            .get_queryset(request)
            .select_related("author", "article", "reply_to")
            .prefetch_related("replies")
            .annotate(
                approved_reply_count_anno=Count(
                    "replies", filter=Q(replies__is_approved=True)
                )
            )
        )
        return qs

    @admin.display(description=_("محتوا"))
    def content_preview(self, obj):
        content = obj.content[:100] + "..." if len(
            obj.content
        ) > 100 else obj.content
        if obj.is_spam:
            return format_html(
                '<span style="color: red; text-decoration: line-through;">{}</span>',
                content
            )
        elif not obj.is_approved:
            return format_html(
                '<span style="color: orange;">{}</span>', content
            )
        return content

    @admin.display(description=_("پاسخ"), boolean=True)
    def is_reply_display(self, obj):
        # Use property but keep name distinct to avoid shadowing
        return obj.is_reply

    @admin.display(description=_("تعداد پاسخ"))
    def approved_reply_count(self, obj):
        # Use annotated value; fallback to property if not annotated (e.g., in exports)
        return getattr(
            obj, "approved_reply_count_anno", None
        ) or obj.reply_count

    # --- Bulk actions ---

    @admin.action(description=_("تایید نظرات انتخاب شده"))
    def approve_comments(self, request, queryset):
        updated = queryset.update(is_approved=True, is_spam=False)
        self.message_user(request, f"{updated} نظر تایید شد.")

    @admin.action(description=_("رد نظرات انتخاب شده"))
    def reject_comments(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f"{updated} نظر رد شد.")

    @admin.action(description=_("علامت‌گذاری به عنوان اسپم"))
    def mark_as_spam(self, request, queryset):
        updated = queryset.update(is_spam=True, is_approved=False)
        self.message_user(
            request, f"{updated} نظر به عنوان اسپم علامت‌گذاری شد."
        )

    @admin.action(description=_("حذف علامت اسپم"))
    def unmark_as_spam(self, request, queryset):
        updated = queryset.update(is_spam=False)
        self.message_user(request, f"{updated} نظر از اسپم خارج شد.")

    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete comments
        return request.user.is_superuser
