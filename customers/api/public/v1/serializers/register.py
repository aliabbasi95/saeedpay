# customers/api/public/v1/serializers/register.py
from django.contrib.auth import get_user_model
from rest_framework import serializers

from customers.models import Customer, PhoneOTP


class RegisterSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    code = serializers.CharField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        phone_number = data.get("phone_number")
        code = data.get("code")
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        try:
            otp_instance = PhoneOTP.objects.get(phone_number=phone_number)
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError(
                {"code": ["Invalid OTP or OTP expired."]}
            )

        if otp_instance and otp_instance.verify(code):
            return data
        raise serializers.ValidationError(
            {"code": ["Invalid OTP or OTP expired."]}
        )

    def create(self, validated_data):
        phone_number = validated_data['phone_number']
        password = validated_data['password']

        user = get_user_model().objects.create(username=phone_number)
        user.set_password(password)
        user.save()

        Customer.objects.create(user=user, phone_number=phone_number)
        self.user = user
        return user
    def to_representation(self, instance):
        return instance.tokens()