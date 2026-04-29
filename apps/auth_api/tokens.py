# auth_api/tokens.py

from rest_framework_simplejwt.tokens import RefreshToken


class CustomRefreshToken(RefreshToken):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if "orig_iat" not in self.payload:
            self.payload["orig_iat"] = self.payload["iat"]

    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        if "orig_iat" not in token.payload and "iat" in token.payload:
            token["orig_iat"] = token["iat"]
        token["is_active_at_issue"] = bool(getattr(user, "is_active", True))
        return token
