# merchants/models/apikey.py

import hashlib
import secrets

from django.db import models
from django.utils import timezone

from store.models import Store


class StoreApiKey(models.Model):
    store = models.OneToOneField(
        Store,
        on_delete=models.CASCADE,
        related_name="api_key",
        verbose_name="فروشگاه"
    )
    key_hash = models.CharField(
        max_length=128,
        unique=True,
        db_index=True,
        verbose_name="هش کلید"
    )
    last_regenerated_at = models.DateTimeField(
        null=True,
        blank=True
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="فعال"
    )

    @classmethod
    def generate_key_and_hash(cls):
        key = secrets.token_urlsafe(48)
        key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return key, key_hash

    def regenerate(self):
        key, key_hash = self.generate_key_and_hash()
        self.key_hash = key_hash
        self.last_regenerated_at = timezone.localtime(timezone.now())
        self.is_active = True
        self.save()
        return key

    def check_key(self, raw_key: str):
        return self.key_hash == hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()
