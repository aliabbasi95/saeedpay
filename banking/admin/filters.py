from django.contrib import admin
from django.db import models
from django.utils.translation import gettext_lazy as _


class HasShebaFilter(admin.SimpleListFilter):
    title = _("دارای شِبا")
    parameter_name = "has_sheba"

    def lookups(self, request, model_admin):
        return [("yes", _("بله")), ("no", _("خیر"))]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(sheba__isnull=True).exclude(
                sheba__exact=""
            )
        if self.value() == "no":
            return queryset.filter(
                models.Q(sheba__isnull=True) | models.Q(sheba__exact="")
            )
        return queryset
