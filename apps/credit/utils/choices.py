# apps/credit/utils/choices.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class StatementStatus(models.TextChoices):
    CURRENT = "current", _("جاری")
    PENDING_PAYMENT = "pending_payment", _("در انتظار پرداخت")
    CLOSED_NO_PENALTY = "closed_no_penalty", _("بسته شده - بدون جریمه")
    CLOSED_WITH_PENALTY = "closed_with_penalty", _("بسته شده - با جریمه")


class StatementLineType(models.TextChoices):
    PURCHASE = "purchase", _("خرید")
    PAYMENT = "payment", _("پرداخت")
    FEE = "fee", _("کارمزد")
    PENALTY = "penalty", _("جریمه")
    INTEREST = "interest", _("سود")


class LoanReportStatus(models.TextChoices):
    """Status of the loan risk report request."""

    PENDING = "PENDING", "در انتظار"
    OTP_SENT = "OTP_SENT", "کد ارسال شده"
    IN_PROCESSING = "IN_PROCESSING", "در حال پردازش"
    COMPLETED = "COMPLETED", "تکمیل شده"
    FAILED = "FAILED", "ناموفق"
    EXPIRED = "EXPIRED", "منقضی شده"


class LoanRiskLevel(models.TextChoices):
    """Credit risk levels (granular)."""

    # A — Excellent (Very Low Risk)
    A1 = "A1", _("ریسک بسیار پایین (A1)")
    A2 = "A2", _("ریسک بسیار پایین (A2)")
    A3 = "A3", _("ریسک بسیار پایین (A3)")

    # B — Good (Low Risk)
    B1 = "B1", _("ریسک پایین (B1)")
    B2 = "B2", _("ریسک پایین (B2)")
    B3 = "B3", _("ریسک پایین (B3)")

    # C — Fair (Medium Risk)
    C1 = "C1", _("ریسک متوسط (C1)")
    C2 = "C2", _("ریسک متوسط (C2)")
    C3 = "C3", _("ریسک متوسط (C3)")

    # D — High Risk
    D = "D", _("ریسک بالا (D)")

    # E — Very High Risk
    E = "E", _("ریسک بسیار بالا (E)")

    # Unknown / Not scored
    UNKNOWN = "UNKNOWN", _("نامشخص")
