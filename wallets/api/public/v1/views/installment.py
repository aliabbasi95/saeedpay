# wallets/api/public/v1/views/installment.py

from lib.cas_auth.views import (
    PublicRetrieveAPIView,
    PublicListAPIView,
)
from wallets.api.public.v1.serializers.installment import InstallmentSerializer
from wallets.models import Installment


class InstallmentListView(PublicListAPIView):
    serializer_class = InstallmentSerializer

    def get_queryset(self):
        return Installment.objects.filter(
            plan__user=self.request.user
        ).select_related("plan", "transaction").order_by("due_date")


class InstallmentsByPlanView(PublicListAPIView):
    serializer_class = InstallmentSerializer

    def get_queryset(self):
        return Installment.objects.filter(
            plan__id=self.kwargs["plan_id"],
            plan__user=self.request.user
        ).select_related("plan", "transaction").order_by("due_date")


class InstallmentDetailView(PublicRetrieveAPIView):
    serializer_class = InstallmentSerializer

    def get_queryset(self):
        return Installment.objects.filter(plan__user=self.request.user)
