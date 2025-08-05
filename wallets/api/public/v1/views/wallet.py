# wallets/api/public/v1/views/wallet.py

from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView

from wallets.api.public.v1.serializers import (
    WalletSerializer,
    WalletListQuerySerializer,
)
from wallets.models import Wallet


@extend_schema(
    tags=["Wallet · Wallets"],
    summary="لیست کیف پول‌های کاربر",
    description="بازگرداندن لیست کیف پول‌ها با امکان فیلتر براساس نوع مالک"
)
class WalletListView(ListAPIView):
    serializer_class = WalletSerializer

    def allow_post(self, request):
        return False

    def get_queryset(self):
        query_serializer = WalletListQuerySerializer(
            data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        owner_type = query_serializer.validated_data["owner_type"]

        qs = Wallet.objects.filter(user=self.request.user).order_by("kind")

        if owner_type:
            qs = qs.filter(owner_type=owner_type)
        return qs
