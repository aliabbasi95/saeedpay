# wallets/api/public/v1/views/transfer.py

from django.db import models
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError

from lib.cas_auth.views import PublicAPIView
from wallets.api.public.v1.serializers import (
    WalletTransferCreateSerializer,
    WalletTransferDetailSerializer,
    WalletTransferConfirmSerializer,
)
from wallets.models import WalletTransferRequest
from wallets.services import (
    create_wallet_transfer_request,
    confirm_wallet_transfer_request,
    reject_wallet_transfer_request,
)
from wallets.services.transfer import check_and_expire_transfer_request
from wallets.utils.choices import TransferStatus


@extend_schema(
    tags=["Wallet · Transfers"],
    summary="لیست یا ایجاد انتقال کیف پول",
    description="درخواست ایجاد انتقال کیف پول یا مشاهده لیست انتقال‌های مرتبط با کاربر"
)
class WalletTransferListCreateView(PublicAPIView):
    serializer_class = WalletTransferCreateSerializer

    def get(self, request):
        user = request.user
        phone = getattr(user.profile, "phone_number", None)
        role = request.query_params.get("role", "all")
        status_param = request.query_params.get("status")

        if role == "sender":
            queryset = WalletTransferRequest.objects.filter(
                sender_wallet__user=user
            )
        elif role == "receiver":
            queryset = WalletTransferRequest.objects.filter(
                models.Q(receiver_wallet__user=user) |
                models.Q(receiver_phone_number=phone)
            )
        else:  # all
            queryset = WalletTransferRequest.objects.filter(
                models.Q(sender_wallet__user=user) |
                models.Q(receiver_wallet__user=user) |
                models.Q(receiver_phone_number=phone)
            ).distinct()

        if status_param:
            queryset = queryset.filter(status=status_param)
        queryset = queryset.order_by("-created_at")

        self.response_data = WalletTransferDetailSerializer(
            queryset, many=True
        ).data
        self.response_status = 200
        return self.response

    def perform_save(self, serializer):
        req = create_wallet_transfer_request(
            sender_wallet=serializer.validated_data["sender_wallet"],
            amount=serializer.validated_data["amount"],
            receiver_wallet=serializer.validated_data.get("receiver_wallet"),
            receiver_phone=serializer.validated_data.get(
                "receiver_phone_number"
            ),
            description=serializer.validated_data.get("description", ""),
            creator=self.request.user
        )
        self.response_data = WalletTransferDetailSerializer(req).data
        self.response_status = status.HTTP_201_CREATED


@extend_schema(
    request=WalletTransferConfirmSerializer,
    responses={200: WalletTransferDetailSerializer},
    tags=["Wallet · Transfers"],
    summary="تایید انتقال کیف پول",
    description="تایید انتقال برای کیف پول دریافتی یا شماره موبایل ثبت‌شده"
)
class WalletTransferConfirmView(PublicAPIView):
    serializer_class = WalletTransferConfirmSerializer

    def post(self, request, pk):
        transfer = WalletTransferRequest.objects.filter(pk=pk).first()
        if not transfer:
            self.response_data = {"detail": "درخواست انتقال پیدا نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        user = request.user
        if transfer.receiver_phone_number:
            if not hasattr(
                    user, "profile"
            ) or user.profile.phone_number != transfer.receiver_phone_number:
                self.response_data = {
                    "detail": "شما مجاز به تایید این انتقال نیستید."
                }
                self.response_status = status.HTTP_403_FORBIDDEN
                return self.response
        else:
            if not transfer.receiver_wallet or transfer.receiver_wallet.user != user:
                self.response_data = {
                    "detail": "شما مجاز به تایید این انتقال نیستید."
                }
                self.response_status = status.HTTP_403_FORBIDDEN
                return self.response

        check_and_expire_transfer_request(transfer)
        if not transfer:
            self.response_data = {"detail": "درخواست انتقال پیدا نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response
        if transfer.receiver_phone_number and not transfer.receiver_wallet:
            serializer = self.get_serializer(
                data=request.data,
                context={'request': self.request}
            )
            serializer.is_valid(raise_exception=True)
            try:
                transfer = confirm_wallet_transfer_request(
                    transfer,
                    serializer.validated_data["receiver_wallet"],
                    request.user
                )
                self.response_data = WalletTransferDetailSerializer(
                    transfer
                ).data
                self.response_status = status.HTTP_200_OK
            except ValidationError as e:
                message = e.detail[0] if isinstance(e.detail, list) else str(
                    e.detail
                )
                self.response_data = {"detail": message}
                self.response_status = status.HTTP_400_BAD_REQUEST
            except Exception as e:
                self.response_data = {"detail": str(e)}
                self.response_status = status.HTTP_400_BAD_REQUEST
            return self.response
        self.response_data = {"detail": "انتقال قابل تایید نیست."}
        self.response_status = status.HTTP_400_BAD_REQUEST
        return self.response


@extend_schema(
    responses={200: WalletTransferDetailSerializer},
    tags=["Wallet · Transfers"],
    summary="رد انتقال کیف پول",
    description="رد کردن درخواست انتقال دریافتی توسط کاربر"
)
class WalletTransferRejectView(PublicAPIView):
    serializer_class = WalletTransferDetailSerializer

    def post(self, request, pk):
        transfer = WalletTransferRequest.objects.filter(pk=pk).first()
        if not transfer:
            self.response_data = {"detail": "درخواست انتقال پیدا نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response

        user = request.user
        if transfer.receiver_phone_number:
            if not hasattr(
                    user, "profile"
            ) or user.profile.phone_number != transfer.receiver_phone_number:
                self.response_data = {
                    "detail": "شما مجاز به رد این انتقال نیستید."
                }
                self.response_status = status.HTTP_403_FORBIDDEN
                return self.response
        elif transfer.receiver_wallet and transfer.receiver_wallet.user != user:
            self.response_data = {
                "detail": "شما مجاز به رد این انتقال نیستید."
            }
            self.response_status = status.HTTP_403_FORBIDDEN
            return self.response
        if not transfer:
            self.response_data = {"detail": "درخواست انتقال پیدا نشد."}
            self.response_status = status.HTTP_404_NOT_FOUND
            return self.response
        if transfer.status != TransferStatus.PENDING_CONFIRMATION:
            self.response_data = {"detail": "درخواست قابل رد کردن نیست."}
            self.response_status = status.HTTP_400_BAD_REQUEST
            return self.response
        try:
            transfer = reject_wallet_transfer_request(transfer)
            self.response_data = self.serializer_class(transfer).data
            self.response_status = status.HTTP_200_OK
        except Exception as e:
            self.response_data = {"detail": str(e)}
            self.response_status = status.HTTP_400_BAD_REQUEST
        return self.response
