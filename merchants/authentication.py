# merchants/authentication.py
import hashlib

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from merchants.models import MerchantApiKey


class MerchantAPIKeyAuthentication(BaseAuthentication):
    keyword = "ApiKey"

    def authenticate(self, request):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith(self.keyword + " "):
            return None

        api_key = auth[len(self.keyword) + 1:]
        key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

        try:
            api_key_obj = MerchantApiKey.objects.get(
                key_hash=key_hash, is_active=True
            )
        except MerchantApiKey.DoesNotExist:
            raise AuthenticationFailed("Invalid API Key")

        user = api_key_obj.merchant.user
        return (user, None)
