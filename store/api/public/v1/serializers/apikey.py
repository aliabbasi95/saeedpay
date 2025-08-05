# store/api/public/v1/serializers/apikey.py

from rest_framework import serializers

from store.models import Store


class StoreApiKeyRegenerateRequestSerializer(serializers.Serializer):
    store_id = serializers.IntegerField()

    def validate_store_id(self, value):
        user = self.context["request"].user
        merchant = getattr(user, "merchant", None)

        if not merchant:
            raise serializers.ValidationError("مرچنت یافت نشد.")

        try:
            store = Store.objects.get(id=value)
        except Store.DoesNotExist:
            raise serializers.ValidationError("فروشگاه یافت نشد.")

        if store.merchant != merchant:
            raise serializers.ValidationError("شما مجاز به تغییر کلید این فروشگاه نیستید.")

        return value

class StoreApiKeyRegenerateResponseSerializer(serializers.Serializer):
    api_key = serializers.CharField()
