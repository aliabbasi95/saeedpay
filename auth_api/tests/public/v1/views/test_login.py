# auth_api/tests/public/v1/views/test_login.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

LOGIN_URL = '/saeedpay/api/auth/public/v1/login/'


@pytest.mark.django_db
class TestLoginView:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def create_user(self, phone, password, is_active=True):
        user = get_user_model().objects.create(username=phone)
        user.set_password(password)
        user.is_active = is_active
        user.save()
        return user

    def test_successful_login(self):
        user = self.create_user("09123456789", "MyStrongPass123")
        response = self.client.post(
            LOGIN_URL, {
                "phone_number": "09123456789",
                "password": "MyStrongPass123"
            }
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["user_id"] == user.id
        assert "access" in response.data

    def test_wrong_password(self):
        self.create_user("09123456789", "CorrectPassword")
        response = self.client.post(
            LOGIN_URL, {
                "phone_number": "09123456789",
                "password": "WrongPassword"
            }
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "شماره تلفن یا رمز عبور اشتباه است" in str(response.data)

    def test_nonexistent_user(self):
        response = self.client.post(
            LOGIN_URL, {
                "phone_number": "09999999999",
                "password": "AnyPassword"
            }
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "شماره تلفن یا رمز عبور اشتباه است" in str(response.data)

    def test_inactive_user(self):
        self.create_user("09121234567", "MyPassword123", is_active=False)
        response = self.client.post(
            LOGIN_URL, {
                "phone_number": "09121234567",
                "password": "MyPassword123"
            }
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "حساب کاربری شما غیرفعال است" in str(response.data)

    def test_missing_fields(self):
        response = self.client.post(LOGIN_URL, {"phone_number": "09121234567"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in str(response.data)

        response = self.client.post(LOGIN_URL, {"password": "somepass"})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "phone_number" in str(response.data)

    def test_empty_fields(self):
        response = self.client.post(
            LOGIN_URL, {"phone_number": "", "password": ""}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_user_without_roles(self):
        self.create_user("09121111111", "NoRolePass")
        response = self.client.post(
            LOGIN_URL, {
                "phone_number": "09121111111",
                "password": "NoRolePass"
            }
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["roles"] == []

    def test_access_token_format(self):
        user = self.create_user("09301234567", "MyPass123!")
        response = self.client.post(
            LOGIN_URL, {
                "phone_number": "09301234567",
                "password": "MyPass123!"
            }
            )
        token = response.data["access"]
        assert len(token.split(".")) == 3

