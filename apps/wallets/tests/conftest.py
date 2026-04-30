# apps/wallets/tests/conftest.py

import pytest
from django.contrib.auth import get_user_model

from apps.customers.models import Customer
from apps.merchants.models import Merchant
from apps.profiles.models import Profile
from apps.store.models import Store
from apps.wallets.models import Wallet
from apps.wallets.utils.choices import OwnerType, WalletKind
from apps.wallets.utils.escrow import ensure_escrow_wallet_exists


@pytest.fixture
def user_factory(db):
    def _make(
        username: str,
        phone: str | None = None,
        *,
        create_customer: bool = False,
    ):
        user_model = get_user_model()
        user = user_model.objects.create(username=username)

        if phone:
            Profile.objects.create(user=user, phone_number=phone)

        if create_customer:
            Customer.objects.create(user=user)

        return user

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
    return user_factory(
        "cust_09120000000",
        phone="09120000000",
        create_customer=True,
    )


@pytest.fixture
def customer(db, customer_user):
    return customer_user.customer


@pytest.fixture
def customer_cash_wallet(db, customer_user):
    return Wallet.objects.create(
        user=customer_user,
        kind=WalletKind.CASH,
        owner_type=OwnerType.CUSTOMER,
        balance=100_000,
    )


@pytest.fixture
def customer_credit_wallet(db, customer_user):
    return Wallet.objects.create(
        user=customer_user,
        kind=WalletKind.CREDIT,
        owner_type=OwnerType.CUSTOMER,
        balance=0,
    )


@pytest.fixture
def merchant_gateway_wallet(db, merchant_user):
    return Wallet.objects.create(
        user=merchant_user,
        kind=WalletKind.MERCHANT_GATEWAY,
        owner_type=OwnerType.MERCHANT,
        balance=0,
    )


@pytest.fixture
def ensure_escrow(db):
    ensure_escrow_wallet_exists()
