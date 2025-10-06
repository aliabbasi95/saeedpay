# credit/utils/choices.py

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
    PENDING = 'PENDING', 'در انتظار'
    OTP_SENT = 'OTP_SENT', 'کد ارسال شده'
    IN_PROCESSING = 'IN_PROCESSING', 'در حال پردازش'
    COMPLETED = 'COMPLETED', 'تکمیل شده'
    FAILED = 'FAILED', 'ناموفق'
    EXPIRED = 'EXPIRED', 'منقضی شده'


class LoanRiskLevel(models.TextChoices):
    """Credit risk levels."""
    A1 = 'A1', 'ریسک بسیار پایین'
    A2 = 'A2', 'ریسک پایین'
    B1 = 'B1', 'ریسک کم'
    B2 = 'B2', 'ریسک متوسط پایین'
    C1 = 'C1', 'ریسک متوسط'
    C2 = 'C2', 'ریسک متوسط بالا'
    D = 'D', 'ریسک بالا'
    E = 'E', 'ریسک بسیار بالا'
    UNKNOWN = 'UNKNOWN', 'نامشخص'
