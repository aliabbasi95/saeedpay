# banking/api/public/v1/serializers/bank_card.py

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from banking.models import BankCard
from banking.services import bank_card_service
from banking.utils.choices import BankCardStatus


class BankCardSerializer(serializers.ModelSerializer):
    last4 = serializers.CharField(read_only=True)

    class Meta:
        model = BankCard
        fields = [
            "id",
            "bank",
            "last4",
            "card_holder_name",
            "is_default",
            "status",
            "is_active",
            "sheba",
            "created_at",
            "last_used",
            "rejection_reason",
        ]


class BankCardCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankCard
        fields = [
            "card_number",
        ]
        extra_kwargs = {"card_number": {"write_only": True}}

    def validate_card_number(self, value):
        value = bank_card_service.normalize_card_number(value)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not bank_card_service.is_luhn_valid(value):
            raise serializers.ValidationError(_("شماره کارت نامعتبر است."))
        # Check for duplicate card for this user (any status)
        if user and BankCard.objects.filter(
                user=user, card_number=value
        ).exists():
            raise serializers.ValidationError(
                _("شما قبلاً این کارت را ثبت کرده‌اید.")
            )
        # Check for globally verified card
        if BankCard.objects.filter(
                card_number=value, status=BankCardStatus.VERIFIED
        ).exists():
            raise serializers.ValidationError(
                _("این شماره کارت قبلاً توسط کاربر دیگری تأیید شده است.")
            )
        return value

    def create(self, validated_data):
        validated_data[
            "card_number"] = bank_card_service.normalize_card_number(
            validated_data["card_number"]
        )
        validated_data["status"] = BankCardStatus.PENDING
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class BankCardUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankCard
        fields = [
            "card_number",
        ]

    def validate(self, attrs):
        if self.instance.status == BankCardStatus.PENDING:
            raise serializers.ValidationError(
                _("کارت‌های در حال بررسی قابل ویرایش نیستند.")
            )
        if self.instance.status != BankCardStatus.REJECTED:
            raise serializers.ValidationError(
                _("تنها کارت‌های رد شده قابل ویرایش هستند.")
            )
        return attrs

    def validate_card_number(self, value):
        if not bank_card_service.is_luhn_valid(value):
            raise serializers.ValidationError(_("شماره کارت نامعتبر است."))

        user = self.context["request"].user
        if BankCard.objects.filter(user=user, card_number=value).exclude(
                pk=self.instance.pk
        ).exists():
            raise serializers.ValidationError(
                _("شما قبلاً این کارت را ثبت کرده‌اید.")
            )
        if BankCard.objects.filter(
                card_number=value, status=BankCardStatus.VERIFIED
        ).exclude(user=user).exists():
            raise serializers.ValidationError(
                _("این شماره کارت قبلاً توسط کاربر دیگری تأیید شده است.")
            )
        return value

    def update(self, instance, validated_data):
        instance.status = BankCardStatus.PENDING
        instance.rejection_reason = None
        return super().update(instance, validated_data)
