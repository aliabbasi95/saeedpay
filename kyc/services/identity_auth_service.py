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
from .video_identity_verification_service import VideoIdentityVerificationService

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
        self.org_name = os.environ.get('KIAHOOSHAN_ORGNAME', '')
        self.org_national_code = os.environ.get('KIAHOOSHAN_ORGNATIONALCODE', '')
        self.business_token = os.environ.get('KIAHOOSHAN_BUSINESS_TOKEN', '')
        self.timeout = getattr(settings, 'KYC_IDENTITY_TIMEOUT', 30)
        self.token_skew_seconds = getattr(settings, 'KYC_IDENTITY_TOKEN_SKEW_SECONDS', 30)
        self.cache_key_prefix = 'kyc_identity_'
        self.video_verification = VideoIdentityVerificationService()
        # Minimal config check; org fields are optional
        if not all([self.base_url, self.username, self.password]):
            logger.warning("KYC Identity service minimal configuration incomplete (base_url/username/password)")
        if not self.business_token:
            logger.warning("KYC Identity service: business token missing; refresh/video APIs may fail")
    
    def _get_cache_key(self, key_suffix: str) -> str:
        """Generate cache key with prefix."""
        return f"{self.cache_key_prefix}{key_suffix}"
    
    def _cache_token_with_exp(self, key_suffix: str, token: str, default_ttl: int) -> None:
        """
        Cache a token using its JWT exp claim when available, with a small negative skew.
        """
        if not token:
            return
        ttl = default_ttl
        try:
            decoded = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
            exp_ts = decoded.get("exp")
            if exp_ts:
                now_ts = int(time.time())
                ttl = max(int(exp_ts) - now_ts - int(self.token_skew_seconds), 0)
        except Exception:
            # If token is not a JWT or missing exp, fallback to default TTL
            pass
        cache.set(self._get_cache_key(key_suffix), token, timeout=ttl or default_ttl)
    
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
            # Decode without verifying signature or exp; compare ourselves to avoid tz issues
            decoded = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
            exp_timestamp = decoded.get('exp')
            if exp_timestamp:
                now_ts = int(time.time())
                return int(exp_timestamp) > (now_ts + int(self.token_skew_seconds))
            return True  # If no expiration, assume valid
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid {token_type} token: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error during {token_type} token validation: {e}")
            return False
    
    def _handle_token_http_error(self, e, context):
        status = e.response.status_code if e.response else None
        body = e.response.text if e.response else ''
        if status == 400:
            logger.error(f"{context} failed: Invalid input parameters (400). Response: {body}")
        elif status == 403:
            logger.error(f"{context} failed: Forbidden (403). Token expired, invalid, or unauthorized. Response: {body}")
        elif status == 500:
            logger.error(f"{context} failed: Internal server error (500). Response: {body}")
        else:
            logger.error(f"{context} failed: HTTP {status}. Response: {body}")
    
    def _request_token(self, url, payload, headers, context):
        try:
            def _do_request():
                resp = requests.post(url, json=payload, timeout=self.timeout, headers=headers)
                # Ensure HTTP errors become exceptions so retry/handling works
                resp.raise_for_status()
                return resp
            response = self._retry_with_exponential_backoff(_do_request)
            data = response.json()
            # Support both camelCase and snake_case keys from provider/tests
            access_token = data.get('accessToken') or data.get('access_token')
            refresh_token = data.get('refreshToken') or data.get('refresh_token')
            if access_token:
                self._cache_token_with_exp('access_token', access_token, default_ttl=3600)
            if refresh_token:
                self._cache_token_with_exp('refresh_token', refresh_token, default_ttl=86400)
            if access_token or refresh_token:
                logger.info(f"Successfully completed {context} with KYC Identity service")
                return access_token, refresh_token
            logger.error(f"Invalid response from KYC Identity service: missing tokens [{context}]")
            return None, None
        except requests.exceptions.HTTPError as e:
            self._handle_token_http_error(e, context)
            return None, None
        except (requests.exceptions.RequestException, JSONDecodeError) as e:
            logger.error(f"{context} request failed after retries: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Unexpected error during {context}: {e}")
            # Fail gracefully to align with calling code/tests
            return None, None

    def _authenticate(self) -> Tuple[Optional[str], Optional[str]]:
        # Full configuration is required including org fields
        if not all([self.base_url, self.username, self.password, self.org_name, self.org_national_code]):
            logger.error("KYC Identity service not properly configured")
            return None, None
        auth_url = f"{self.base_url.rstrip('/')}/api/ums/token"
        payload = {
            'username': self.username,
            'password': self.password,
            'orgName': self.org_name,
            'orgNationalCode': self.org_national_code
        }
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'SaeedPay-KYC-Service/1.0'
        }
        return self._request_token(auth_url, payload, headers, "Token request")

    def _refresh_token(self, refresh_token: str) -> Tuple[Optional[str], Optional[str]]:
        if not refresh_token or not self.base_url:
            return None, None
        refresh_url = f"{self.base_url.rstrip('/')}/api/ums/token/refresh"
        payload = {'refreshToken': refresh_token}
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'SaeedPay-KYC-Service/1.0',
            'Authorization': f'Bearer {self.business_token}'
        }
        return self._request_token(refresh_url, payload, headers, "Token refresh")
    
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
            # Prevent thundering herd: simple cache-based lock
            lock_key = self._get_cache_key('refresh_lock')
            got_lock = cache.add(lock_key, str(time.time()), timeout=10)
            if got_lock:
                try:
                    logger.info("Access token expired, attempting refresh")
                    new_access_token, new_refresh_token = self._refresh_token(refresh_token)
                    if new_access_token:
                        return new_access_token, new_refresh_token
                finally:
                    cache.delete(lock_key)
            else:
                # Another worker is refreshing; wait briefly and reuse new tokens
                for _ in range(3):
                    time.sleep(0.25)
                    access_token = cache.get(self._get_cache_key('access_token'))
                    if access_token and self._is_token_valid(access_token, 'access'):
                        return access_token, cache.get(self._get_cache_key('refresh_token'))
        
        # If refresh failed or no refresh token, re-authenticate
        # As a last resort, re-authenticate with a similar lock
        auth_lock_key = self._get_cache_key('auth_lock')
        got_auth_lock = cache.add(auth_lock_key, str(time.time()), timeout=10)
        if got_auth_lock:
            try:
                logger.info("Refresh failed or no valid tokens, re-authenticating")
                return self._authenticate()
            finally:
                cache.delete(auth_lock_key)
        else:
            for _ in range(3):
                time.sleep(0.25)
                access_token = cache.get(self._get_cache_key('access_token'))
                if access_token and self._is_token_valid(access_token, 'access'):
                    return access_token, cache.get(self._get_cache_key('refresh_token'))
        # If still nothing, return failure
        return None, None
    
    def verify_identity(self, user_data: Dict) -> Dict:
        """
        Verify user identity using the external service.
        
        Args:
            user_data: Dictionary containing user information to verify
                      (e.g., {'national_id': '1234567890', 'phone': '09123456789'})
        
        Returns:
            Dict containing verification result, always with a 'success' key
        """
        access_token, refresh_token = self.get_valid_tokens()
        
        if not access_token:
            return {
                'success': False,
                'error': 'Authentication failed',
                'error_code': 'AUTH_FAILED'
            }
        
        verify_url = f"{self.base_url.rstrip('/')}/verify/identity"
        
        def _make_verification_request(token):
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'User-Agent': 'SaeedPay-KYC-Service/1.0'
            }
            return requests.post(
                verify_url,
                json=user_data,
                timeout=self.timeout,
                headers=headers
            )
        
        try:
            # First attempt with current access token
            response = self._retry_with_exponential_backoff(lambda: _make_verification_request(access_token))
            
            # If unauthorized, try to refresh once and retry
            if response.status_code == 401 and refresh_token and self._is_token_valid(refresh_token, 'refresh'):
                logger.info("Access token unauthorized (401). Attempting token refresh and retrying verification.")
                new_access_token, new_refresh_token = self._refresh_token(refresh_token)
                if new_access_token:
                    response = self._retry_with_exponential_backoff(lambda: _make_verification_request(new_access_token))
            
            if 200 <= response.status_code < 300:
                try:
                    resp_json = response.json()
                except JSONDecodeError:
                    logger.error("Invalid JSON in verification success response")
                    return {
                        'success': False,
                        'error': 'Invalid JSON in success response',
                        'error_code': 'INVALID_JSON'
                    }
                return {'success': True, 'data': resp_json}
            else:
                # Non-2xx status
                error_body = ''
                try:
                    error_body = response.text[:500]
                except Exception:
                    pass
                logger.error(f"Verification failed: HTTP {response.status_code} | URL: {verify_url} | Response: {error_body}")
                return {
                    'success': False,
                    'error': error_body or 'Verification failed',
                    'error_code': 'VERIFICATION_FAILED',
                    'status': response.status_code
                }
        except (requests.exceptions.RequestException, JSONDecodeError) as e:
            # Enhanced logging with more context
            error_msg = f"Identity verification request failed after retries: {e}"
            if hasattr(e, 'response') and e.response is not None:
                error_msg += f" | URL: {verify_url} | Status: {e.response.status_code}"
                try:
                    response_content = e.response.text[:500]  # Limit to 500 chars
                    error_msg += f" | Response: {response_content}"
                except Exception:
                    pass
            logger.error(error_msg)
            
            return {
                'success': False,
                'error': f'Verification request failed: {str(e)}',
                'error_code': 'VERIFICATION_FAILED'
            }
        except Exception as e:
            logger.error(f"Unexpected error during identity verification: {e}")
            return {
                'success': False,
                'error': 'Unexpected error during identity verification',
                'error_code': 'UNEXPECTED_ERROR'
            }
    
    def verify_idcard_video(self, national_code, birth_date, selfie_video_path, rand_action, matching_thr=None, liveness_thr=None):
        """
        Proxy for video-based identity verification.
        """
        return self.video_verification.verify_idcard_video(
            national_code=national_code,
            birth_date=birth_date,
            selfie_video_path=selfie_video_path,
            rand_action=rand_action,
            matching_thr=matching_thr,
            liveness_thr=liveness_thr
        )
    
    def get_video_verification_result(self, unique_id):
        """
        Proxy for fetching video verification result by unique_id.
        """
        return self.video_verification.get_verification_result(unique_id)
    
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
