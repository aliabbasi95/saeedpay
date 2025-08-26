from django.db import models
from django.utils.translation import gettext_lazy as _
from wallets.models import Transaction
from credit.utils.choices import StatementLineType


class StatementLine(models.Model):
    statement = models.ForeignKey(
        "credit.Statement", related_name="lines", on_delete=models.CASCADE
    )
    type = models.CharField(max_length=20, choices=StatementLineType.choices)
    amount = models.BigIntegerField()
    transaction = models.ForeignKey(
        Transaction, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.get_type_display()} | {self.amount} | {self.created_at.date()}"

    def save(self, *args, **kwargs):
        """Override save to update parent statement balances"""
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Update parent statement balances after creating new line
        if is_new and self.statement:
            self.statement.update_balances()

    class Meta:
        verbose_name = _("سطر صورتحساب")
        verbose_name_plural = _("سطرهای صورتحساب")
        ordering = ["created_at"]
