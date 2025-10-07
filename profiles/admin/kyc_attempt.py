# profiles/admin/kyc_attempt.py

from __future__ import annotations
from __future__ import annotations

import json
from datetime import timedelta

from django.contrib import admin, messages
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from profiles.models.kyc_attempt import ProfileKYCAttempt
from profiles.tasks import (
    verify_identity_phone_national_id,
    check_profile_video_auth_result,
    reset_profile_video_auth,
)
from profiles.utils.choices import (
    AttemptStatus, KYCStatus,
    AuthenticationStage,
)
from profiles.utils.choices import (
    AttemptType,
)


def _badge(text: str, color: str) -> str:
    """Render a small colored badge."""
    return format_html(
        '<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
        'font-size:12px;color:#fff;background:{};">{}</span>',
        color, text
    )


def _status_badge(value: str) -> str:
    """Map AttemptStatus to consistent badge colors."""
    colors = {
        AttemptStatus.PROCESSING: "#f59e0b",  # amber
        AttemptStatus.SUCCESS: "#16a34a",  # green
        AttemptStatus.FAILED: "#ef4444",  # red
        AttemptStatus.REJECTED: "#6b7280",  # gray
        AttemptStatus.PENDING: "#3b82f6",  # blue
    }
    return _badge(value, colors.get(value, "#3b82f6"))


def _kyc_result_badge(value: str | None) -> str:
    colors = {
        KYCStatus.ACCEPTED: "#16a34a",
        KYCStatus.REJECTED: "#ef4444",
        KYCStatus.FAILED: "#f59e0b",
        KYCStatus.PROCESSING: "#3b82f6",
        None: "#6b7280",
    }
    text = value or "None"
    return _badge(text, colors.get(value, "#6b7280"))


def _pretty_json(obj: dict | None) -> str:
    """Safe pretty JSON renderer for admin detail pages."""
    if not obj:
        return "-"
    try:
        pretty = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        pretty = str(obj)
    return mark_safe(
        f'<pre style="white-space:pre-wrap; direction:ltr">{pretty}</pre>'
    )


def _admin_link_to_profile(profile_id: int) -> str:
    url = reverse("admin:profiles_profile_change", args=[profile_id])
    return format_html('<a href="{}">Profile #{}</a>', url, profile_id)


class HasExternalIDFilter(admin.SimpleListFilter):
    title = "دارای شناسه خارجی؟"
    parameter_name = "has_external_id"

    def lookups(self, request, model_admin):
        return (("yes", "بله"), ("no", "خیر"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(external_id__isnull=True).exclude(
                external_id__exact=""
            )
        if self.value() == "no":
            return queryset.filter(
                Q(external_id__isnull=True) | Q(external_id__exact="")
            )
        return queryset


class HasErrorFilter(admin.SimpleListFilter):
    title = "دارای خطا؟"
    parameter_name = "has_error"

    def lookups(self, request, model_admin):
        return (("yes", "بله"), ("no", "خیر"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(error_message__isnull=True).exclude(
                error_message__exact=""
            )
        if self.value() == "no":
            return queryset.filter(
                Q(error_message__isnull=True) | Q(error_message__exact="")
            )
        return queryset


class StaleProcessingFilter(admin.SimpleListFilter):
    """Show attempts that stuck in PROCESSING beyond a threshold."""
    title = "باقیمانده در حالت پردازش"
    parameter_name = "stale_proc"

    def lookups(self, request, model_admin):
        return (("15", "قدیمی‌تر از ۱۵ دقیقه"),
                ("60", "قدیمی‌تر از ۱ ساعت"),
                ("240", "قدیمی‌تر از ۴ ساعت"))

    def queryset(self, request, queryset):
        if not self.value():
            return queryset
        minutes = int(self.value())
        cutoff = timezone.now() - timedelta(minutes=minutes)
        return queryset.filter(
            status=AttemptStatus.PROCESSING, started_at__lt=cutoff
        )


@admin.register(ProfileKYCAttempt)
class ProfileKYCAttemptAdmin(admin.ModelAdmin):
    """Operator-friendly admin for tracing KYC flow."""
    list_display = (
        "id",
        "profile_link",
        "attempt_type",
        "status_badge",
        "external_id",
        "retry_count",
        "duration_sec",
        "jalali_creation_time",
        "jalali_update_time",
    )
    list_filter = (
        "attempt_type",
        "status",
        HasExternalIDFilter,
        HasErrorFilter,
        StaleProcessingFilter,
        "created_at",
    )
    search_fields = (
        "id",
        "external_id",
        "error_code",
        "error_message",
        "profile__user__username",
        "profile__phone_number",
        "profile__national_id",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    autocomplete_fields = ("profile",)
    readonly_fields = (
        "id",
        "profile",
        "attempt_type",
        "status",
        "external_id",
        "retry_count",
        "started_at",
        "finished_at",
        "http_status",
        "error_code",
        "error_message",
        "created_at",
        "updated_at",
        "request_pretty",
        "response_pretty",
        "profile_snapshot",
    )
    fieldsets = (
        ("Attempt", {
            "fields": (
                ("id", "attempt_type", "status"),
                ("profile", "external_id", "retry_count"),
                ("started_at", "finished_at"),
                "duration_readonly",
            )
        }),
        ("HTTP / Error", {
            "fields": (("http_status", "error_code"), "error_message")
        }),
        ("Payloads", {
            "classes": ("collapse",),
            "fields": ("request_pretty", "response_pretty")
        }),
    )
    actions = ("action_requeue_shahkar", "action_poll_video_result",
               "action_reset_video")

    # ---------- list_display helpers ----------
    @admin.display(description="پروفایل")
    def profile_link(self, obj: ProfileKYCAttempt):
        return _admin_link_to_profile(obj.profile_id)

    @admin.display(description="وضعیت", ordering="status")
    def status_badge(self, obj: ProfileKYCAttempt):
        return _status_badge(obj.status)

    @admin.display(description="مدت (ثانیه)")
    def duration_sec(self, obj: ProfileKYCAttempt):
        if obj.started_at and obj.finished_at:
            return round((obj.finished_at - obj.started_at).total_seconds(), 3)
        return "-"

    # ---------- detail helpers ----------
    @admin.display(description="درخواست (JSON مرتب)")
    def request_pretty(self, obj: ProfileKYCAttempt):
        return _pretty_json(obj.request_payload)

    @admin.display(description="پاسخ (JSON مرتب)")
    def response_pretty(self, obj: ProfileKYCAttempt):
        return _pretty_json(obj.response_payload)

    @admin.display(description="مدت (نمایشی)")
    def duration_readonly(self, obj: ProfileKYCAttempt):
        if obj.started_at and obj.finished_at:
            s = (obj.finished_at - obj.started_at).total_seconds()
            return f"{s:.3f} s"
        return "-"

    @admin.display(description="تصویر لحظه‌ای از پروفایل")
    def profile_snapshot(self, obj: ProfileKYCAttempt):
        p = obj.profile
        return mark_safe(
            "<div style='line-height:1.7'>"
            f"<strong>کاربر:</strong> {p.user} <br>"
            f"<strong>موبایل:</strong> {p.phone_number or '-'} <br>"
            f"<strong>کد ملی:</strong> {p.national_id or '-'} <br>"
            f"<strong>مرحله احراز:</strong> {AuthenticationStage(p.auth_stage).label} <br>"
            f"<strong>شاهکار:</strong> {_kyc_result_badge(p.phone_national_id_match_status)} <br>"
            f"<strong>احراز هویت ویدئویی:</strong> {_kyc_result_badge(p.video_auth_status)}"
            "</div>"
        )

    # ---------- actions ----------
    @admin.action(
        description="ارسال دوباره استعلام شاهکار (برای رکوردهای انتخاب‌شده)"
    )
    def action_requeue_shahkar(self, request, queryset):
        count = 0
        for att in queryset:
            # Only meaningful for Shahkar attempts
            if att.attempt_type != AttemptType.SHAHKAR:
                continue
            verify_identity_phone_national_id.delay(att.profile_id)
            count += 1
        if count:
            self.message_user(
                request, f"{count} تسک شاهکار دوباره صف شد.",
                level=messages.SUCCESS
            )

        else:
            self.message_user(
                request, "مورد معتبری برای شاهکار در انتخاب وجود ندارد.",
                level=messages.WARNING
            )

    @admin.action(
        description="پول کردن نتیجهٔ ویدئو (برای رکوردهای انتخاب‌شده)"
    )
    def action_poll_video_result(self, request, queryset):
        count = 0
        for att in queryset:
            if att.attempt_type != AttemptType.VIDEO_RESULT:
                continue
            check_profile_video_auth_result.delay(att.profile_id)
            count += 1
        if count:
            self.message_user(
                request, f"پول نتیجه برای {count} مورد صف شد.",
                level=messages.SUCCESS
            )
        else:
            self.message_user(
                request, "موردی از نوع VIDEO_RESULT در انتخاب نیست.",
                level=messages.WARNING
            )

    @admin.action(description="ریست احراز هویت ویدئویی پروفایل‌های مرتبط")
    def action_reset_video(self, request, queryset):
        count = 0
        for att in queryset:
            reset_profile_video_auth.delay(
                att.profile_id, reason="admin_action"
            )
            count += 1
        self.message_user(
            request, f"ریست ویدئویی برای {count} پروفایل زمان‌بندی شد.",
            level=messages.SUCCESS
        )
