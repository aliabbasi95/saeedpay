# wallets/api/public/v1/views/installment.py

from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView

from wallets.api.public.v1.serializers.installment import InstallmentSerializer
from wallets.models import Installment


@extend_schema(
    tags=["Wallet · Installments"],
    summary="لیست همه اقساط کاربر",
    description="دریافت تمام اقساط متعلق به کاربر، مرتب‌شده بر اساس تاریخ سررسید"
)
class InstallmentListView(ListAPIView):
    serializer_class = InstallmentSerializer

    def get_queryset(self):
        return Installment.objects.filter(
            plan__user=self.request.user
        ).select_related("plan", "transaction").order_by("due_date")


@extend_schema(
    tags=["Wallet · Installments"],
    summary="لیست اقساط مرتبط با یک برنامه خاص",
    description="دریافت لیست اقساط برای برنامه اقساطی مشخص‌شده با شناسه plan_id"
)
class InstallmentsByPlanView(ListAPIView):
    serializer_class = InstallmentSerializer

    def get_queryset(self):
        return Installment.objects.filter(
            plan__id=self.kwargs["plan_id"],
            plan__user=self.request.user
        ).select_related("plan", "transaction").order_by("due_date")


@extend_schema(
    tags=["Wallet · Installments"],
    summary="جزئیات یک قسط",
    description="دریافت اطلاعات کامل یک قسط شامل تاریخ، مبلغ، وضعیت، جریمه و تراکنش مرتبط"
)
class InstallmentDetailView(RetrieveAPIView):
    serializer_class = InstallmentSerializer

    def get_queryset(self):
        return Installment.objects.filter(plan__user=self.request.user)
