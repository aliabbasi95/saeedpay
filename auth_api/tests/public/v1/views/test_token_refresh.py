# auth_api/tests/public/v1/views/test_token_refresh.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from auth_api.tokens import CustomRefreshToken

REFRESH_URL = "/saeedpay/api/auth/public/v1/token/refresh/"


@pytest.mark.django_db
class TestTokenRefreshAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def create_refresh_token(self, username):
        user = get_user_model().objects.create(username=username)
        refresh = CustomRefreshToken.for_user(user)
        return str(refresh), str(refresh.access_token)

    def test_refresh_success(self):
        refresh, _ = self.create_refresh_token("09120000001")
        response = self.client.post(REFRESH_URL, {"refresh": refresh})
        print(response.data)
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_invalid_refresh_token(self):
        response = self.client.post(
            REFRESH_URL, {"refresh": "bad.token.string"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "access" not in response.data

    def test_missing_refresh_token_field(self):
        response = self.client.post(REFRESH_URL, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "refresh" in str(response.data)

    def test_blacklisted_refresh_token(self):
        refresh, _ = self.create_refresh_token("09120000002")
        # Blacklist the refresh token
        token = CustomRefreshToken(refresh)
        token.blacklist()

        response = self.client.post(REFRESH_URL, {"refresh": refresh})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_with_access_token(self):
        _, access = self.create_refresh_token("09120000003")
        response = self.client.post(REFRESH_URL, {"refresh": access})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "access" not in response.data

    def test_refresh_with_malformed_token(self):
        malformed_token = "invalidtokenwithoutdots"
        response = self.client.post(REFRESH_URL, {"refresh": malformed_token})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_with_inactive_user(self):
        user = get_user_model().objects.create(
            username="09120000004", is_active=False
        )
        refresh = CustomRefreshToken.for_user(user)
        response = self.client.post(REFRESH_URL, {"refresh": str(refresh)})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
