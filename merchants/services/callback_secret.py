# merchants/services/callback_secret.py
from merchants.models import MerchantCallbackSecret

def regenerate_merchant_callback_secret(merchant):
    try:
        callback_secret_obj = merchant.callback_secret
        return callback_secret_obj.regenerate()
    except MerchantCallbackSecret.DoesNotExist:
        secret = MerchantCallbackSecret.generate_secret()
        MerchantCallbackSecret.objects.create(
            secret=secret, is_active=True
        )
        return secret
