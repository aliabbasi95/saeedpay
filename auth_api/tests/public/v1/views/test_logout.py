# auth_api/tests/public/v1/views/test_logout.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from rest_framework_simplejwt.tokens import RefreshToken

LOGOUT_URL = "/saeedpay/api/auth/public/v1/logout/"


@pytest.mark.django_db
class TestLogoutView:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()

    def create_user_and_tokens(self, username):
        user = get_user_model().objects.create(
            username=username, password="TestPass123!"
        )
        refresh = RefreshToken.for_user(user)
        return user, str(refresh), str(refresh.access_token)

    def test_successful_logout(self):
        user, refresh, access = self.create_user_and_tokens(
            username="09123456789"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = self.client.post(LOGOUT_URL, {"refresh": refresh})

        assert response.status_code == status.HTTP_205_RESET_CONTENT
        assert response.data["detail"] == "خروج با موفقیت انجام شد."

    def test_invalid_refresh_token(self):
        user, _, access = self.create_user_and_tokens(username="09123456789")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = self.client.post(
            LOGOUT_URL, {"refresh": "invalid.token.here"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "توکن نامعتبر" in str(response.data)

    def test_missing_refresh_field(self):
        user, _, access = self.create_user_and_tokens(username="09123456789")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = self.client.post(LOGOUT_URL, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "refresh" in str(response.data)

    def test_refresh_token_does_not_belong_to_user(self):
        user1, _, access1 = self.create_user_and_tokens(username="09123456789")
        user2, refresh2, _ = self.create_user_and_tokens(
            username="09123456788"
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access1}")
        response = self.client.post(LOGOUT_URL, {"refresh": refresh2})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "توکن متعلق به کاربر جاری نیست" in str(response.data)

    def test_logout_requires_authentication(self):
        _, refresh, _ = self.create_user_and_tokens(username="09123456789")
        response = self.client.post(LOGOUT_URL, {"refresh": refresh})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_logout_with_blacklisted_refresh_token(self):
        user, refresh, access = self.create_user_and_tokens(
            username="09124440000"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        # First logout (should succeed)
        response1 = self.client.post(LOGOUT_URL, {"refresh": refresh})
        assert response1.status_code == status.HTTP_205_RESET_CONTENT

        # Second logout with same refresh (should fail)
        response2 = self.client.post(LOGOUT_URL, {"refresh": refresh})
        assert response2.status_code == status.HTTP_400_BAD_REQUEST
        assert "توکن نامعتبر" in str(response2.data)

    def test_logout_with_invalid_access_token(self):
        user, refresh, _ = self.create_user_and_tokens(username="09125550000")
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalidaccesstoken")
        response = self.client.post(LOGOUT_URL, {"refresh": refresh})
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED,
                                        status.HTTP_403_FORBIDDEN]

    def test_logout_with_refresh_as_list(self):
        user, refresh, access = self.create_user_and_tokens(
            username="09126660000"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = self.client.post(LOGOUT_URL, {"refresh": [refresh, "test"]})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout_no_data_no_auth(self):
        response = self.client.post(LOGOUT_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_logout_with_inactive_user(self):
        user, refresh, access = self.create_user_and_tokens(
            username="09127770000"
        )
        user.is_active = False
        user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.post(LOGOUT_URL, {"refresh": refresh})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_logout_with_refresh_none(self):
        user, _, access = self.create_user_and_tokens(username="09128880000")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = self.client.post(
            LOGOUT_URL, {"refresh": None}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "refresh" in response.data

    def test_logout_with_refresh_integer(self):
        user, _, access = self.create_user_and_tokens(username="09129990000")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = self.client.post(LOGOUT_URL, {"refresh": 12345})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "refresh" in response.data

    def test_logout_with_deleted_user(self):
        user, refresh, access = self.create_user_and_tokens(
            username="09121112222"
        )
        user.delete()

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.post(LOGOUT_URL, {"refresh": refresh})

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_logout_with_blacklist_error(self):
        user, refresh, access = self.create_user_and_tokens(
            username="09123334444"
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        from unittest.mock import patch

        with patch(
                "rest_framework_simplejwt.tokens.RefreshToken.blacklist"
        ) as mocked:
            mocked.side_effect = Exception("mocked error")

            response = self.client.post(LOGOUT_URL, {"refresh": refresh})
            assert response.status_code in [status.HTTP_400_BAD_REQUEST,
                                            status.HTTP_500_INTERNAL_SERVER_ERROR]

    @pytest.mark.parametrize(
        "invalid_refresh", [12345, True, {}, {"token": "val"}]
        )
    def test_refresh_token_wrong_type(self, invalid_refresh):
        user, _, access = self.create_user_and_tokens("09331110000")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.post(
            LOGOUT_URL, {"refresh": invalid_refresh}, format="json"
            )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_refresh_token_empty_string(self):
        user, _, access = self.create_user_and_tokens("09332220000")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.post(LOGOUT_URL, {"refresh": ""}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_access_token_wrong_header_format(self):
        user, refresh, _ = self.create_user_and_tokens("09334440000")
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {refresh}")
        response = self.client.post(LOGOUT_URL, {"refresh": refresh})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_refresh_token_too_long(self):
        user, _, access = self.create_user_and_tokens("09336660000")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        long_token = "a" * 10000
        response = self.client.post(LOGOUT_URL, {"refresh": long_token})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_refresh_token_missing_user_id(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        user, _, access = self.create_user_and_tokens("09338880000")
        refresh = RefreshToken()
        refresh["some"] = "value"
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.post(LOGOUT_URL, {"refresh": str(refresh)})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_refresh_token_empty_string(self):
        user, refresh, access = self.create_user_and_tokens("09000000000")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.post(LOGOUT_URL, {"refresh": ""})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "refresh" in str(response.data).lower()

    def test_refresh_token_with_extra_spaces(self):
        user, refresh, access = self.create_user_and_tokens("09000000001")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        token_with_spaces = f"  {refresh}  "
        response = self.client.post(LOGOUT_URL, {"refresh": token_with_spaces})
        assert response.status_code == status.HTTP_205_RESET_CONTENT

    def test_refresh_token_with_access_token_instead(self):
        user, refresh, access = self.create_user_and_tokens("09000000002")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.post(LOGOUT_URL, {"refresh": access})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "توکن نامعتبر" in str(response.data)

    def test_logout_with_wrong_content_type(self):
        user, refresh, access = self.create_user_and_tokens("09009990000")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.post(
            LOGOUT_URL,
            data=f"refresh={refresh}",
            content_type="text/plain"
        )
        assert response.status_code in [status.HTTP_400_BAD_REQUEST,
                                        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE]

    def test_access_token_still_usable_after_logout(self):
        user, refresh, access = self.create_user_and_tokens("09008880000")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        response = self.client.post(LOGOUT_URL, {"refresh": refresh})
        assert response.status_code == status.HTTP_205_RESET_CONTENT

        response = self.client.get(
            "/saeedpay/api/auth/public/v1/logout/"
            )
        assert response.status_code in [status.HTTP_200_OK,
                                        status.HTTP_405_METHOD_NOT_ALLOWED]

