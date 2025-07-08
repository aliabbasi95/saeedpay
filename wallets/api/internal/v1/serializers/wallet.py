# wallets/api/internal/v1/serializers/wallet.py
from django.core.validators import RegexValidator
from rest_framework import serializers

from wallets.models import Wallet


class PhoneNumberInputSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=11,
        validators=[
            RegexValidator(
                regex=r'^09\d{9}$',
                message="شماره تلفن معتبر نیست."
            ),
        ]
    )


class WalletSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(
        source="get_kind_display", read_only=True
    )

    class Meta:
        model = Wallet
        fields = [
            "kind_display",
            "balance",
        ]
        read_only_fields = fields
