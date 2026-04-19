# wallets/api/public/v1/schema/payment_requests.py

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema

from wallets.api.public.v1.serializers.payment import (
    PaymentActionResponseSerializer,
    PaymentConfirmSerializer,
    PaymentRequestDetailWithWalletsSerializer,
    PaymentRequestListItemSerializer,
)
from wallets.api.public.v1.serializers.payment_pos import (
    MerchantPosPaymentRequestCreateResponseSerializer,
    MerchantPosPaymentRequestCreateSerializer,
    MerchantPosPaymentRequestDetailSerializer,
    MerchantPosPaymentRequestListItemSerializer,
)

payment_list_schema = extend_schema(
    summary="لیست درخواست‌های پرداخت مشتری",
    description=(
        "لیست درخواست‌های پرداخت متعلق به مشتری لاگین‌شده را برمی‌گرداند. "
        "امکان فیلتر بر اساس وضعیت، فروشگاه، بازه زمانی و جستجو بر اساس reference_code وجود دارد."
    ),
    parameters=[
        OpenApiParameter(name="status", required=False, type=str),
        OpenApiParameter(name="store_id", required=False, type=int),
        OpenApiParameter(name="q", required=False, type=str),
        OpenApiParameter(name="created_from", required=False, type=str),
        OpenApiParameter(name="created_to", required=False, type=str),
        OpenApiParameter(name="expires_from", required=False, type=str),
        OpenApiParameter(name="expires_to", required=False, type=str),
        OpenApiParameter(
            name="ordering",
            required=False,
            type=str,
            description="created_at, -created_at, amount, -amount",
        ),
    ],
    responses={
        200: PaymentRequestListItemSerializer(many=True),
    },
)

payment_retrieve_schema = extend_schema(
    summary="جزییات درخواست پرداخت",
    description=(
        "جزییات یک درخواست پرداخت را بر اساس reference_code برمی‌گرداند. "
        "برای درخواست‌های عمومی QR، کاربر بدون احراز هویت هم می‌تواند جزییات کلی را ببیند، "
        "اما پرداخت فقط برای کاربر مجاز و احراز هویت‌شده ممکن است."
    ),
    responses={
        200: PaymentRequestDetailWithWalletsSerializer,
    },
)

payment_confirm_schema = extend_schema(
    summary="تایید و پرداخت درخواست پرداخت",
    description=(
        "درخواست پرداخت را با کیف پول انتخاب‌شده و OTP کاربر نهایی می‌کند. "
        "در flow آنلاین، نتیجه وارد waiting_for_store_confirmation می‌شود؛ "
        "در QR POS پرداخت مستقیم completed می‌شود."
    ),
    request=PaymentConfirmSerializer,
    responses={
        200: PaymentActionResponseSerializer,
        400: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Validation, business rule, or internal error response.",
        ),
        410: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Expired payment request.",
        ),
    },
)

merchant_pos_payment_create_schema = extend_schema(
    summary="ایجاد درخواست پرداخت حضوری QR توسط فروشنده",
    description=(
        "فروشنده برای فروشگاه خودش یک درخواست پرداخت از نوع QR POS ایجاد می‌کند. "
        "در این flow، customer در زمان ایجاد خالی است و frontend با reference_code، QR تولید می‌کند."
    ),
    request=MerchantPosPaymentRequestCreateSerializer,
    responses={
        201: MerchantPosPaymentRequestCreateResponseSerializer,
        400: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Validation or business rule error.",
        ),
        404: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Store not found or does not belong to merchant.",
        ),
    },
)

merchant_pos_payment_list_schema = extend_schema(
    summary="لیست درخواست‌های پرداخت حضوری QR فروشنده",
    description=(
        "لیست درخواست‌های QR POS متعلق به فروشنده لاگین‌شده را برمی‌گرداند. "
        "امکان فیلتر بر اساس فروشگاه، وضعیت، بازه زمانی و جستجو بر اساس reference_code وجود دارد."
    ),
    parameters=[
        OpenApiParameter(name="store_id", required=False, type=int),
        OpenApiParameter(name="status", required=False, type=str),
        OpenApiParameter(name="q", required=False, type=str),
        OpenApiParameter(name="created_from", required=False, type=str),
        OpenApiParameter(name="created_to", required=False, type=str),
        OpenApiParameter(
            name="ordering",
            required=False,
            type=str,
            description="created_at, -created_at, amount, -amount",
        ),
    ],
    responses={
        200: MerchantPosPaymentRequestListItemSerializer(many=True),
    },
)

merchant_pos_payment_retrieve_schema = extend_schema(
    summary="جزییات درخواست پرداخت حضوری QR فروشنده",
    description=(
        "جزییات یک درخواست QR POS را برای فروشنده همان فروشگاه برمی‌گرداند. "
        "این خروجی فقط داده‌های عملیاتی لازم برای cashier را شامل می‌شود و اطلاعات هویتی مشتری را برنمی‌گرداند."
    ),
    responses={
        200: MerchantPosPaymentRequestDetailSerializer,
        404: OpenApiResponse(description="Payment request not found."),
    },
)

merchant_pos_payment_cancel_schema = extend_schema(
    summary="لغو درخواست پرداخت حضوری QR توسط فروشنده",
    description=(
        "درخواست QR POS را فقط در وضعیت قابل لغو، برای فروشگاه متعلق به همان فروشنده، لغو می‌کند."
    ),
    responses={
        200: PaymentActionResponseSerializer,
        400: OpenApiResponse(
            response=PaymentActionResponseSerializer,
            description="Validation, business rule, or internal error response.",
        ),
        404: OpenApiResponse(description="Payment request not found."),
    },
)
