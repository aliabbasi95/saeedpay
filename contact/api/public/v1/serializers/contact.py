# contact/api/public/v1/views/contact.py

from rest_framework import serializers

from contact.models.contact import Contact


class ContactCreateSerializer(serializers.ModelSerializer):
    """
    Public serializer for creating contact messages.
    """

    def validate_name(self, value: str) -> str:
        value = (value or "").strip()
        if len(value) < 3:
            raise serializers.ValidationError("نام باید حداقل ۳ کاراکتر باشد.")
        return value

    def validate_message(self, value: str) -> str:
        value = (value or "").strip()
        if len(value) < 5:
            raise serializers.ValidationError("پیام خیلی کوتاه است.")
        if len(value) > 5000:
            raise serializers.ValidationError("پیام بیش از حد طولانی است.")
        return value

    class Meta:
        model = Contact
        fields = ['name', 'email', 'phone', 'message']
