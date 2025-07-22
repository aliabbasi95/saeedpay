from django.contrib.auth import password_validation
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from lib.erp_base.serializers.persian_error_message import PersianValidationErrorMessages

class ChangePasswordSerializer(PersianValidationErrorMessages, serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        try:
            password_validation.validate_password(password=value, user=self.context['request'].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value

    def validate(self, data):
        user = self.context['request'].user
        
        # Validate current password
        if not user.check_password(data['current_password']):
            raise serializers.ValidationError(
                {'current_password': 'رمز عبور فعلی اشتباه است.'}
            )
        
        # Validate password confirmation
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'رمز عبور جدید و تکرار آن یکسان نیستند.'}
            )
        
        # Validate that new password is different from current
        if data['current_password'] == data['new_password']:
            raise serializers.ValidationError(
                {'new_password': 'رمز عبور جدید نباید با رمز عبور فعلی یکسان باشد.'}
            )
        
        return data

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user 