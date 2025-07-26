# wallets/api/internal/v1/views/wallet.py

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from lib.cas_auth.views import CasAuthAPIView
from profiles.models import Profile
from wallets.api.internal.v1.serializers import (
    WalletSerializer,
    NationalIdInputSerializer,
)
from wallets.models import Wallet
from wallets.utils.choices import OwnerType


class InternalCustomerWalletListByNationalIdView(CasAuthAPIView):
    authentication_classes = (AllowAny,)
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = NationalIdInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            profile = Profile.objects.get(
                national_id=serializer.validated_data["national_id"]
            )
            user = profile.user
        except Profile.DoesNotExist:
            return Response(
                {"detail": "کاربری با این کد ملی پیدا نشد."},
                status=status.HTTP_404_NOT_FOUND
            )

        wallets = Wallet.objects.filter(
            user=user, owner_type=OwnerType.CUSTOMER
        ).order_by("kind")
        wallet_serializer = WalletSerializer(wallets, many=True)
        return Response(wallet_serializer.data, status=status.HTTP_200_OK)
