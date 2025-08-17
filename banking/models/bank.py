"""
Defines the Bank model for storing bank information.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Bank(models.Model):
    """
    Represents a bank or financial institution.
    """

    name = models.CharField(max_length=100, verbose_name=_("Name"))
    logo = models.ImageField(
        upload_to="banks/logos/", blank=True, null=True, verbose_name=_("Logo")
    )
    color = models.CharField(
        max_length=7,
        help_text=_("Hex color, e.g., “#1E88E5”"),
        verbose_name=_("Color"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Created at")
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name=_("Updated at")
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("Bank")
        verbose_name_plural = _("Banks")

    def __str__(self):
        return self.name
