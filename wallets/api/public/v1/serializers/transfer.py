# wallets/api/public/v1/serializers/transfer.py

from rest_framework import serializers

from wallets.api.public.v1.serializers import TransactionSerializer
from wallets.models import Wallet, WalletTransferRequest


class WalletTransferCreateSerializer(serializers.Serializer):
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
        sender_wallet = Wallet.objects.filter(
            id=data["sender_wallet_id"]
        ).first()
        receiver_wallet = None
        # فقط اگر انتقال مستقیم به کیف مقصد داریم
        if data.get("receiver_wallet_id"):
            receiver_wallet = Wallet.objects.filter(
                id=data["receiver_wallet_id"]
            ).first()
        if not sender_wallet:
            raise serializers.ValidationError("کیف پول مبدا پیدا نشد.")
        if sender_wallet.balance - sender_wallet.reserved_balance < data[
            "amount"]:
            raise serializers.ValidationError("موجودی کافی نیست.")
        if receiver_wallet and sender_wallet.user == receiver_wallet.user:
            raise serializers.ValidationError(
                "انتقال بین کیف‌های یک نفر مجاز نیست."
            )
        if not data.get("receiver_wallet_id") and not data.get(
                "receiver_phone_number"
        ):
            raise serializers.ValidationError("گیرنده باید مشخص شود.")
        data["sender_wallet"] = sender_wallet
        data["receiver_wallet"] = receiver_wallet
        return data


class WalletTransferDetailSerializer(serializers.ModelSerializer):
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
    receiver_wallet_id = serializers.IntegerField()

    def validate(self, data):
        user = self.context["request"].user
        receiver_wallet = Wallet.objects.filter(
            id=data["receiver_wallet_id"]
        ).first()
        if not receiver_wallet:
            raise serializers.ValidationError("کیف پول مقصد پیدا نشد.")
        if receiver_wallet.user != user:
            raise serializers.ValidationError(
                "شما فقط می‌توانید انتقال را به کیف پول خود تایید کنید."
            )
        data["receiver_wallet"] = receiver_wallet
        return data
