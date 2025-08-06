# banking/api/public/v1/serializers/bank_card.py

from rest_framework import serializers

from banking.utils.choices import BankCardStatus
from django.utils.translation import gettext_lazy as _

from banking.models import BankCard
from banking.services import bank_card_service


class BankCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankCard
        fields = [
            "id",
            "bank",
            "card_number",
            "card_holder_name",
            "is_default",
            "status",
            "is_active",
            "sheba",
            "added_at",
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
        if not bank_card_service.is_luhn_valid(value):
            raise serializers.ValidationError(_("شماره کارت نامعتبر است."))
        return value

    def create(self, validated_data):
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
        return value

    def update(self, instance, validated_data):
        instance.status = BankCardStatus.PENDING
        instance.rejection_reason = None
        return super().update(instance, validated_data)
