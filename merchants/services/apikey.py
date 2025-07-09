# merchants/services/apikey.py
from merchants.models import MerchantApiKey

def regenerate_merchant_api_key(merchant):
    try:
        api_key_obj = merchant.api_key
        return api_key_obj.regenerate()
    except MerchantApiKey.DoesNotExist:
        key, key_hash = MerchantApiKey.generate_key_and_hash()
        MerchantApiKey.objects.create(
            merchant=merchant, key_hash=key_hash, is_active=True
        )
        return key
