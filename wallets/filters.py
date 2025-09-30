# wallets/filters.py

from django_filters import rest_framework as filters

from wallets.models import Installment, InstallmentPlan


class InstallmentFilter(filters.FilterSet):
    status = filters.CharFilter(field_name="status", lookup_expr="exact")
    due_from = filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_to = filters.DateFilter(field_name="due_date", lookup_expr="lte")

    class Meta:
        model = Installment
        fields = ["status", "due_from", "due_to"]


class InstallmentPlanFilter(filters.FilterSet):
    status = filters.CharFilter(field_name="status", lookup_expr="exact")
    created_from = filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_to = filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = InstallmentPlan
        fields = ["status", "created_from", "created_to"]
