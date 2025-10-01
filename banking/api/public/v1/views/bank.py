# banking/api/public/v1/views/bank.py

from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from banking.api.public.v1.schema import bank_viewset_schema
from banking.api.public.v1.serializers import (
    BankSerializer,
    BankDetailSerializer,
)
from banking.models import Bank


@bank_viewset_schema
class BankViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Public read-only list & retrieve of banks.
    """
    queryset = Bank.objects.all().order_by("name")
    permission_classes = [AllowAny]
    lookup_field = "id"
    pagination_class = None  # small, static catalog

    def get_serializer_class(self):
        return BankDetailSerializer if self.action == "retrieve" else BankSerializer
