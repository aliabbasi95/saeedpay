# wallets/services/callback.py

import requests
import logging

logger = logging.getLogger(__name__)


def notify_merchant_user_confirmed(installment_request):
    url = installment_request.contract.callback_url
    if not url:
        return

    payload = {
        "reference_code": installment_request.reference_code,
        "status": "user_confirmed"
    }

    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.warning(f"Callback failed for {url}: {e}")