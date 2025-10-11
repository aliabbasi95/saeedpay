# profiles/admin/kyc_video_asset.py

from __future__ import annotations

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from profiles.models.kyc_video_asset import KYCVideoAsset


class RetentionStatusFilter(admin.SimpleListFilter):
    """Filter by retention bucket: Infinite, Expiring (future date), Expired."""
    title = _("Retention status")
    parameter_name = "retention_status"

    def lookups(self, request, model_admin):
        return (
            ("infinite", _("Infinite")),
            ("expiring", _("Expiring")),
            ("expired", _("Expired")),
        )

    def queryset(self, request, queryset):
        val = self.value()
        now = timezone.now()
        if val == "infinite":
            return queryset.filter(retention_until__isnull=True)
        if val == "expiring":
            return queryset.filter(retention_until__gt=now)
        if val == "expired":
            return queryset.filter(
                retention_until__lte=now, retention_until__isnull=False
            )
        return queryset


@admin.register(KYCVideoAsset)
class KYCVideoAssetAdmin(admin.ModelAdmin):
    """
    Clean and practical admin for durable KYC video assets.
    """
    list_display = (
        "id",
        "profile",
        "is_approved_copy",
        "retention_badge",
        "size_human",
        "sha256_short",
        "attempt_link",
        "created_at",
        "file_link",
    )
    list_filter = (
        "is_approved_copy",
        RetentionStatusFilter,
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "id",
        "profile__id",
        "created_by_attempt__id",
        "sha256",
        "file",
    )
    readonly_fields = (
        "sha256",
        "size",
        "retention_badge",
        "size_human",
        "file_link",
        "created_at",
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
        "created_at",
        "updated_info",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    # ----- Computed/pretty fields -----

    def sha256_short(self, obj: KYCVideoAsset) -> str:
        """Shortened SHA256 for listing."""
        if not obj.sha256:
            return "-"
        return f"{obj.sha256[:10]}…"

    sha256_short.short_description = "SHA256"

    def size_human(self, obj: KYCVideoAsset) -> str:
        """Display size in a human-readable format."""
        size = obj.size or 0
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.0f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"

    size_human.short_description = "Size"

    def retention_badge(self, obj: KYCVideoAsset) -> str:
        """Color-coded retention: Infinite / Expiring in Xd / Expired."""
        if obj.retention_until is None:
            return format_html('<span style="color:#0a7">Infinite</span>')
        now = timezone.now()
        if obj.retention_until <= now:
            return format_html('<span style="color:#c00">Expired</span>')
        days = (obj.retention_until.date() - now.date()).days
        return format_html(
            '<span style="color:#a70">Expiring in {}d</span>', days
        )

    retention_badge.short_description = "Retention"

    def attempt_link(self, obj: KYCVideoAsset) -> str:
        """Clickable link to the creating attempt, if present."""
        if not obj.created_by_attempt_id:
            return "-"
        return format_html(
            '<a href="/admin/{app}/{model}/{pk}/" target="_blank">#{}</a>',
            obj.created_by_attempt_id,
            app="profiles",
            model="profilekycattempt",
            pk=obj.created_by_attempt_id,
        )

    attempt_link.short_description = "Attempt"

    def file_link(self, obj: KYCVideoAsset) -> str:
        """Safe link to view/download the file (if storage provides a URL)."""
        try:
            url = obj.file.url
            return format_html('<a href="{}" target="_blank">Open</a>', url)
        except Exception:
            return "-"

    file_link.short_description = "File"

    def updated_info(self, obj: KYCVideoAsset) -> str:
        """Compact debug info."""
        return f"path={obj.file.name}"

    updated_info.short_description = "Storage path"

    # ----- Actions -----

    actions = [
        "action_mark_approved",
        "action_mark_not_approved",
        "action_set_infinite_retention",
        "action_set_retention_30d",
        "action_set_retention_90d",
        "action_purge_files_and_records",
    ]

    @admin.action(description="Mark as approved copy (keep retention as-is)")
    def action_mark_approved(self, request, queryset):
        updated = queryset.update(is_approved_copy=True)
        self.message_user(
            request, f"Marked {updated} asset(s) as approved.",
            level=messages.SUCCESS
        )

    @admin.action(description="Mark as not approved")
    def action_mark_not_approved(self, request, queryset):
        updated = queryset.update(is_approved_copy=False)
        self.message_user(
            request, f"Marked {updated} asset(s) as not approved.",
            level=messages.SUCCESS
        )

    @admin.action(description="Set infinite retention")
    def action_set_infinite_retention(self, request, queryset):
        now = timezone.now()  # noqa: F841
        count = 0
        for obj in queryset:
            obj.mark_retention(days=None, approved=obj.is_approved_copy)
            count += 1
        self.message_user(
            request, f"Updated {count} asset(s) to infinite retention.",
            level=messages.SUCCESS
        )

    @admin.action(description="Set retention to 30 days")
    def action_set_retention_30d(self, request, queryset):
        count = 0
        for obj in queryset:
            obj.mark_retention(days=30, approved=obj.is_approved_copy)
            count += 1
        self.message_user(
            request, f"Updated {count} asset(s) retention to 30 days.",
            level=messages.SUCCESS
        )

    @admin.action(description="Set retention to 90 days")
    def action_set_retention_90d(self, request, queryset):
        count = 0
        for obj in queryset:
            obj.mark_retention(days=90, approved=obj.is_approved_copy)
            count += 1
        self.message_user(
            request, f"Updated {count} asset(s) retention to 90 days.",
            level=messages.SUCCESS
        )

    @admin.action(description="Purge files & delete selected records")
    def action_purge_files_and_records(self, request, queryset):
        deleted = 0
        for obj in queryset:
            # Best-effort file deletion
            try:
                if obj.file:
                    obj.file.delete(save=False)
            except Exception:
                pass
            obj.delete()
            deleted += 1
        self.message_user(
            request, f"Purged {deleted} asset(s).", level=messages.WARNING
        )
