import logging
import os
import time
import requests
from typing import Optional, Dict, Any, Callable
from django.conf import settings

logger = logging.getLogger(__name__)

class VideoIdentityVerificationService:
    """
    Service for handling video-based identity verification via external API.
    """
    def __init__(self):
        self.base_url = getattr(settings, 'KYC_IDENTITY_BASE_URL', '')
        self.business_token = os.environ.get('KIAHOOSHAN_BUSINESS_TOKEN', '')
        self.timeout = getattr(settings, 'KYC_IDENTITY_TIMEOUT', 30)
        self.session = requests.Session()
        if not all([self.base_url, self.business_token]):
            logger.warning("Video Identity Verification service configuration incomplete")

    def _retry_with_exponential_backoff(self, func: Callable[[], requests.Response], max_retries: int = 3, base_delay: float = 0.5):
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                return func()
            except requests.exceptions.RequestException as e:
                last_exception = e
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(f"Video verify attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"All {max_retries + 1} attempts failed for video verify. Last error: {e}")
        # If we reach here, raise the last exception to be handled by caller
        raise last_exception

    def verify_idcard_video(
        self,
        national_code: str,
        birth_date: str,
        selfie_video_path: str,
        rand_action: str,
        matching_thr: Optional[int] = None,
        liveness_thr: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send video-based identity verification request.
        Args:
            national_code: National ID number
            birth_date: Date of birth (yyyymmdd)
            selfie_video_path: Path to selfie video file
            rand_action: Random action string
            matching_thr: (optional) facial matching threshold
            liveness_thr: (optional) liveness threshold
        Returns:
            Dict with API response or error info
        """
        url = f"{self.base_url.rstrip('/')}/api/vvs/video/verify-idcard-img"
        headers = {
            'Authorization': f'Bearer {self.business_token}',
            'User-Agent': 'SaeedPay-KYC-Service/1.0'
        }
        data = {
            'nationalCode': national_code,
            'birthDate': birth_date,
            'randAction': rand_action
        }
        if matching_thr is not None:
            data['matchingTHR'] = str(matching_thr)
        if liveness_thr is not None:
            data['livenessTHR'] = str(liveness_thr)
        try:
            with open(selfie_video_path, 'rb') as video_file:
                def _do_request():
                    # Reset file pointer on retries
                    try:
                        video_file.seek(0)
                    except Exception:
                        pass
                    files = {
                        'selfieVideo': (os.path.basename(selfie_video_path), video_file, 'video/mp4')
                    }
                    return self.session.post(
                        url,
                        data=data,
                        files=files,
                        headers=headers,
                        timeout=self.timeout
                    )
                response = self._retry_with_exponential_backoff(_do_request)
            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    return {'success': True, 'data': resp_json}
                except Exception:
                    logger.error('Invalid JSON in success response')
                    return {'success': False, 'error': 'Invalid JSON in success response'}
            elif response.status_code == 400:
                try:
                    err_json = response.json()
                    return {'success': False, 'error': err_json.get('error', {}), 'status': 400}
                except Exception:
                    logger.error('Invalid JSON in error response (400)')
                    return {'success': False, 'error': 'Invalid JSON in error response (400)', 'status': 400}
            else:
                logger.error(f'Unexpected status {response.status_code}: {response.text}')
                return {'success': False, 'error': response.text, 'status': response.status_code}
        except requests.exceptions.RequestException as e:
            logger.error(f'Network error: {e}')
            return {'success': False, 'error': str(e), 'status': 'network'}
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
            return {'success': False, 'error': str(e), 'status': 'exception'}

    def get_verification_result(self, unique_id: str):
        """
        Fetch the result of a video-based identity verification by uniqueId.
        Returns dict with success status, result booleans if available, or error info.
        """
        url = f"{self.base_url.rstrip('/')}/api/vvs/video/verify/result"
        headers = {
            'Authorization': f'Bearer {self.business_token}',
            'User-Agent': 'SaeedPay-KYC-Service/1.0'
        }
        params = {'uniqueId': unique_id}
        try:
            def _do_request():
                return self.session.get(url, headers=headers, params=params, timeout=self.timeout)
            response = self._retry_with_exponential_backoff(_do_request)
            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    content = resp_json.get('content', {})
                    data = content.get('data', {})
                    return {
                        'success': True,
                        'matching': data.get('matching'),
                        'liveness': data.get('liveness'),
                        'spoofing': data.get('spoofing'),
                        'raw': resp_json
                    }
                except Exception:
                    logger.error('Invalid JSON in success response')
                    return {'success': False, 'error': 'Invalid JSON in success response'}
            elif response.status_code == 404:
                try:
                    err_json = response.json()
                    return {'success': False, 'error': err_json.get('result', {}), 'status': 404}
                except Exception:
                    logger.error('Invalid JSON in error response (404)')
                    return {'success': False, 'error': 'Invalid JSON in error response (404)', 'status': 404}
            else:
                logger.error(f'Unexpected status {response.status_code}: {response.text}')
                return {'success': False, 'error': response.text, 'status': response.status_code}
        except requests.exceptions.RequestException as e:
            logger.error(f'Network error: {e}')
            return {'success': False, 'error': str(e), 'status': 'network'}
        except Exception as e:
            logger.error(f'Unexpected error: {e}')
            return {'success': False, 'error': str(e), 'status': 'exception'}
