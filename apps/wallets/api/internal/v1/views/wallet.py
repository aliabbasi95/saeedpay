# apps/wallets/api/internal/v1/views/wallet.py

from rest_framework import status
from rest_framework.response import Response

from apps.profiles.models import Profile
from apps.wallets.api.internal.v1.schema.wallet import (
    internal_customer_wallets_by_national_id_schema,
)
from apps.wallets.api.internal.v1.serializers import (
    NationalIdInputSerializer,
    WalletSerializer,
)
from apps.wallets.models import Wallet
from apps.wallets.utils.choices import OwnerType
from lib.cas_auth.views import CasAuthAPIView


class InternalCustomerWalletListByNationalIdView(CasAuthAPIView):
    serializer_class = WalletSerializer

    @internal_customer_wallets_by_national_id_schema
    def post(self, request):
        serializer = NationalIdInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            profile = Profile.objects.get(
                national_id=serializer.validated_data["national_id"]
            )
            user = profile.user
        except Profile.DoesNotExist:
            return Response(
                {"detail": "کاربری با این کد ملی پیدا نشد."},
                status=status.HTTP_404_NOT_FOUND,
            )

        wallets = Wallet.objects.filter(
            user=user, owner_type=OwnerType.CUSTOMER
        ).order_by("kind")
        wallet_serializer = self.get_serializer(wallets, many=True)
        return Response(wallet_serializer.data, status=status.HTTP_200_OK)
