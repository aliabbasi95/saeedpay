# kyc/services/__init__.py

from .identity_auth_service import IdentityAuthService, get_identity_auth_service

__all__ = [
    'IdentityAuthService',
    'get_identity_auth_service',
]
