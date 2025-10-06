# wallets/tests/conftest.py
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from profiles.models import Profile
from merchants.models import Merchant
from store.models import Store
from wallets.models import Wallet
from wallets.utils.choices import OwnerType, WalletKind
from wallets.utils.escrow import ensure_escrow_wallet_exists


@pytest.fixture
def user_factory(db):
    def _make(username: str, phone: str | None = None):
        User = get_user_model()
        u = User.objects.create(username=username)
        if phone:
            Profile.objects.create(user=u, phone_number=phone)
        return u

    return _make


@pytest.fixture
def merchant_user(db, user_factory):
    return user_factory("merchant_user_1")


@pytest.fixture
def merchant(db, merchant_user):
    return Merchant.objects.create(user=merchant_user)


@pytest.fixture
def store(db, merchant):
    return Store.objects.create(name="store-1", merchant=merchant)


@pytest.fixture
def customer_user(db, user_factory):
    return user_factory("cust_09120000000", phone="09120000000")


@pytest.fixture
def customer_cash_wallet(db, customer_user):
    return Wallet.objects.create(
        user=customer_user, kind=WalletKind.CASH,
        owner_type=OwnerType.CUSTOMER, balance=100_000
    )


@pytest.fixture
def customer_credit_wallet(db, customer_user):
    return Wallet.objects.create(
        user=customer_user, kind=WalletKind.CREDIT,
        owner_type=OwnerType.CUSTOMER, balance=0
    )


@pytest.fixture
def merchant_gateway_wallet(db, merchant_user):
    return Wallet.objects.create(
        user=merchant_user, kind=WalletKind.MERCHANT_GATEWAY,
        owner_type=OwnerType.MERCHANT, balance=0
    )


@pytest.fixture
def ensure_escrow(db):
    ensure_escrow_wallet_exists()
