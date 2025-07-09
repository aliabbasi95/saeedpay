# auth_api/tests/public/v1/serializers/test_login.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from auth_api.api.public.v1.serializers import LoginSerializer
from profiles.models import Profile


@pytest.mark.django_db
class TestLoginSerializer:
    def create_user(self, phone, password, is_active=True):
        user = get_user_model().objects.create(username=phone)
        Profile.objects.create(user=user, phone_number=phone)
        user.set_password(password)
        user.is_active = is_active
        user.save()
        return user

    def test_valid_credentials(self):
        user = self.create_user("09123456789", "TestPass123!")
        serializer = LoginSerializer(
            data={
                "phone_number": "09123456789",
                "password": "TestPass123!"
            }
        )
        assert serializer.is_valid()
        assert serializer.validated_data == {
            "phone_number": "09123456789", "password": "TestPass123!"
        }
        assert serializer.user == user

    def test_wrong_password(self):
        self.create_user("09123456789", "CorrectPass")
        serializer = LoginSerializer(
            data={
                "phone_number": "09123456789",
                "password": "WrongPass"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "شماره تلفن یا رمز عبور اشتباه است" in str(exc.value)

    def test_nonexistent_user(self):
        serializer = LoginSerializer(
            data={
                "phone_number": "09999999999",
                "password": "Pass123!"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "شماره تلفن یا رمز عبور اشتباه است" in str(exc.value)

    def test_inactive_user(self):
        self.create_user("09121234567", "TestPass123!", is_active=False)
        serializer = LoginSerializer(
            data={
                "phone_number": "09121234567",
                "password": "TestPass123!"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "حساب کاربری شما غیرفعال است" in str(exc.value)

    def test_empty_input(self):
        serializer = LoginSerializer(data={"phone_number": "", "password": ""})
        assert not serializer.is_valid()
        assert "phone_number" in serializer.errors
        assert "password" in serializer.errors

    def test_to_representation_no_roles(self):
        user = self.create_user("09121111111", "TestPass123!")
        serializer = LoginSerializer()
        output = serializer.to_representation(user)
        assert output["roles"] == []
        assert output["phone_number"] == "09121111111"
        assert "access" in output
        assert "refresh" in output
