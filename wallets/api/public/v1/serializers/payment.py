# wallets/api/public/v1/serializers/payment.py
import re

from rest_framework import serializers

from auth_api.models import PhoneOTP
from wallets.models import PaymentRequest


class PaymentRequestDetailSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(
        source='store.name', read_only=True
    )
    store_id = serializers.IntegerField(
        source='store.id', read_only=True
    )
    status = serializers.CharField(read_only=True)

    class Meta:
        model = PaymentRequest
        fields = [
            "reference_code",
            "amount",
            "description",
            "store_id",
            "store_name",
            "status",
            "expires_at",
        ]


class PaymentConfirmSerializer(serializers.Serializer):
    wallet_id = serializers.IntegerField()
    code = serializers.CharField()

    def validate(self, data):
        user = self.context["request"].user
        phone_number = user.profile.phone_number

        if not phone_number or not re.match(r'^09\d{9}$', phone_number):
            raise serializers.ValidationError(
                {"phone_number": ["شماره تلفن معتبر نیست."]}
            )

        code = data.get("code")
        try:
            otp_instance = PhoneOTP.objects.get(phone_number=phone_number)
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError(
                {"code": "کد تایید یافت نشد یا منقضی شده است."}
            )

        if not otp_instance.verify(code):
            raise serializers.ValidationError(
                {"code": "کد تایید اشتباه یا منقضی شده است."}
            )

        return data


class PaymentConfirmResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    payment_reference_code = serializers.CharField()
    transaction_reference_code = serializers.CharField()
    return_url = serializers.URLField()
