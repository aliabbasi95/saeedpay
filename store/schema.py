# store/schema.py

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class StoreApiKeyAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = 'store.authentication.StoreApiKeyAuthentication'
    name = 'APIKeyAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'ApiKey',
        }
