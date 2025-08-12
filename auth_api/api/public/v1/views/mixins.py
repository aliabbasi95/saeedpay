# auth_api/api/public/v1/views/mixins.py

from rest_framework import status
from rest_framework.response import Response

from auth_api.tokens import CustomRefreshToken
from auth_api.utils.cookies import set_refresh_cookie


class IssueTokensResponseMixin:
    default_success_status = status.HTTP_200_OK

    def _make_tokens_payload(self, user):
        refresh = CustomRefreshToken.for_user(user)
        access = str(refresh.access_token)
        return str(refresh), access

    def build_tokens_response(self, serializer, user) -> Response:
        refresh_str, access_str = self._make_tokens_payload(user)

        payload = serializer.build_user_public_payload(user)
        payload.update({
            "access": access_str,
            "token_type": "Bearer",
        })

        resp = Response(payload, status=self.default_success_status)

        set_refresh_cookie(resp, refresh_str)
        return resp
