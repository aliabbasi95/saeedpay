# wallets/api/public/v1/views/installment.py

from rest_framework.mixins import ListModelMixin, RetrieveModelMixin

from lib.cas_auth.views import PublicGenericAPIView
from wallets.api.public.v1.serializers.installment import InstallmentSerializer
from wallets.models import Installment


class InstallmentListView(ListModelMixin, PublicGenericAPIView):
    serializer_class = InstallmentSerializer

    def get_queryset(self):
        return Installment.objects.filter(
            plan__user=self.request.user
        ).select_related("plan", "transaction").order_by("due_date")


class InstallmentsByPlanView(ListModelMixin, PublicGenericAPIView):
    serializer_class = InstallmentSerializer

    def get_queryset(self):
        return Installment.objects.filter(
            plan__id=self.kwargs["plan_id"],
            plan__user=self.request.user
        ).select_related("plan", "transaction").order_by("due_date")


class InstallmentDetailView(RetrieveModelMixin, PublicGenericAPIView):
    serializer_class = InstallmentSerializer

    def get_queryset(self):
        return Installment.objects.filter(plan__user=self.request.user)
