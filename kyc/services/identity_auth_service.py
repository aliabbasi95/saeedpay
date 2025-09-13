# kyc/services/identity_auth_service.py

import logging
import os
import requests
import jwt
import time
from json import JSONDecodeError
from typing import Dict, Optional, Tuple
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class IdentityAuthService:
    """
    Service for handling user identity authentication with external KYC provider.
    
    This service manages access and refresh tokens for external identity verification
    and can be used across different apps in the project.
    """
    
    def __init__(self):
        self.base_url = getattr(settings, 'KYC_IDENTITY_BASE_URL', '')
        self.username = os.environ.get('KIAHOOSHAN_USERNAME', '')
        self.password = os.environ.get('KIAHOOSHAN_PASSWORD', '')
        self.timeout = getattr(settings, 'KYC_IDENTITY_TIMEOUT', 30)
        self.cache_key_prefix = 'kyc_identity_'
        
        if not all([self.base_url, self.username, self.password]):
            logger.warning("KYC Identity service configuration incomplete")
    
    def _get_cache_key(self, key_suffix: str) -> str:
        """Generate cache key with prefix."""
        return f"{self.cache_key_prefix}{key_suffix}"
    
    def _retry_with_exponential_backoff(self, func, max_retries: int = 3, base_delay: float = 1.0):
        """
        Retry a function with exponential backoff.
        
        Args:
            func: Function to retry
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            
        Returns:
            Function result or raises the last exception
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func()
            except (requests.exceptions.RequestException, JSONDecodeError) as e:
                last_exception = e
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f} seconds..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries + 1} attempts failed. Last error: {e}")
            except Exception as e:
                # Let unexpected exceptions propagate immediately
                logger.error(f"Unexpected error during retry attempt {attempt + 1}: {e}")
                raise
        
        # If we get here, all retries failed
        raise last_exception
    
    def _is_token_valid(self, token: str, token_type: str = 'access') -> bool:
        """
        Check if a token is still valid (not expired).
        
        Args:
            token: The token to validate
            token_type: Type of token ('access' or 'refresh')
            
        Returns:
            bool: True if token is valid, False otherwise
        """
        if not token:
            return False
            
        try:
            # Try to decode JWT token to check expiration
            decoded = jwt.decode(token, options={"verify_signature": False})
            exp_timestamp = decoded.get('exp')
            
            if exp_timestamp:
                exp_datetime = datetime.fromtimestamp(exp_timestamp)
                return exp_datetime > timezone.now()
            
            return True  # If no expiration, assume valid
        except jwt.ExpiredSignatureError:
            logger.info(f"{token_type} token has expired")
            return False
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid {token_type} token: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error during {token_type} token validation: {e}")
            return False
    
    def _authenticate(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Authenticate with the identity service and get tokens.
        
        Returns:
            Tuple of (access_token, refresh_token) or (None, None) on failure
        """
        if not all([self.base_url, self.username, self.password]):
            logger.error("KYC Identity service not properly configured")
            return None, None
        
        auth_url = f"{self.base_url.rstrip('/')}/auth/login"
        
        def _make_auth_request():
            payload = {
                'username': self.username,
                'password': self.password
            }
            
            response = requests.post(
                auth_url,
                json=payload,
                timeout=self.timeout,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'SaeedPay-KYC-Service/1.0'
                }
            )
            
            response.raise_for_status()
            return response
        
        try:
            response = self._retry_with_exponential_backoff(_make_auth_request)
            data = response.json()
            
            access_token = data.get('access_token')
            refresh_token = data.get('refresh_token')
            
            if access_token and refresh_token:
                # Cache tokens
                cache.set(
                    self._get_cache_key('access_token'), 
                    access_token, 
                    timeout=3600  # 1 hour default
                )
                cache.set(
                    self._get_cache_key('refresh_token'), 
                    refresh_token, 
                    timeout=86400  # 24 hours default
                )
                
                logger.info("Successfully authenticated with KYC Identity service")
                return access_token, refresh_token
            else:
                logger.error("Invalid response from KYC Identity service: missing tokens")
                return None, None
                
        except (requests.exceptions.RequestException, JSONDecodeError) as e:
            logger.error(f"Authentication request failed after retries: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Unexpected error during authentication: {e}")
            raise
    
    def _refresh_token(self, refresh_token: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Refresh the access token using refresh token.
        
        Args:
            refresh_token: The refresh token to use
            
        Returns:
            Tuple of (new_access_token, new_refresh_token) or (None, None) on failure
        """
        if not refresh_token or not self.base_url:
            return None, None
        
        refresh_url = f"{self.base_url.rstrip('/')}/auth/refresh"
        
        def _make_refresh_request():
            payload = {
                'refresh_token': refresh_token
            }
            
            response = requests.post(
                refresh_url,
                json=payload,
                timeout=self.timeout,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'SaeedPay-KYC-Service/1.0'
                }
            )
            
            response.raise_for_status()
            return response
        
        try:
            response = self._retry_with_exponential_backoff(_make_refresh_request)
            data = response.json()
            
            new_access_token = data.get('access_token')
            new_refresh_token = data.get('refresh_token', refresh_token)  # Keep old if not provided
            
            if new_access_token:
                # Cache new tokens
                cache.set(
                    self._get_cache_key('access_token'), 
                    new_access_token, 
                    timeout=3600
                )
                if new_refresh_token != refresh_token:
                    cache.set(
                        self._get_cache_key('refresh_token'), 
                        new_refresh_token, 
                        timeout=86400
                    )
                
                logger.info("Successfully refreshed KYC Identity tokens")
                return new_access_token, new_refresh_token
            else:
                logger.error("Invalid response from token refresh: missing access token")
                return None, None
                
        except (requests.exceptions.RequestException, JSONDecodeError) as e:
            logger.error(f"Token refresh request failed after retries: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {e}")
            raise
    
    def get_valid_tokens(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get valid access and refresh tokens.
        
        This method will:
        1. Check cached tokens first
        2. Try to refresh if access token is invalid
        3. Re-authenticate if refresh fails
        
        Returns:
            Tuple of (access_token, refresh_token) or (None, None) on failure
        """
        # Try to get cached tokens
        access_token = cache.get(self._get_cache_key('access_token'))
        refresh_token = cache.get(self._get_cache_key('refresh_token'))
        
        # Check if access token is valid
        if access_token and self._is_token_valid(access_token, 'access'):
            return access_token, refresh_token
        
        # Try to refresh if we have a refresh token
        if refresh_token and self._is_token_valid(refresh_token, 'refresh'):
            logger.info("Access token expired, attempting refresh")
            new_access_token, new_refresh_token = self._refresh_token(refresh_token)
            if new_access_token:
                return new_access_token, new_refresh_token
        
        # If refresh failed or no refresh token, re-authenticate
        logger.info("Refresh failed or no valid tokens, re-authenticating")
        return self._authenticate()
    
    def verify_identity(self, user_data: Dict) -> Dict:
        """
        Verify user identity using the external service.
        
        Args:
            user_data: Dictionary containing user information to verify
                      (e.g., {'national_id': '1234567890', 'phone': '09123456789'})
        
        Returns:
            Dict containing verification result
        """
        access_token, refresh_token = self.get_valid_tokens()
        
        if not access_token:
            return {
                'success': False,
                'error': 'Authentication failed',
                'error_code': 'AUTH_FAILED'
            }
        
        verify_url = f"{self.base_url.rstrip('/')}/verify/identity"
        
        def _make_verification_request():
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'User-Agent': 'SaeedPay-KYC-Service/1.0'
            }
            
            response = requests.post(
                verify_url,
                json=user_data,
                timeout=self.timeout,
                headers=headers
            )
            
            response.raise_for_status()
            return response
        
        try:
            response = self._retry_with_exponential_backoff(_make_verification_request)
            return response.json()
            
        except (requests.exceptions.RequestException, JSONDecodeError) as e:
            # Enhanced logging with more context
            error_msg = f"Identity verification request failed after retries: {e}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f" | URL: {verify_url} | Status: {e.response.status_code}"
                try:
                    response_content = e.response.text[:500]  # Limit to 500 chars
                    error_msg += f" | Response: {response_content}"
                except:
                    pass
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': f'Verification request failed: {str(e)}',
                'error_code': 'VERIFICATION_FAILED'
            }
        except Exception as e:
            logger.error(f"Unexpected error during identity verification: {e}")
            raise
    
    def clear_tokens(self) -> None:
        """Clear cached tokens (useful for logout or service restart)."""
        cache.delete(self._get_cache_key('access_token'))
        cache.delete(self._get_cache_key('refresh_token'))
        logger.info("KYC Identity tokens cleared from cache")


# Convenience function for easy usage across the project
def get_identity_auth_service() -> IdentityAuthService:
    """
    Get a new instance of the IdentityAuthService.
    
    This function creates a new instance on each call, which is safe for
    multi-process environments like Gunicorn. The service relies on Django's
    cache for shared state between processes.
    
    Returns:
        IdentityAuthService instance
    """
    return IdentityAuthService()
