# wallets/api/public/v1/serializers/transfer.py

from rest_framework import serializers

from wallets.api.public.v1.serializers import TransactionSerializer
from wallets.models import Wallet, WalletTransferRequest


class WalletTransferCreateSerializer(serializers.Serializer):
    """
    Validates inputs for creating a transfer request.
    Enforces:
    - Sender wallet exists and belongs to current user.
    - Receiver is provided either by wallet_id or phone_number.
    - No self-transfer between wallets of the same user.
    - Sender has enough spendable funds (balance - reserved).
    """
    sender_wallet_id = serializers.IntegerField()
    receiver_wallet_id = serializers.IntegerField(required=False)
    receiver_phone_number = serializers.CharField(
        required=False, allow_blank=True
    )
    amount = serializers.IntegerField(min_value=1)
    description = serializers.CharField(
        max_length=255, required=False, allow_blank=True
    )

    def validate(self, data):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        sender_wallet = Wallet.objects.filter(
            id=data["sender_wallet_id"]
        ).first()
        if not sender_wallet:
            raise serializers.ValidationError("کیف پول مبدا پیدا نشد.")
        if sender_wallet.user_id != getattr(user, "id", None):
            raise serializers.ValidationError("شما مالک کیف پول مبدا نیستید.")

        receiver_wallet = None
        if data.get("receiver_wallet_id"):
            receiver_wallet = Wallet.objects.filter(
                id=data["receiver_wallet_id"]
            ).first()
            if not receiver_wallet:
                raise serializers.ValidationError("کیف پول مقصد پیدا نشد.")
            if receiver_wallet.user_id == sender_wallet.user_id:
                raise serializers.ValidationError(
                    "انتقال بین کیف‌های یک نفر مجاز نیست."
                )

        receiver_phone = (data.get("receiver_phone_number") or "").strip()
        if not receiver_wallet and not receiver_phone:
            raise serializers.ValidationError("گیرنده باید مشخص شود.")

        spendable = int(sender_wallet.balance or 0) - int(
            sender_wallet.reserved_balance or 0
        )
        if spendable < int(data["amount"]):
            raise serializers.ValidationError("موجودی کافی نیست.")

        data["sender_wallet"] = sender_wallet
        data["receiver_wallet"] = receiver_wallet
        data["receiver_phone_number"] = receiver_phone or None
        return data


class WalletTransferDetailSerializer(serializers.ModelSerializer):
    """Read-only representation of a transfer request."""
    sender_wallet = serializers.StringRelatedField()
    receiver_wallet = serializers.StringRelatedField()
    transaction = TransactionSerializer(read_only=True)

    class Meta:
        model = WalletTransferRequest
        fields = [
            "id",
            "sender_wallet",
            "receiver_wallet",
            "receiver_phone_number",
            "amount",
            "description",
            "status",
            "expires_at",
            "created_at",
            "reference_code",
            "transaction",
        ]


class WalletTransferConfirmSerializer(serializers.Serializer):
    """
    Used only when the transfer was created for a phone number
    and the receiver must select a wallet to accept it.
    """
    receiver_wallet_id = serializers.IntegerField()

    def validate(self, data):
        request = self.context["request"]
        user = request.user

        receiver_wallet = Wallet.objects.filter(
            id=data["receiver_wallet_id"]
        ).first()
        if not receiver_wallet:
            raise serializers.ValidationError("کیف پول مقصد پیدا نشد.")
        if receiver_wallet.user_id != user.id:
            raise serializers.ValidationError(
                "شما فقط می‌توانید انتقال را به کیف پول خود تایید کنید."
            )

        data["receiver_wallet"] = receiver_wallet
        return data
