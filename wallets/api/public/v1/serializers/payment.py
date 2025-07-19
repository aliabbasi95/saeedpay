# wallets/api/internal/v1/serializers/payment.py
import re

from rest_framework import serializers

from auth_api.models import PhoneOTP
from wallets.models import PaymentRequest
from wallets.utils.validators import https_only_validator


class PaymentRequestCreateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    return_url = serializers.URLField(
        required=True, validators=[https_only_validator]
    )
    description = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )


class PaymentRequestDetailSerializer(serializers.ModelSerializer):
    merchant_shop_name = serializers.CharField(
        source='merchant.merchant.shop_name', read_only=True
    )
    merchant_id = serializers.IntegerField(
        source='merchant.id', read_only=True
    )
    status = serializers.CharField(read_only=True)

    class Meta:
        model = PaymentRequest
        fields = [
            "reference_code",
            "amount",
            "description",
            "merchant_id",
            "merchant_shop_name",
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


class PaymentVerifyResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    payment_reference_code = serializers.CharField()
    transaction_reference_code = serializers.CharField()
    amount = serializers.IntegerField()


class PaymentRequestCreateResponseSerializer(serializers.Serializer):
    payment_request_id = serializers.IntegerField()
    payment_reference_code = serializers.CharField()
    amount = serializers.IntegerField()
    description = serializers.CharField()
    return_url = serializers.URLField()
    status = serializers.CharField()
    payment_url = serializers.URLField()


class PaymentConfirmResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    payment_reference_code = serializers.CharField()
    transaction_reference_code = serializers.CharField()
    return_url = serializers.URLField()
