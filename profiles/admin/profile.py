# profiles/admin/profile.py

from __future__ import annotations

import json

from django.contrib import admin, messages
from django.utils.safestring import mark_safe

from profiles.models.kyc_attempt import ProfileKYCAttempt
from profiles.models.profile import Profile
from profiles.tasks import (
    verify_identity_phone_national_id,
    check_profile_video_auth_result,
    reset_profile_video_auth,
)
from profiles.utils.choices import KYCStatus, AuthenticationStage


def _badge(text: str, color: str) -> str:
    from django.utils.html import format_html
    return format_html(
        '<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
        'font-size:12px;color:#fff;background:{};">{}</span>', color, text
    )


def _kyc_result_badge(value: str | None) -> str:
    colors = {
        KYCStatus.ACCEPTED: "#16a34a",
        KYCStatus.REJECTED: "#ef4444",
        KYCStatus.FAILED: "#f59e0b",
        KYCStatus.PROCESSING: "#3b82f6",
        None: "#6b7280",
    }
    return _badge(value or "None", colors.get(value, "#6b7280"))


class ProfileKYCAttemptInline(admin.TabularInline):
    model = ProfileKYCAttempt
    extra = 0
    can_delete = False
    fields = ("created_at", "attempt_type", "status", "external_id",
              "retry_count")
    readonly_fields = fields
    ordering = ("-created_at",)
    show_change_link = True


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "phone_number",
        "national_id",
        "auth_stage_label",
        "shahkar_badge",
        "video_badge",
        "jalali_creation_time",
        "jalali_update_time",
    )
    list_filter = (
        "auth_stage",
        "phone_national_id_match_status",
        "video_auth_status",
        ("updated_at", admin.DateFieldListFilter),
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = ("id", "user__username", "user__email", "phone_number",
                     "national_id", "email")
    ordering = ("-updated_at",)
    date_hierarchy = "created_at"
    inlines = (ProfileKYCAttemptInline,)
    autocomplete_fields = ("user",)
    list_select_related = ("user",)
    list_per_page = 40
    save_on_top = True

    readonly_fields = (
        "created_at",
        "updated_at",
        "identity_verified_at",
        "video_submitted_at",
        "video_verified_at",
        "video_auth_last_checked_at",
        "video_auth_status",
        "phone_national_id_match_status",
        "auth_stage",
        "video_task_id",
        "video_auth_summary",
        "jalali_creation_time",
        "jalali_update_time",
    )

    fieldsets = (
        ("مشخصات هویتی", {
            "fields": ("user", "phone_number", "national_id",
                       ("first_name", "last_name"), "email", "birth_date")
        }),
        ("وضعیت احراز هویت", {
            "fields": (
                "auth_stage",
                "video_auth_status",
                "phone_national_id_match_status",
                "identity_verified_at",
                "video_submitted_at",
                "video_verified_at",
                "video_auth_last_checked_at",
                "video_task_id",
                "video_auth_summary",
            )
        }),
    )

    actions = ("action_requeue_shahkar_for_profiles",
               "action_poll_video_result_for_profiles",
               "action_reset_video_for_profiles")

    # ---- list_display helpers ----
    @admin.display(description="مرحله احراز", ordering="auth_stage")
    def auth_stage_label(self, obj: Profile):
        return AuthenticationStage(obj.auth_stage).label

    @admin.display(description="شاهکار")
    def shahkar_badge(self, obj: Profile):
        return _kyc_result_badge(obj.phone_national_id_match_status)

    @admin.display(description="احراز ویدئویی")
    def video_badge(self, obj: Profile):
        return _kyc_result_badge(obj.video_auth_status)

    # ---- detail helper
    @admin.display(description="خلاصهٔ احراز هویت ویدئویی")
    def video_auth_summary(self, obj: Profile):
        info = obj.get_video_auth_status_display_info()
        pretty = json.dumps(info, ensure_ascii=False, indent=2, default=str)
        return mark_safe(
            '<pre style="white-space:pre-wrap; direction:ltr; margin:0">{}</pre>'.format(
                pretty
            )
        )

    # ---- actions ----
    @admin.action(
        description="ارسال دوباره استعلام شاهکار برای پروفایل‌های انتخاب‌شده"
    )
    def action_requeue_shahkar_for_profiles(self, request, queryset):
        count = 0
        for p in queryset:
            if not (p.national_id and p.phone_number):
                continue
            if p.phone_national_id_match_status in (KYCStatus.ACCEPTED,
                                                    KYCStatus.REJECTED,
                                                    KYCStatus.FAILED):
                continue
            verify_identity_phone_national_id.delay(p.id)
            count += 1
        self.message_user(
            request,
            f"استعلام شاهکار برای {count} پروفایل صف شد." if count else "پروفایل واجد شرایطی وجود ندارد.",
            level=messages.SUCCESS if count else messages.WARNING
        )

    @admin.action(
        description="پول نتیجهٔ احراز ویدئویی برای پروفایل‌های انتخاب‌شده"
    )
    def action_poll_video_result_for_profiles(self, request, queryset):
        count = 0
        for p in queryset:
            check_profile_video_auth_result.delay(p.id)
            count += 1
        self.message_user(
            request, f"پول نتیجه برای {count} پروفایل صف شد.",
            level=messages.SUCCESS
        )

    @admin.action(
        description="ریست احراز هویت ویدئویی برای پروفایل‌های انتخاب‌شده"
    )
    def action_reset_video_for_profiles(self, request, queryset):
        count = 0
        for p in queryset:
            reset_profile_video_auth.delay(p.id, reason="admin_action")
            count += 1
        self.message_user(
            request, f"ریست ویدئویی برای {count} پروفایل زمان‌بندی شد.",
            level=messages.SUCCESS
        )
