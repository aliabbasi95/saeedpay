# wallets/api/public/v1/views/wallet.py
from rest_framework.mixins import ListModelMixin

from lib.cas_auth.views import PublicGenericAPIView
from wallets.api.public.v1.serializers import WalletSerializer
from wallets.models import Wallet


class WalletListView(ListModelMixin, PublicGenericAPIView):
    serializer_class = WalletSerializer

    def allow_post(self, request):
        return False

    def get_queryset(self):
        qs = Wallet.objects.filter(user=self.request.user).order_by("kind")

        owner_type = self.request.query_params.get("owner_type")
        if owner_type:
            qs = qs.filter(owner_type=owner_type)
        return qs

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
