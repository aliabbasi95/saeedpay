# store/api/public/v1/views/contract.py

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.mixins import (
    CreateModelMixin, ListModelMixin,
    RetrieveModelMixin, UpdateModelMixin,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from merchants.permissions import IsMerchant
from store.api.public.v1.serializers import StoreContractSerializer
from store.models import StoreContract


@extend_schema(
    tags=["Store · Contract"],
    summary="ثبت قرارداد جدید فروشگاه",
    description="ثبت یا بروزرسانی قرارداد فروشگاه توسط فروشنده. فقط یک قرارداد فعال مجاز است."
)
class StoreContractViewSet(
    CreateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    GenericViewSet
):
    permission_classes = [IsAuthenticated, IsMerchant]
    queryset = StoreContract.objects.all()
    serializer_class = StoreContractSerializer

    def get_queryset(self):
        return StoreContract.objects.filter(
            store__merchant=self.request.user.merchant
        )

    def perform_create(self, serializer):
        store = serializer.validated_data["store"]

        if store.merchant != self.request.user.merchant:
            raise ValidationError("دسترسی به این فروشگاه مجاز نیست.")

        StoreContract.objects.filter(store=store, active=True).update(
            active=False
        )

        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.get_status_number() == 2:
            raise ValidationError("ویرایش قرارداد تأییدشده مجاز نیست.")
        serializer.save()
