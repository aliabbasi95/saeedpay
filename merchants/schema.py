# merchants/schema.py
from drf_spectacular.extensions import OpenApiAuthenticationExtension

class MerchantAPIKeyAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = 'merchants.authentication.MerchantAPIKeyAuthentication'
    name = 'APIKeyAuth'
    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'ApiKey',
        }