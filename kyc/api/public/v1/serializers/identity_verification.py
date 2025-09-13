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
        """Validate national ID format."""
        if value and not validate_national_id(value):
            raise serializers.ValidationError("Invalid national ID format")
        return value
    
    def validate_phone(self, value):
        """Validate phone number format."""
        if value and not validate_phone_number(value):
            raise serializers.ValidationError("Invalid phone number format")
        return value
    
    def validate(self, data):
        """Validate that at least one required field is provided."""
        if not any(data.get(field) for field in ['national_id', 'phone']):
            raise serializers.ValidationError(
                "At least one of national_id or phone must be provided"
            )
        return data
