# auth_api/tests/public/v1/views/test_logout.py

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from auth_api.tokens import CustomRefreshToken

LOGOUT_URL = "/saeedpay/api/auth/public/v1/logout/"


@pytest.mark.django_db
class TestLogoutView:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def _issue_cookie(self, username="09120000000"):
        user = get_user_model().objects.create(username=username)
        refresh = CustomRefreshToken.for_user(user)
        self.client.cookies["sp_refresh"] = str(refresh)
        return str(refresh)

    def test_successful_logout_always_205_and_clears_cookie(self):
        self._issue_cookie()
        resp = self.client.post(LOGOUT_URL)
        assert resp.status_code == status.HTTP_205_RESET_CONTENT
        assert resp.data["detail"] == "خروج انجام شد."
        morsel = resp.cookies.get("sp_refresh")
        assert morsel is not None
        assert morsel["max-age"] == "0" or morsel.get("expires")

    def test_logout_without_cookie_is_idempotent(self):
        resp = self.client.post(LOGOUT_URL)
        assert resp.status_code == status.HTTP_205_RESET_CONTENT
        assert resp.data["detail"] == "خروج انجام شد."

    def test_logout_does_not_require_auth(self):
        self._issue_cookie("09120000001")
        # بدون Authorization
        resp = self.client.post(LOGOUT_URL)
        assert resp.status_code == status.HTTP_205_RESET_CONTENT

    def test_logout_multiple_times(self):
        self._issue_cookie("09120000002")
        r1 = self.client.post(LOGOUT_URL)
        assert r1.status_code == status.HTTP_205_RESET_CONTENT
        r2 = self.client.post(LOGOUT_URL)
        assert r2.status_code == status.HTTP_205_RESET_CONTENT
