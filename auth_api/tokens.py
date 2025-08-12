# auth_api/tokens.py

from rest_framework_simplejwt.tokens import RefreshToken


class CustomRefreshToken(RefreshToken):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'orig_iat' not in self.payload:
            self.payload['orig_iat'] = self.payload['iat']
