# credit/admin/loan_risk_report.py

from __future__ import annotations

import json

from django.contrib import admin, messages
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from persiantools.jdatetime import JalaliDateTime

from credit.models.loan_risk_report import LoanRiskReport
from credit.tasks_loan_validation import (
    send_loan_validation_otp,
    check_loan_report_result,
)
from credit.utils.choices import LoanReportStatus, LoanRiskLevel


# ---------- date & formatting helpers ----------
def _to_jalali(dt):
    """Convert aware datetime to formatted Jalali or '-'."""
    if not dt:
        return "-"
    dt = timezone.localtime(dt)
    return JalaliDateTime(dt).strftime("%Y/%m/%d %H:%M:%S")


def _badge(text: str, color: str) -> str:
    """Render a colored pill badge."""
    return format_html(
        '<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
        'font-size:12px;color:#fff;background:{};">{}</span>',
        color, text,
    )


def _status_badge(value: str) -> str:
    """LoanReportStatus → colored badge with Farsi label."""
    colors = {
        LoanReportStatus.PENDING: "#3b82f6",
        LoanReportStatus.OTP_SENT: "#6366f1",
        LoanReportStatus.IN_PROCESSING: "#f59e0b",
        LoanReportStatus.COMPLETED: "#16a34a",
        LoanReportStatus.FAILED: "#ef4444",
    }
    label = LoanReportStatus(value).label if value else "نامشخص"
    return _badge(label, colors.get(value, "#6b7280"))


def _risk_badge(value: str | None) -> str:
    """LoanRiskLevel → colored badge with Farsi label."""
    colors = {
        LoanRiskLevel.A1: "#059669",
        LoanRiskLevel.A2: "#10b981",
        LoanRiskLevel.B1: "#14b8a6",
        LoanRiskLevel.B2: "#0ea5e9",
        LoanRiskLevel.C1: "#f59e0b",
        LoanRiskLevel.C2: "#d97706",
        LoanRiskLevel.D: "#ef4444",
        LoanRiskLevel.E: "#991b1b",
        None: "#6b7280",
    }
    text = LoanRiskLevel(value).label if value else "نامشخص"
    return _badge(text, colors.get(value, "#6b7280"))


def _pretty_json(obj) -> str:
    """Safe pretty JSON in LTR <pre>."""
    if obj in (None, "", {}):
        return "-"
    try:
        pretty = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:  # pragma: no cover
        pretty = str(obj)
    return mark_safe(
        '<pre style="white-space:pre-wrap; direction:ltr; margin:0">{}</pre>'.format(
            pretty
        )
    )


def _profile_link(obj: LoanRiskReport) -> str:
    """Clickable link to related Profile in admin."""
    url = reverse("admin:profiles_profile_change", args=[obj.profile_id])
    return format_html(
        '<a href="{}" target="_blank">Profile #{}</a>', url, obj.profile_id
    )


# ---------- list filters ----------
class HasErrorFilter(admin.SimpleListFilter):
    title = "دارای خطا؟"
    parameter_name = "has_error"

    def lookups(self, request, model_admin):
        return (("yes", "بله"), ("no", "خیر"))

    def queryset(self, request, qs):
        if self.value() == "yes":
            return qs.exclude(error_message__isnull=True).exclude(
                error_message__exact=""
            )
        if self.value() == "no":
            return qs.filter(
                models.Q(error_message__isnull=True) | models.Q(
                    error_message__exact=""
                )
            )
        return qs


class HasOTPFilter(admin.SimpleListFilter):
    title = "OTP دارد؟"
    parameter_name = "has_otp"

    def lookups(self, request, model_admin):
        return (("yes", "بله"), ("no", "خیر"))

    def queryset(self, request, qs):
        if self.value() == "yes":
            return qs.exclude(otp_unique_id__isnull=True).exclude(
                otp_unique_id__exact=""
            )
        if self.value() == "no":
            return qs.filter(
                models.Q(otp_unique_id__isnull=True) | models.Q(
                    otp_unique_id__exact=""
                )
            )
        return qs


class HasReportIDFilter(admin.SimpleListFilter):
    title = "Report ID دارد؟"
    parameter_name = "has_report"

    def lookups(self, request, model_admin):
        return (("yes", "بله"), ("no", "خیر"))

    def queryset(self, request, qs):
        if self.value() == "yes":
            return qs.exclude(report_unique_id__isnull=True).exclude(
                report_unique_id__exact=""
            )
        if self.value() == "no":
            return qs.filter(
                models.Q(report_unique_id__isnull=True) | models.Q(
                    report_unique_id__exact=""
                )
            )
        return qs


class ScoreBucketFilter(admin.SimpleListFilter):
    title = "باکت امتیاز"
    parameter_name = "score_bucket"

    def lookups(self, request, model_admin):
        return (
            ("<300", "< 300"),
            ("300-500", "300–500"),
            ("500-650", "500–650"),
            ("650-800", "650–800"),
            (">800", "> 800"),
        )

    def queryset(self, request, qs):
        val = self.value()
        if not val:
            return qs
        if val == "<300":
            return qs.filter(credit_score__lt=300)
        if val == "300-500":
            return qs.filter(credit_score__gte=300, credit_score__lt=500)
        if val == "500-650":
            return qs.filter(credit_score__gte=500, credit_score__lt=650)
        if val == "650-800":
            return qs.filter(credit_score__gte=650, credit_score__lt=800)
        if val == ">800":
            return qs.filter(credit_score__gte=800)
        return qs


# ---------- admin ----------
@admin.register(LoanRiskReport)
class LoanRiskReportAdmin(admin.ModelAdmin):
    """Rich admin for loan risk reports with badges, Jalali times, and safe actions."""

    list_display = (
        "id",
        "profile_link",
        "national_code",
        "mobile_number",
        "status_badge_col",
        "risk_badge_col",
        "credit_score",
        "otp_unique_id",
        "report_unique_id",
        "jalali_creation_time",
        "jalali_update_time",
    )
    list_filter = (
        "status",
        "risk_level",
        HasErrorFilter,
        HasOTPFilter,
        HasReportIDFilter,
        ScoreBucketFilter,
        ("created_at", admin.DateFieldListFilter),
        ("completed_at", admin.DateFieldListFilter),
        ("otp_sent_at", admin.DateFieldListFilter),
        ("report_requested_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "id",
        "profile__user__username",
        "profile__user__email",
        "profile__phone_number",
        "national_code",
        "mobile_number",
        "otp_unique_id",
        "report_unique_id",
        "error_code",
        "error_message",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    autocomplete_fields = ("profile",)
    list_select_related = ("profile",)
    empty_value_display = "-"

    readonly_fields = (
        "status",
        "credit_score",
        "risk_level",
        "grade_description",
        "otp_unique_id",
        "otp_sent_at",
        "report_unique_id",
        "report_requested_at",
        "report_timestamp",
        "report_types_pretty",
        "report_data_pretty",
        "error_code",
        "error_message",
        "completed_at",
        "created_at",
        "updated_at",
        "jalali_creation_time",
        "jalali_update_time",
        "jalali_otp_sent_at",
        "jalali_report_requested_at",
        "jalali_completed_at",
        "can_request_new_label",
        "otp_valid_label",
    )

    fieldsets = (
        ("شناسه‌ها و وضعیت", {
            "fields": (
                "profile",
                "status",
                ("credit_score", "risk_level", "grade_description"),
                ("otp_unique_id", "report_unique_id"),
                ("otp_valid_label", "can_request_new_label"),
            )
        }),
        ("اطلاعات هویتی داخل گزارش", {
            "fields": ("national_code", "mobile_number")
        }),
        ("زمان‌ها", {
            "fields": (
                ("otp_sent_at", "jalali_otp_sent_at"),
                ("report_requested_at", "jalali_report_requested_at"),
                ("completed_at", "jalali_completed_at"),
                ("created_at", "jalali_creation_time"),
                ("updated_at", "jalali_update_time"),
            )
        }),
        ("انواع گزارش و مُهر زمان سرویس", {
            "fields": ("report_types_pretty", "report_timestamp")
        }),
        ("دادهٔ کامل گزارش", {
            "classes": ("collapse",),
            "fields": ("report_data_pretty",)
        }),
        ("خطا", {
            "fields": (("error_code",), "error_message")
        }),
    )

    actions = (
        "action_send_otp",
        "action_check_result",
        "action_clear_error_note",
    )

    # ---------- list_display helpers ----------
    @admin.display(description="پروفایل")
    def profile_link(self, obj: LoanRiskReport):
        return _profile_link(obj)

    @admin.display(description="وضعیت", ordering="status")
    def status_badge_col(self, obj: LoanRiskReport):
        return _status_badge(obj.status)

    @admin.display(description="سطح ریسک", ordering="risk_level")
    def risk_badge_col(self, obj: LoanRiskReport):
        return _risk_badge(obj.risk_level)

    # ---------- readonly / pretty fields ----------
    @admin.display(description="JSON انواع گزارش")
    def report_types_pretty(self, obj: LoanRiskReport):
        return _pretty_json(obj.report_types)

    @admin.display(description="JSON دادهٔ کامل گزارش")
    def report_data_pretty(self, obj: LoanRiskReport):
        return _pretty_json(obj.report_data)

    @admin.display(description="OTP (جلالی)")
    def jalali_otp_sent_at(self, obj: LoanRiskReport):
        return _to_jalali(obj.otp_sent_at)

    @admin.display(description="درخواست گزارش (جلالی)")
    def jalali_report_requested_at(self, obj: LoanRiskReport):
        return _to_jalali(obj.report_requested_at)

    @admin.display(description="تکمیل (جلالی)")
    def jalali_completed_at(self, obj: LoanRiskReport):
        return _to_jalali(obj.completed_at)

    @admin.display(description="امکان درخواست جدید؟")
    def can_request_new_label(self, obj: LoanRiskReport):
        can, reason, _last = LoanRiskReport.can_user_request_new_report(
            obj.profile
        )
        color = "#16a34a" if can else "#ef4444"
        text = "بله" if can else "خیر"
        tip = reason or ""
        return format_html(
            '<span title="{}" style="color:{};font-weight:600">{}</span>', tip,
            color, text
        )

    @admin.display(description="OTP معتبر است؟")
    def otp_valid_label(self, obj: LoanRiskReport):
        if not obj.otp_sent_at:
            return "-"
        is_valid = obj.is_otp_valid()
        color = "#16a34a" if is_valid else "#ef4444"
        text = "بله" if is_valid else "خیر"
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>', color, text
        )

    # ---------- actions (status-aware + celery-safe) ----------
    @admin.action(description="ارسال OTP (برای موارد انتخاب‌شده)")
    def action_send_otp(self, request, queryset):
        if not send_loan_validation_otp:
            self.message_user(
                request,
                "تسک ارسال OTP یافت نشد (credit.tasks_loan_validation).",
                level=messages.WARNING
            )
            return
        eligible = queryset.filter(status=LoanReportStatus.PENDING)
        skipped = queryset.exclude(pk__in=eligible.values("pk")).count()
        count = 0
        for r in eligible:
            send_loan_validation_otp.delay(r.id)
            count += 1
        if skipped:
            self.message_user(
                request,
                f"{skipped} رکورد به‌دلیل وضعیت نامعتبر برای OTP نادیده گرفته شد.",
                level=messages.WARNING
            )
        self.message_user(
            request, f"OTP برای {count} گزارش صف شد.", level=messages.SUCCESS
        )

    @admin.action(description="بررسی نتیجه (برای موارد انتخاب‌شده)")
    def action_check_result(self, request, queryset):
        if not check_loan_report_result:
            self.message_user(
                request,
                "تسک بررسی نتیجه یافت نشد (credit.tasks_loan_validation).",
                level=messages.WARNING
            )
            return
        eligible = queryset.filter(
            status=LoanReportStatus.IN_PROCESSING
        ).exclude(report_unique_id__isnull=True).exclude(
            report_unique_id__exact=""
        )
        skipped = queryset.exclude(pk__in=eligible.values("pk")).count()
        count = 0
        for r in eligible:
            check_loan_report_result.delay(r.id)
            count += 1
        if skipped:
            self.message_user(
                request,
                f"{skipped} رکورد به‌دلیل وضعیت/Report ID نامعتبر نادیده گرفته شد.",
                level=messages.WARNING
            )
        self.message_user(
            request, f"بررسی نتیجه برای {count} مورد صف شد.",
            level=messages.SUCCESS
        )

    @admin.action(description="پاک‌کردن پیام/کد خطا (یادداشت مدیریتی)")
    def action_clear_error_note(self, request, queryset):
        updated = queryset.update(error_message=None, error_code=None)
        self.message_user(
            request, f"خطا برای {updated} رکورد پاک شد.",
            level=messages.SUCCESS
        )
