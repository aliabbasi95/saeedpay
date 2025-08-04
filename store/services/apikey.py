# store/services/apikey.py

from store.models import StoreApiKey

def regenerate_store_api_key(store):
    try:
        api_key_obj = store.api_key
        return api_key_obj.regenerate()
    except StoreApiKey.DoesNotExist:
        key, key_hash = StoreApiKey.generate_key_and_hash()
        StoreApiKey.objects.create(
            store=store, key_hash=key_hash, is_active=True
        )
        return key
