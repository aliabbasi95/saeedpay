# credit/utils/choices.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class StatementStatus(models.TextChoices):
    CURRENT = "current", _("جاری")
    PENDING_PAYMENT = "pending_payment", _("در انتظار پرداخت")
    OVERDUE = "overdue", _("سررسید گذشته")
    CLOSED_NO_PENALTY = "closed_no_penalty", _("بسته شده - بدون جریمه")
    CLOSED_WITH_PENALTY = "closed_with_penalty", _("بسته شده - با جریمه")


class StatementLineType(models.TextChoices):
    PURCHASE = "purchase", _("خرید")
    PAYMENT = "payment", _("پرداخت")
    FEE = "fee", _("کارمزد")
    PENALTY = "penalty", _("جریمه")
    INTEREST = "interest", _("سود")
