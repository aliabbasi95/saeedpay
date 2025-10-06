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

    def _cookie_for(self, username):
        user = get_user_model().objects.create(username=username)
        r = CustomRefreshToken.for_user(user)
        self.client.cookies["sp_refresh"] = str(r)
        return user, r

    def test_refresh_success_from_cookie(self):
        _, r = self._cookie_for("09120000001")
        resp = self.client.post(REFRESH_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert "access" in resp.data
        assert "sp_refresh" in resp.cookies

    def test_missing_refresh_cookie(self):
        resp = self.client.post(REFRESH_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_blacklisted_refresh_token(self):
        user = get_user_model().objects.create(username="09120000002")
        refresh = CustomRefreshToken.for_user(user)
        CustomRefreshToken(str(refresh)).blacklist()
        self.client.cookies["sp_refresh"] = str(refresh)
        response = self.client.post(REFRESH_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_with_inactive_or_deleted_user(self):
        user, _ = self._cookie_for("09120000004")
        user.is_active = False
        user.save()
        resp = self.client.post(REFRESH_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_with_inactive_user(self):
        user = get_user_model().objects.create(
            username="09120000004",
            is_active=False
        )
        refresh = CustomRefreshToken.for_user(user)
        self.client.cookies["sp_refresh"] = str(refresh)
        response = self.client.post(REFRESH_URL)
        assert response.status_code == status.HTTP_200_OK
