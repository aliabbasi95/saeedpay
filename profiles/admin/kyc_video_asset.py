# profiles/admin/kyc_video_asset.py

from __future__ import annotations

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from profiles.models.kyc_video_asset import KYCVideoAsset


class RetentionStatusFilter(admin.SimpleListFilter):
    title = _("وضعیت نگهداشت")
    parameter_name = "retention_status"

    def lookups(self, request, model_admin):
        return (
            ("infinite", _("نامحدود")),
            ("expiring", _("در حال انقضا")),
            ("expired", _("منقضی شده"))
        )

    def queryset(self, request, qs):
        now = timezone.now()
        if self.value() == "infinite":
            return qs.filter(retention_until__isnull=True)
        if self.value() == "expiring":
            return qs.filter(retention_until__gt=now)
        if self.value() == "expired":
            return qs.filter(
                retention_until__lte=now, retention_until__isnull=False
            )
        return qs


@admin.register(KYCVideoAsset)
class KYCVideoAssetAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "profile",
        "is_approved_copy",
        "retention_badge",
        "size_human",
        "sha256_short",
        "attempt_link",
        "file_link",
        "jalali_creation_time",
        "jalali_update_time",
    )
    list_filter = ("is_approved_copy", RetentionStatusFilter,
                   ("created_at", admin.DateFieldListFilter))
    search_fields = ("id", "profile__id", "created_by_attempt__id", "sha256",
                     "file")
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    list_select_related = ("profile", "created_by_attempt")

    readonly_fields = (
        "retention_badge",
        "sha256",
        "size",
        "size_human",
        "file_link",
        "created_by_attempt",
        "created_at",
        "updated_at",
        "jalali_creation_time",
        "jalali_update_time",
        "updated_info",
    )

    fields = (
        "profile",
        "file",
        "file_link",
        "is_approved_copy",
        "retention_until",
        "retention_badge",
        "sha256",
        "size",
        "size_human",
        "created_by_attempt",
        ("created_at", "jalali_creation_time"),
        ("updated_at", "jalali_update_time"),
        "updated_info",
    )

    # ---------- computed displays ----------
    @admin.display(description="SHA256 کوتاه")
    def sha256_short(self, obj: KYCVideoAsset) -> str:
        return f"{obj.sha256[:10]}…" if obj.sha256 else "-"

    @admin.display(description="حجم")
    def size_human(self, obj: KYCVideoAsset) -> str:
        size = obj.size or 0
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.0f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"

    @admin.display(description="نگهداشت")
    def retention_badge(self, obj: KYCVideoAsset) -> str:
        if obj.retention_until is None:
            return format_html('<span style="color:#0a7">نامحدود</span>')
        now = timezone.now()
        if obj.retention_until <= now:
            return format_html('<span style="color:#c00">منقضی شده</span>')
        days = (obj.retention_until.date() - now.date()).days
        return format_html(
            '<span style="color:#a70">انقضا در {} روز</span>', days
        )

    @admin.display(description="Attempt")
    def attempt_link(self, obj: KYCVideoAsset) -> str:
        if not obj.created_by_attempt_id:
            return "-"
        return format_html(
            '<a href="/admin/profiles/profilekycattempt/{}/" target="_blank">#{}</a>',
            obj.created_by_attempt_id,
            obj.created_by_attempt_id,
        )

    @admin.display(description="فایل")
    def file_link(self, obj: KYCVideoAsset) -> str:
        try:
            url = obj.file.url
            return format_html(
                '<a href="{}" target="_blank">باز کردن</a>', url
            )
        except Exception:
            return "-"

    @admin.display(description="مسیر ذخیره‌سازی")
    def updated_info(self, obj: KYCVideoAsset) -> str:
        return f"path={obj.file.name}"

    # ---------- actions ----------
    actions = [
        "action_mark_approved",
        "action_mark_not_approved",
        "action_set_infinite_retention",
        "action_set_retention_30d",
        "action_set_retention_90d",
        "action_purge_files_and_records",
    ]

    @admin.action(description="نشانه‌گذاری به‌عنوان نسخهٔ مورد تأیید")
    def action_mark_approved(self, request, queryset):
        updated = queryset.update(is_approved_copy=True)
        self.message_user(
            request, f"{updated} مورد به‌عنوان مورد تأیید علامت‌گذاری شد.",
            level=messages.SUCCESS
        )

    @admin.action(description="لغو تأیید نسخه")
    def action_mark_not_approved(self, request, queryset):
        updated = queryset.update(is_approved_copy=False)
        self.message_user(
            request, f"تأیید {updated} مورد لغو شد.", level=messages.SUCCESS
        )

    @admin.action(description="نگهداشت نامحدود")
    def action_set_infinite_retention(self, request, queryset):
        count = 0
        for obj in queryset:
            obj.mark_retention(days=None, approved=obj.is_approved_copy)
            count += 1
        self.message_user(
            request, f"نگهداشت نامحدود برای {count} مورد تنظیم شد.",
            level=messages.SUCCESS
        )

    @admin.action(description="تنظیم نگهداشت ۳۰ روز")
    def action_set_retention_30d(self, request, queryset):
        count = 0
        for obj in queryset:
            obj.mark_retention(days=30, approved=obj.is_approved_copy)
            count += 1
        self.message_user(
            request, f"نگهداشت ۳۰ روز برای {count} مورد تنظیم شد.",
            level=messages.SUCCESS
        )

    @admin.action(description="تنظیم نگهداشت ۹۰ روز")
    def action_set_retention_90d(self, request, queryset):
        count = 0
        for obj in queryset:
            obj.mark_retention(days=90, approved=obj.is_approved_copy)
            count += 1
        self.message_user(
            request, f"نگهداشت ۹۰ روز برای {count} مورد تنظیم شد.",
            level=messages.SUCCESS
        )

    @admin.action(description="حذف فایل‌ها و رکوردهای انتخاب‌شده")
    def action_purge_files_and_records(self, request, queryset):
        deleted = 0
        for obj in queryset:
            try:
                if obj.file:
                    obj.file.delete(save=False)
            except Exception:
                pass
            obj.delete()
            deleted += 1
        self.message_user(
            request, f"{deleted} مورد حذف شد.", level=messages.WARNING
        )
