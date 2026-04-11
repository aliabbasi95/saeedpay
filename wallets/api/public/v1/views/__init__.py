# wallets/api/public/v1/views/__init__.py

from wallets.api.public.v1.views.installment import InstallmentViewSet
from wallets.api.public.v1.views.installment_plan import InstallmentPlanViewSet
from wallets.api.public.v1.views.payment import PaymentRequestViewSet
from wallets.api.public.v1.views.payment_pos import MerchantPosPaymentRequestViewSet
from wallets.api.public.v1.views.transfer import WalletTransferViewSet
from wallets.api.public.v1.views.wallet import WalletViewSet

__all__ = [
    "WalletViewSet",
    "WalletTransferViewSet",
    "PaymentRequestViewSet",
    "MerchantPosPaymentRequestViewSet",
    "InstallmentPlanViewSet",
    "InstallmentViewSet",
]
