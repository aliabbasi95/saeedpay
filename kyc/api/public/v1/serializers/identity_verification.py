# kyc/api/public/v1/serializers/identity_verification.py

from rest_framework import serializers

from kyc.utils import validate_national_id, validate_phone_number


class IdentityVerificationSerializer(serializers.Serializer):
    """
    Serializer for identity verification requests.
    """
    national_id = serializers.CharField(
        max_length=10,
        required=False,
        help_text="Iranian national ID (10 digits)"
    )
    phone = serializers.CharField(
        max_length=15,
        required=False,
        help_text="Iranian phone number (09xxxxxxxxx)"
    )
    first_name = serializers.CharField(
        max_length=100,
        required=False,
        help_text="User's first name"
    )
    last_name = serializers.CharField(
        max_length=100,
        required=False,
        help_text="User's last name"
    )

    def validate_national_id(self, value):
        v = (value or "").strip()
        if v and not validate_national_id(v):
            raise serializers.ValidationError("Invalid national ID format.")
        return v

    def validate_phone(self, value):
        v = (value or "").strip()
        if v and not validate_phone_number(v):
            raise serializers.ValidationError("Invalid phone number format.")
        return v

    def validate(self, attrs):
        if not any(
                [(attrs.get("national_id") or "").strip(),
                 (attrs.get("phone") or "").strip()]
        ):
            raise serializers.ValidationError(
                "At least one of national_id or phone must be provided."
            )
        return attrs
