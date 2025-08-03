# wallets/api/public/v1/views/installment_plan.py

from rest_framework.mixins import ListModelMixin

from lib.cas_auth.views import PublicGenericAPIView
from wallets.api.public.v1.serializers import InstallmentPlanSerializer
from wallets.models import InstallmentPlan


class InstallmentPlanListView(ListModelMixin, PublicGenericAPIView):
    serializer_class = InstallmentPlanSerializer

    def get_queryset(self):
        return InstallmentPlan.objects.filter(user=self.request.user).order_by(
            "-created_at"
        )
