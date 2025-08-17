# banking/api/public/v1/urls.py

from django.urls import path, include
from rest_framework.routers import SimpleRouter

from .views.bank import BankViewSet
from .views.bank_card import BankCardViewSet

app_name = "banking_public_v1"

router = SimpleRouter()
router.register("banks", BankViewSet, basename="bank")
router.register("cards", BankCardViewSet, basename="card")

urlpatterns = [
    path("", include(router.urls)),
]
