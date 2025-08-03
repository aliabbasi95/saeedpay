# wallets/api/public/v1/views/installment_plan.py

from drf_spectacular.utils import extend_schema

from lib.cas_auth.views import PublicListAPIView
from wallets.api.public.v1.serializers import InstallmentPlanSerializer
from wallets.models import InstallmentPlan


@extend_schema(
    tags=["Wallet · Installment Plans"],
    summary="لیست برنامه‌های اقساطی",
    description="دریافت لیست تمام برنامه‌های اقساطی فعال یا بسته شده‌ی کاربر"
)
class InstallmentPlanListView(PublicListAPIView):
    serializer_class = InstallmentPlanSerializer

    def get_queryset(self):
        return InstallmentPlan.objects.filter(user=self.request.user).order_by(
            "-created_at"
        )
