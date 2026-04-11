# wallets/api/public/v1/views/payment.py

from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from wallets.api.payment_responses import (
    payment_error_response,
    payment_success_response,
)
from wallets.api.public.v1.schema import (
    payment_confirm_schema,
    payment_list_schema,
    payment_retrieve_schema,
)
from wallets.api.public.v1.serializers.payment import (
    PaymentActionResponseSerializer,
    PaymentConfirmSerializer,
    PaymentRequestDetailWithWalletsSerializer,
    PaymentRequestListItemSerializer,
)
from wallets.models import PaymentRequest, Wallet
from wallets.services.payment import (
    check_and_expire_payment_request,
    pay_payment_request,
)
from wallets.services.payment.payment_request_service import (
    validate_payment_request_payer_access,
)
from wallets.utils.choices import OwnerType

_ALLOWED_ORDERING = {"created_at", "-created_at", "amount", "-amount"}


def _parse_dt_maybe(value):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt:
        return dt
    return parse_date(value)


def _extract_validation_code(exc, default="validation_error"):
    if hasattr(exc, "get_codes"):
        codes = exc.get_codes()
        if isinstance(codes, list) and codes:
            return codes[0]
        if isinstance(codes, str):
            return codes
        if isinstance(codes, dict):
            first_value = next(iter(codes.values()), default)
            if isinstance(first_value, list) and first_value:
                return first_value[0]
            if isinstance(first_value, str):
                return first_value
    return getattr(exc, "code", default)


class PaymentRequestViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [AllowAny]
    lookup_field = "reference_code"
    lookup_value_regex = r"[-A-Za-z0-9_]+"
    throttle_scope_map = {
        "default": "user",
        "confirm": "payment-confirm",
        "retrieve": "user",
        "list": "user",
    }

    def _require_authenticated_user(self, request):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated("احراز هویت الزامی است.")

    def get_queryset(self):
        if self.action in {"retrieve", "confirm"}:
            return (
                PaymentRequest.objects.select_related("store")
                .only(
                    "reference_code",
                    "amount",
                    "description",
                    "status",
                    "flow_type",
                    "expires_at",
                    "created_at",
                    "store_id",
                    "store__id",
                    "store__name",
                    "customer_id",
                    "return_url",
                    "paid_at",
                )
            )

        user = self.request.user
        customer = getattr(user, "customer", None)
        if not customer:
            return PaymentRequest.objects.none()

        params = self.request.query_params
        qs = (
            PaymentRequest.objects.select_related("store")
            .only(
                "reference_code",
                "amount",
                "description",
                "status",
                "flow_type",
                "expires_at",
                "created_at",
                "store_id",
                "store__id",
                "store__name",
                "customer_id",
                "return_url",
                "paid_at",
            )
            .filter(customer=customer)
        )

        status_param = params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        store_id = params.get("store_id")
        if store_id:
            qs = qs.filter(store_id=store_id)

        q = params.get("q")
        if q:
            qs = qs.filter(reference_code__icontains=q)

        created_from = _parse_dt_maybe(params.get("created_from"))
        if created_from:
            qs = qs.filter(created_at__gte=created_from)

        created_to = _parse_dt_maybe(params.get("created_to"))
        if created_to:
            qs = qs.filter(created_at__lte=created_to)

        expires_from = _parse_dt_maybe(params.get("expires_from"))
        if expires_from:
            qs = qs.filter(expires_at__gte=expires_from)

        expires_to = _parse_dt_maybe(params.get("expires_to"))
        if expires_to:
            qs = qs.filter(expires_at__lte=expires_to)

        ordering = params.get("ordering") or "-created_at"
        if ordering not in _ALLOWED_ORDERING:
            ordering = "-created_at"
        return qs.order_by(ordering)

    @payment_list_schema
    def list(self, request, *args, **kwargs):
        self._require_authenticated_user(request)
        self.serializer_class = PaymentRequestListItemSerializer
        return super().list(request, *args, **kwargs)

    @payment_retrieve_schema
    def retrieve(self, request, *args, **kwargs):
        self.serializer_class = PaymentRequestDetailWithWalletsSerializer
        payment_request = self.get_object()
        check_and_expire_payment_request(payment_request, raise_exception=False)
        payment_request.refresh_from_db()

        serializer = self.get_serializer(
            payment_request,
            context={"request": request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @payment_confirm_schema
    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, *args, **kwargs):
        self._require_authenticated_user(request)
        payment_request = self.get_object()

        try:
            check_and_expire_payment_request(payment_request)
            payment_request.refresh_from_db()
            validate_payment_request_payer_access(
                payment_request=payment_request,
                user=request.user,
            )
        except ValidationError as exc:
            code = _extract_validation_code(exc)
            http_status = (
                status.HTTP_410_GONE
                if code == "expired"
                else status.HTTP_400_BAD_REQUEST
            )
            return payment_error_response(
                detail=str(exc),
                code=code,
                http_status=http_status,
                payment_request=payment_request,
            )
        except Exception as exc:
            return payment_error_response(
                detail=str(exc),
                code="unknown_error",
                http_status=status.HTTP_400_BAD_REQUEST,
                payment_request=payment_request,
            )

        serializer = PaymentConfirmSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        wallet_id = serializer.validated_data["wallet_id"]
        try:
            wallet = Wallet.objects.get(
                id=wallet_id,
                user=request.user,
                owner_type=OwnerType.CUSTOMER,
            )
        except Wallet.DoesNotExist:
            return payment_error_response(
                detail="کیف پول پیدا نشد یا متعلق به شما نیست.",
                code="wallet_not_owned",
                http_status=status.HTTP_400_BAD_REQUEST,
                payment_request=payment_request,
            )

        try:
            payment = pay_payment_request(payment_request, request.user, wallet)
            payment_request.refresh_from_db()
            payment.refresh_from_db()
        except ValidationError as exc:
            return payment_error_response(
                detail=str(exc),
                code=_extract_validation_code(exc),
                http_status=status.HTTP_400_BAD_REQUEST,
                payment_request=payment_request,
            )
        except Exception as exc:
            return payment_error_response(
                detail=str(exc),
                code="business_rule",
                http_status=status.HTTP_400_BAD_REQUEST,
                payment_request=payment_request,
            )

        payload_response = payment_success_response(
            detail="پرداخت با موفقیت انجام شد.",
            code="payment_confirmed",
            payment_request=payment_request,
            payment=payment,
            http_status=status.HTTP_200_OK,
        )

        serializer = PaymentActionResponseSerializer(payload_response.data)
        return Response(serializer.data, status=payload_response.status_code)


# wallets/services/payment/payment_processing_service.py

from django.db import transaction
from rest_framework.exceptions import ValidationError

from credit.models.authorization import CreditAuthorization
from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.utils.choices import StatementLineType
from wallets.models import Payment, PaymentRequest, Transaction, Wallet
from wallets.services.payment.payment_request_service import (
    check_and_expire_payment_request,
    ensure_no_active_payment_exists,
    ensure_request_can_be_paid,
    resolve_payment_method,
    validate_payment_request_payer_access,
    validate_wallet_ownership,
)
from wallets.services.payment.payment_shared import (
    build_authorized_event_extra,
    create_event,
    credit_auth_hold_expiry,
    ensure_payment_request_status,
    get_latest_payment_for_request,
    get_escrow_wallet,
    get_merchant_gateway_wallet,
    logger,
    merchant_confirm_expiry,
)
from wallets.utils.choices import (
    PaymentEventType,
    PaymentFlowType,
    PaymentMethod,
    PaymentRequestStatus,
    PaymentStatus,
    TransactionPurpose,
)


def pay_payment_request(request_obj: PaymentRequest, user, wallet: Wallet):
    with transaction.atomic():
        payment_request = (
            PaymentRequest.objects.select_for_update()
            .select_related("store__merchant__user", "customer__user")
            .get(pk=request_obj.pk)
        )

        check_and_expire_payment_request(payment_request)
        ensure_request_can_be_paid(payment_request)
        validate_payment_request_payer_access(
            payment_request=payment_request,
            user=user,
        )

        customer_wallet = validate_wallet_ownership(user=user, wallet=wallet)
        ensure_no_active_payment_exists(payment_request)
        payment_method = resolve_payment_method(customer_wallet)

        payment = Payment.objects.create(
            payment_request=payment_request,
            payer=user,
            payer_wallet=customer_wallet,
            amount=payment_request.amount,
            method=payment_method,
            flow_type=payment_request.flow_type,
            status=PaymentStatus.CREATED,
        )

        if payment.method == PaymentMethod.CASH:
            _authorize_cash_payment(payment, customer_wallet)

            if payment.flow_type == PaymentFlowType.QR_POS:
                _settle_cash_payment(payment)
                payment.mark_completed()
                payment_request.mark_completed_direct(
                    user=user,
                    wallet=customer_wallet,
                )
                _log_request_completed_event(
                    payment_request=payment_request,
                    user=user,
                    wallet=customer_wallet,
                    payment=payment,
                    from_status=PaymentRequestStatus.CREATED,
                )
            else:
                _mark_payment_awaiting_merchant(payment)
                _move_request_to_awaiting_merchant(
                    payment_request=payment_request,
                    user=user,
                    wallet=customer_wallet,
                    merchant_deadline=payment.merchant_confirm_expires_at,
                    payment=payment,
                )

        elif payment.method == PaymentMethod.CREDIT:
            _authorize_credit_payment(payment)

            if payment.flow_type == PaymentFlowType.QR_POS:
                _settle_credit_payment(payment)
                payment.mark_completed()
                payment_request.mark_completed_direct(
                    user=user,
                    wallet=customer_wallet,
                )
                _log_request_completed_event(
                    payment_request=payment_request,
                    user=user,
                    wallet=customer_wallet,
                    payment=payment,
                    from_status=PaymentRequestStatus.CREATED,
                )
            else:
                _mark_payment_awaiting_merchant(payment)
                _move_request_to_awaiting_merchant(
                    payment_request=payment_request,
                    user=user,
                    wallet=customer_wallet,
                    merchant_deadline=payment.merchant_confirm_expires_at,
                    payment=payment,
                )

        return payment


def verify_payment_request(payment_request: PaymentRequest, *, store=None) -> Payment:
    with transaction.atomic():
        request_obj = (
            PaymentRequest.objects.select_for_update()
            .select_related("store__merchant__user")
            .get(pk=payment_request.pk)
        )

        if store is not None and request_obj.store_id != store.id:
            raise ValidationError(
                "این درخواست پرداخت متعلق به این فروشگاه نیست.",
                code="forbidden_store",
            )

        check_and_expire_payment_request(request_obj)
        latest_payment = get_latest_payment_for_request(request_obj)

        if request_obj.status == PaymentRequestStatus.COMPLETED:
            raise ValidationError(
                "این درخواست پرداخت قبلاً نهایی شده است.",
                code="already_completed",
            )

        if request_obj.status == PaymentRequestStatus.CANCELLED:
            raise ValidationError(
                "درخواست پرداخت لغو شده است.",
                code="cancelled",
            )

        if request_obj.status == PaymentRequestStatus.EXPIRED:
            raise ValidationError(
                "درخواست پرداخت منقضی شده است.",
                code="expired",
            )

        ensure_payment_request_status(
            request_obj,
            allowed_statuses={PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION},
            error_message="پرداخت قابل نهایی‌سازی نیست یا قبلاً تایید شده است.",
            error_code="invalid_state",
        )

        payment = (
            Payment.objects.select_for_update()
            .filter(
                payment_request=request_obj,
                status=PaymentStatus.AWAITING_MERCHANT_CONFIRMATION,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        if not payment:
            raise ValidationError(
                "پرداخت مرتبط برای نهایی‌سازی پیدا نشد.",
                code="missing_payment",
            )

        actor = None
        if store and getattr(store, "merchant", None):
            actor = getattr(store.merchant, "user", None)

        create_event(
            payment_request=request_obj,
            payment=latest_payment,
            actor=actor,
            event_type=PaymentEventType.PAYMENT_VERIFY_REQUESTED,
            from_status=request_obj.status,
            to_status=request_obj.status,
            description="Merchant requested payment verification.",
            extra_data={
                "store_id": store.id if store else None,
            },
        )

        if payment.method == PaymentMethod.CASH:
            _settle_cash_payment(payment)
        elif payment.method == PaymentMethod.CREDIT:
            _settle_credit_payment(payment)
        else:
            raise ValidationError(
                "روش پرداخت پشتیبانی نمی‌شود.",
                code="unsupported_payment_method",
            )

        from_status = request_obj.status
        payment.mark_completed()
        request_obj.mark_completed(
            user=request_obj.paid_by,
            wallet=request_obj.paid_wallet,
        )
        _log_request_completed_event(
            payment_request=request_obj,
            user=request_obj.paid_by,
            wallet=request_obj.paid_wallet,
            payment=payment,
            from_status=from_status,
        )
        return payment


def rollback_payment(payment_request: PaymentRequest):
    with transaction.atomic():
        request_obj = PaymentRequest.objects.select_for_update().get(
            pk=payment_request.pk
        )

        payment = (
            Payment.objects.select_for_update()
            .filter(payment_request=request_obj)
            .order_by("-created_at", "-id")
            .first()
        )
        if not payment:
            return None

        if payment.status == PaymentStatus.COMPLETED:
            return None

        if payment.method == PaymentMethod.CASH:
            return _rollback_cash_payment(payment)

        if payment.method == PaymentMethod.CREDIT:
            return _rollback_credit_payment(payment)

        return None


def _authorize_cash_payment(payment: Payment, customer_wallet: Wallet):
    escrow_wallet = get_escrow_wallet()

    if customer_wallet.available_balance < payment.amount:
        raise ValidationError(
            "موجودی کافی نیست.",
            code="insufficient_funds",
        )

    customer_wallet.balance -= payment.amount
    escrow_wallet.balance += payment.amount
    customer_wallet.save(update_fields=["balance"])
    escrow_wallet.save(update_fields=["balance"])

    escrow_transaction = Transaction.create_success(
        payment=payment,
        payment_request=payment.payment_request,
        from_wallet=customer_wallet,
        to_wallet=escrow_wallet,
        amount=payment.amount,
        purpose=TransactionPurpose.ESCROW_DEBIT,
        description="Customer → Escrow",
    )

    payment.mark_authorized()

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        transaction=escrow_transaction,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_AUTHORIZED,
        to_status=payment.status,
        description="Cash payment authorized.",
        extra_data=build_authorized_event_extra(
            payment=payment,
            wallet_id=customer_wallet.id,
        ),
    )


def _authorize_credit_payment(payment: Payment):
    from credit.models.credit_limit import CreditLimit

    credit_limit = CreditLimit.objects.get_user_credit_limit(payment.payer)
    if not credit_limit or not credit_limit.is_active:
        raise ValidationError(
            "اعتبار فعال یافت نشد یا منقضی شده است.",
            code="credit_unavailable",
        )
    if int(credit_limit.available_limit) < int(payment.amount):
        raise ValidationError(
            "اعتبار کافی نیست.",
            code="insufficient_credit",
        )

    authorization_expires_at = credit_auth_hold_expiry()

    authorization = CreditAuthorization.objects.create(
        user=payment.payer,
        payment=payment,
        payment_request=payment.payment_request,
        amount=int(payment.amount),
        status=CreditAuthorization.Status.ACTIVE,
        expires_at=authorization_expires_at,
    )

    payment.authorization_expires_at = authorization_expires_at
    payment.mark_authorized()

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_AUTHORIZED,
        to_status=payment.status,
        description="Credit payment authorized.",
        extra_data=build_authorized_event_extra(
            payment=payment,
            wallet_id=payment.payer_wallet_id,
            extra={"credit_authorization_id": authorization.id},
        ),
    )


def _mark_payment_awaiting_merchant(payment: Payment):
    payment.merchant_confirm_expires_at = merchant_confirm_expiry()
    payment.mark_awaiting_merchant()


def _move_request_to_awaiting_merchant(
        *,
        payment_request: PaymentRequest,
        user,
        wallet,
        merchant_deadline,
        payment: Payment,
):
    from_status = payment_request.status

    payment_request.mark_awaiting_merchant(
        user=user,
        wallet=wallet,
        merchant_deadline=merchant_deadline,
    )

    create_event(
        payment_request=payment_request,
        payment=payment,
        actor=user,
        event_type=PaymentEventType.AWAITING_MERCHANT,
        from_status=from_status,
        to_status=payment_request.status,
        description="Payment request is waiting for merchant confirmation.",
        extra_data={
            "merchant_confirm_expires_at": (
                merchant_deadline.isoformat() if merchant_deadline else None
            ),
            "wallet_id": wallet.id if wallet else None,
        },
    )


def _log_request_completed_event(
        *,
        payment_request: PaymentRequest,
        user,
        wallet,
        payment: Payment,
        from_status,
):
    create_event(
        payment_request=payment_request,
        payment=payment,
        actor=user,
        event_type=PaymentEventType.PAYMENT_COMPLETED,
        from_status=from_status,
        to_status=payment_request.status,
        description="Payment request completed.",
        extra_data={
            "wallet_id": wallet.id if wallet else None,
        },
    )


def _settle_cash_payment(payment):
    customer_to_escrow_txn = Transaction.latest_success_for_payment(
        payment,
        TransactionPurpose.ESCROW_DEBIT,
    )
    if not customer_to_escrow_txn:
        raise ValidationError(
            "تراکنش انتقال به امانی برای این پرداخت پیدا نشد.",
            code="missing_escrow_transaction",
        )

    escrow_wallet = Wallet.objects.select_for_update().get(
        pk=customer_to_escrow_txn.to_wallet_id
    )
    merchant_wallet = get_merchant_gateway_wallet(payment)

    if escrow_wallet.balance < payment.amount:
        logger.error(
            "ESCROW low balance verify: need %s, have %s",
            payment.amount,
            escrow_wallet.balance,
        )
        raise ValidationError(
            "عملیات با خطا مواجه شد. لطفاً بعداً تلاش کنید.",
            code="escrow_insufficient",
        )

    escrow_wallet.balance -= payment.amount
    merchant_wallet.balance += payment.amount
    escrow_wallet.save(update_fields=["balance"])
    merchant_wallet.save(update_fields=["balance"])

    settlement_txn = Transaction.create_success(
        payment=payment,
        payment_request=payment.payment_request,
        from_wallet=escrow_wallet,
        to_wallet=merchant_wallet,
        amount=payment.amount,
        purpose=TransactionPurpose.SETTLEMENT,
        description="Escrow → Merchant",
        related_transaction=customer_to_escrow_txn,
    )

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        transaction=settlement_txn,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_SETTLED,
        description="Cash payment settled from escrow to merchant.",
        extra_data={
            "transaction_id": settlement_txn.id,
            "amount": payment.amount,
        },
    )
    return settlement_txn


def _settle_credit_payment(payment: Payment):
    auth = (
        CreditAuthorization.objects.select_for_update()
        .filter(
            payment=payment,
            payment_request=payment.payment_request,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if not auth:
        raise ValidationError(
            "Authorization not found.",
            code="missing_authorization",
        )

    if auth.status == CreditAuthorization.Status.SETTLED:
        return auth

    if auth.status != CreditAuthorization.Status.ACTIVE:
        raise ValidationError(
            "Authorization is not active.",
            code="invalid_authorization_state",
        )

    auth.status = CreditAuthorization.Status.SETTLED
    auth.save(update_fields=["status"])

    statement, _ = Statement.objects.get_or_create_current_statement(
        payment.payer
    )
    existing_line = StatementLine.all_objects.filter(
        payment=payment,
        type=StatementLineType.PURCHASE,
    ).first()
    if existing_line:
        return auth

    StatementLine.objects.create(
        statement=statement,
        type=StatementLineType.PURCHASE,
        amount=payment.amount,
        payment=payment,
        payment_request=payment.payment_request,
        description=f"Purchase {payment.payment_request.reference_code}",
    )

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_SETTLED,
        description="Credit payment settled.",
        extra_data={
            "credit_authorization_id": auth.id,
            "amount": payment.amount,
        },
    )
    return auth


def _rollback_cash_payment(payment: Payment):
    if Transaction.success_exists_for_payment(payment, TransactionPurpose.REVERSAL):
        return Transaction.latest_success_for_payment(
            payment,
            TransactionPurpose.REVERSAL,
        )

    if Transaction.success_exists_for_payment(payment, TransactionPurpose.SETTLEMENT):
        return None

    debit_transaction = Transaction.latest_success_for_payment(
        payment,
        TransactionPurpose.ESCROW_DEBIT,
    )
    if not debit_transaction:
        return None

    escrow_wallet = Wallet.objects.select_for_update().get(
        pk=debit_transaction.to_wallet_id
    )
    customer_wallet = Wallet.objects.select_for_update().get(
        pk=debit_transaction.from_wallet_id
    )

    if escrow_wallet.balance < debit_transaction.amount:
        logger.error(
            "ESCROW low balance rollback: need %s, have %s",
            debit_transaction.amount,
            escrow_wallet.balance,
        )
        raise ValidationError(
            "عملیات بازگشت وجه با خطا مواجه شد.",
            code="escrow_insufficient",
        )

    escrow_wallet.balance -= debit_transaction.amount
    customer_wallet.balance += debit_transaction.amount
    escrow_wallet.save(update_fields=["balance"])
    customer_wallet.save(update_fields=["balance"])

    reversal = Transaction.create_success(
        payment=payment,
        payment_request=payment.payment_request,
        related_transaction=debit_transaction,
        from_wallet=escrow_wallet,
        to_wallet=customer_wallet,
        amount=debit_transaction.amount,
        purpose=TransactionPurpose.REVERSAL,
        description="Escrow → Customer (reversal)",
    )

    if payment.payment_request.status == PaymentRequestStatus.CANCELLED:
        payment.mark_cancelled()
    elif payment.payment_request.status == PaymentRequestStatus.EXPIRED:
        payment.mark_expired()

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        transaction=reversal,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_ROLLBACK,
        to_status=payment.status,
        description="Cash payment rolled back.",
        extra_data={
            "transaction_id": reversal.id,
            "amount": reversal.amount,
        },
    )
    return reversal


def _rollback_credit_payment(payment: Payment):
    auth = (
        CreditAuthorization.objects.select_for_update()
        .filter(
            payment=payment,
            payment_request=payment.payment_request,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if not auth:
        return None

    if auth.status == CreditAuthorization.Status.ACTIVE:
        auth.status = CreditAuthorization.Status.RELEASED
        auth.save(update_fields=["status"])

    if payment.payment_request.status == PaymentRequestStatus.CANCELLED:
        payment.mark_cancelled()
    elif payment.payment_request.status == PaymentRequestStatus.EXPIRED:
        payment.mark_expired()

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_ROLLBACK,
        to_status=payment.status,
        description="Credit authorization released / rolled back.",
        extra_data={
            "credit_authorization_id": auth.id,
            "amount": payment.amount,
        },
    )
    return auth


# wallets/api/public/v1/serializers/payment.py

import re

from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from auth_api.models import PhoneOTP
from wallets.api.public.v1.serializers.wallet import WalletSerializer
from wallets.models import PaymentRequest
from wallets.services.payment import list_eligible_wallets_for_payment_request
from wallets.utils.choices import PaymentFlowType, PaymentRequestStatus


class PaymentRequestDetailSerializer(serializers.ModelSerializer):
    store_name = serializers.CharField(source="store.name", read_only=True)
    store_id = serializers.IntegerField(source="store.id", read_only=True)
    status = serializers.CharField(read_only=True)
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    flow_type = serializers.CharField(read_only=True)
    flow_type_display = serializers.CharField(
        source="get_flow_type_display",
        read_only=True,
    )
    merchant_confirmation_required = serializers.SerializerMethodField()

    class Meta:
        model = PaymentRequest
        fields = [
            "reference_code",
            "amount",
            "description",
            "store_id",
            "store_name",
            "status",
            "status_display",
            "flow_type",
            "flow_type_display",
            "merchant_confirmation_required",
            "expires_at",
            "paid_at",
        ]
        read_only_fields = fields

    def get_merchant_confirmation_required(self, obj: PaymentRequest) -> bool:
        return obj.flow_type == PaymentFlowType.ONLINE


class PaymentConfirmSerializer(serializers.Serializer):
    wallet_id = serializers.IntegerField(min_value=1)
    code = serializers.CharField(min_length=4, max_length=10)

    def validate(self, data):
        user = self.context["request"].user
        phone_number = getattr(
            getattr(user, "profile", None),
            "phone_number",
            None,
        )

        if not phone_number or not re.match(r"^09\d{9}$", phone_number):
            raise serializers.ValidationError(
                {"phone_number": ["شماره تلفن معتبر نیست."]}
            )

        try:
            otp_instance = PhoneOTP.objects.get(phone_number=phone_number)
        except PhoneOTP.DoesNotExist:
            raise serializers.ValidationError(
                {"code": "کد تایید یافت نشد یا منقضی شده است."}
            )

        if not otp_instance.verify(data.get("code")):
            raise serializers.ValidationError(
                {"code": "کد تایید اشتباه یا منقضی شده است."}
            )

        return data


class PaymentActionResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()
    payment_reference_code = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    payment_request_status = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    payment_status = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    transaction_reference_code = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    next_action = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    merchant_confirmation_required = serializers.BooleanField(
        required=False,
        allow_null=True,
    )
    return_url = serializers.URLField(
        required=False,
        allow_null=True,
    )
    amount = serializers.IntegerField(
        required=False,
        allow_null=True,
    )


class PaymentConfirmResponseSerializer(PaymentActionResponseSerializer):
    """
    Backward-compatible alias for older imports/schemas.
    """
    pass


class PaymentRequestDetailWithWalletsSerializer(PaymentRequestDetailSerializer):
    available_wallets = serializers.SerializerMethodField()
    can_pay = serializers.SerializerMethodField()
    reason = serializers.SerializerMethodField()

    def _get_request_user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def _is_authenticated(self, user):
        return bool(user and user.is_authenticated)

    def _is_payer_allowed(self, obj: PaymentRequest, user) -> bool:
        if not self._is_authenticated(user):
            return False

        if not obj.customer_id:
            return True

        user_customer = getattr(user, "customer", None)
        return bool(user_customer and user_customer.id == obj.customer_id)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_available_wallets(self, obj: PaymentRequest):
        user = self._get_request_user()
        if not self._is_payer_allowed(obj, user):
            return []

        qs = list_eligible_wallets_for_payment_request(user, obj)
        return WalletSerializer(qs, many=True).data

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_can_pay(self, obj: PaymentRequest) -> bool:
        user = self._get_request_user()

        if obj.status != PaymentRequestStatus.CREATED:
            return False

        if obj.expires_at and obj.expires_at < timezone.localtime(timezone.now()):
            return False

        if not self._is_authenticated(user):
            return False

        return self._is_payer_allowed(obj, user)

    @extend_schema_field(OpenApiTypes.STR)
    def get_reason(self, obj: PaymentRequest):
        user = self._get_request_user()

        if obj.status == PaymentRequestStatus.EXPIRED:
            return "expired"

        if obj.status != PaymentRequestStatus.CREATED:
            return "not_payable"

        if obj.expires_at and obj.expires_at < timezone.localtime(timezone.now()):
            return "expired"

        if not self._is_authenticated(user):
            return "authentication_required"

        if obj.customer_id:
            user_customer = getattr(user, "customer", None)
            if not user_customer or user_customer.id != obj.customer_id:
                return "not_allowed"

        return None

    class Meta(PaymentRequestDetailSerializer.Meta):
        fields = PaymentRequestDetailSerializer.Meta.fields + [
            "available_wallets",
            "can_pay",
            "reason",
        ]
        read_only_fields = fields


class PaymentRequestListItemSerializer(PaymentRequestDetailSerializer):
    created_at = serializers.DateTimeField(read_only=True)

    class Meta(PaymentRequestDetailSerializer.Meta):
        fields = PaymentRequestDetailSerializer.Meta.fields + ["created_at"]
        read_only_fields = fields


# wallets/api/partner/v1/serializers/payment.py

from rest_framework import serializers

from wallets.models import PaymentRequest
from wallets.utils.choices import PaymentFlowType
from wallets.utils.validators import https_only_validator


class PaymentRequestCreateSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1)
    return_url = serializers.URLField(
        required=True,
        validators=[https_only_validator],
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
    )
    external_guid = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=64,
    )
    national_id = serializers.CharField(max_length=10)
    flow_type = serializers.ChoiceField(
        choices=PaymentFlowType.choices,
        required=False,
        default=PaymentFlowType.ONLINE,
    )

    def validate_flow_type(self, value):
        if value != PaymentFlowType.ONLINE:
            raise serializers.ValidationError(
                "ایجاد درخواست QR POS از این API مجاز نیست."
            )
        return value


class PaymentRequestPartnerDetailSerializer(serializers.ModelSerializer):
    store_id = serializers.IntegerField(source="store.id", read_only=True)
    store_name = serializers.CharField(source="store.name", read_only=True)
    flow_type_display = serializers.CharField(
        source="get_flow_type_display",
        read_only=True,
    )
    merchant_confirmation_required = serializers.SerializerMethodField()

    class Meta:
        model = PaymentRequest
        fields = [
            "reference_code",
            "external_guid",
            "amount",
            "description",
            "status",
            "flow_type",
            "flow_type_display",
            "merchant_confirmation_required",
            "expires_at",
            "paid_at",
            "paid_by",
            "paid_wallet",
            "store_id",
            "store_name",
            "return_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_merchant_confirmation_required(self, obj):
        return obj.flow_type == PaymentFlowType.ONLINE


class PaymentActionResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()
    payment_reference_code = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    payment_request_status = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    payment_status = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    transaction_reference_code = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    next_action = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    merchant_confirmation_required = serializers.BooleanField(
        required=False,
        allow_null=True,
    )
    return_url = serializers.URLField(
        required=False,
        allow_null=True,
    )
    amount = serializers.IntegerField(
        required=False,
        allow_null=True,
    )


class PaymentVerifyResponseSerializer(PaymentActionResponseSerializer):
    """
    Backward-compatible alias for older imports/schemas.
    """
    pass


class PaymentRequestCreateResponseSerializer(PaymentActionResponseSerializer):
    payment_request_id = serializers.IntegerField()
    flow_type = serializers.CharField()
    payment_url = serializers.URLField()


# wallets/api/partner/v1/views/payment.py

from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin
from merchants.permissions import IsMerchant
from profiles.models import Profile
from store.authentication import StoreApiKeyAuthentication
from wallets.api.partner.v1.serializers import (
    PaymentActionResponseSerializer,
    PaymentRequestCreateResponseSerializer,
    PaymentRequestCreateSerializer,
    PaymentRequestPartnerDetailSerializer,
)
from wallets.api.payment_responses import (
    build_payment_response_payload,
    payment_error_response,
    payment_success_response,
)
from wallets.models import PaymentRequest
from wallets.services.payment import (
    check_and_expire_payment_request,
    create_payment_request,
    verify_payment_request,
)
from wallets.utils.choices import PaymentFlowType
from wallets.utils.consts import FRONTEND_PAYMENT_DETAIL_URL


@extend_schema(tags=["Wallet · Payment Requests (Partner)"])
class PartnerPaymentRequestViewSet(
    ScopedThrottleByActionMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    create:   POST /payment-requests/               -> create payment request
    retrieve: GET  /payment-requests/{ref}/         -> partner-side details
    verify:   POST /payment-requests/{ref}/verify/  -> finalize payment
    """

    authentication_classes = [StoreApiKeyAuthentication]
    permission_classes = [IsMerchant]
    serializer_class = PaymentRequestPartnerDetailSerializer
    lookup_field = "reference_code"
    lookup_value_regex = r"[-A-Za-z0-9_]+"

    throttle_scope_map = {
        "default": "partner-payment-read",
        "create": "partner-payment-write",
        "retrieve": "partner-payment-read",
        "verify": "partner-payment-write",
    }

    def get_queryset(self):
        return (
            PaymentRequest.objects.select_related("store", "paid_by", "paid_wallet")
            .filter(store=self.request.store)
        )

    @extend_schema(
        summary="ایجاد درخواست پرداخت",
        request=PaymentRequestCreateSerializer,
        responses={201: PaymentRequestCreateResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = PaymentRequestCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data["flow_type"] != PaymentFlowType.ONLINE:
            return payment_error_response(
                detail="ایجاد درخواست QR POS از این API مجاز نیست.",
                code="unsupported_flow_type",
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            profile = Profile.objects.select_related("user").get(
                national_id=data["national_id"]
            )
            customer = profile.user.customer
        except Profile.DoesNotExist:
            return payment_error_response(
                detail="مشتری با این کد ملی یافت نشد.",
                code="customer_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            return payment_error_response(
                detail="مشتری با این کد ملی یافت نشد.",
                code="customer_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        payment_request = create_payment_request(
            store=request.store,
            customer=customer,
            amount=data["amount"],
            return_url=data["return_url"],
            description=data.get("description", ""),
            external_guid=data.get("external_guid"),
            flow_type=PaymentFlowType.ONLINE,
        )

        payment_url = (
            f"{settings.FRONTEND_BASE_URL}"
            f"{FRONTEND_PAYMENT_DETAIL_URL}"
            f"{payment_request.reference_code}/"
        )

        payload = build_payment_response_payload(
            detail="درخواست پرداخت با موفقیت ایجاد شد.",
            code="payment_request_created",
            payment_request=payment_request,
            extra={
                "payment_request_id": payment_request.id,
                "flow_type": payment_request.flow_type,
                "payment_url": payment_url,
            },
        )

        serializer = PaymentRequestCreateResponseSerializer(payload)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="جزییات درخواست پرداخت",
        responses={200: PaymentRequestPartnerDetailSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        payment_request = self.get_object()
        check_and_expire_payment_request(payment_request, raise_exception=False)
        payment_request.refresh_from_db()

        serializer = PaymentRequestPartnerDetailSerializer(payment_request)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="تایید نهایی پرداخت",
        description="پس از پرداخت موفق توسط مشتری، فروشگاه پرداخت را نهایی می‌کند.",
        responses={
            200: PaymentActionResponseSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Payment request not found"),
        },
    )
    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, *args, **kwargs):
        reference_code = kwargs.get(self.lookup_field)
        try:
            payment_request = self.get_queryset().get(reference_code=reference_code)
        except PaymentRequest.DoesNotExist:
            return payment_error_response(
                detail="درخواست پرداخت پیدا نشد.",
                code="payment_request_not_found",
                http_status=status.HTTP_404_NOT_FOUND,
            )

        try:
            payment = verify_payment_request(
                payment_request,
                store=request.store,
            )
            payment_request.refresh_from_db()
            payment.refresh_from_db()
        except ValidationError as exc:
            return payment_error_response(
                detail=str(exc),
                code=getattr(exc, "code", "validation_error"),
                http_status=status.HTTP_400_BAD_REQUEST,
                payment_request=payment_request,
            )
        except Exception as exc:
            return payment_error_response(
                detail=str(exc),
                code="business_rule",
                http_status=status.HTTP_400_BAD_REQUEST,
                payment_request=payment_request,
            )

        payload_response = payment_success_response(
            detail="پرداخت نهایی شد.",
            code="payment_verified",
            payment_request=payment_request,
            payment=payment,
            http_status=status.HTTP_200_OK,
        )

        serializer = PaymentActionResponseSerializer(payload_response.data)
        return Response(serializer.data, status=payload_response.status_code)


# wallets/services/payment/payment_processing_service.py

from django.db import transaction
from rest_framework.exceptions import ValidationError

from credit.models.authorization import CreditAuthorization
from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.utils.choices import StatementLineType
from wallets.models import Payment, PaymentRequest, Transaction, Wallet
from wallets.services.payment.payment_request_service import (
    check_and_expire_payment_request,
    ensure_no_active_payment_exists,
    ensure_request_can_be_paid,
    resolve_payment_method,
    validate_payment_request_payer_access,
    validate_wallet_ownership,
)
from wallets.services.payment.payment_shared import (
    build_authorized_event_extra,
    create_event,
    credit_auth_hold_expiry,
    ensure_payment_request_status,
    get_latest_payment_for_request,
    get_escrow_wallet,
    get_merchant_gateway_wallet,
    logger,
    merchant_confirm_expiry,
)
from wallets.utils.choices import (
    PaymentEventType,
    PaymentFlowType,
    PaymentMethod,
    PaymentRequestStatus,
    PaymentStatus,
    TransactionPurpose,
)


def pay_payment_request(request_obj: PaymentRequest, user, wallet: Wallet):
    with transaction.atomic():
        payment_request = (
            PaymentRequest.objects.select_for_update()
            .select_related("store__merchant__user", "customer__user")
            .get(pk=request_obj.pk)
        )

        check_and_expire_payment_request(payment_request)
        ensure_request_can_be_paid(payment_request)
        validate_payment_request_payer_access(
            payment_request=payment_request,
            user=user,
        )

        customer_wallet = validate_wallet_ownership(user=user, wallet=wallet)
        ensure_no_active_payment_exists(payment_request)
        payment_method = resolve_payment_method(customer_wallet)

        payment = Payment.objects.create(
            payment_request=payment_request,
            payer=user,
            payer_wallet=customer_wallet,
            amount=payment_request.amount,
            method=payment_method,
            flow_type=payment_request.flow_type,
            status=PaymentStatus.CREATED,
        )

        if payment.method == PaymentMethod.CASH:
            _authorize_cash_payment(payment, customer_wallet)

            if payment.flow_type == PaymentFlowType.QR_POS:
                _settle_cash_payment(payment)
                payment.mark_completed()
                payment_request.mark_completed_direct(
                    user=user,
                    wallet=customer_wallet,
                )
                _log_request_completed_event(
                    payment_request=payment_request,
                    user=user,
                    wallet=customer_wallet,
                    payment=payment,
                    from_status=PaymentRequestStatus.CREATED,
                )
            else:
                _mark_payment_awaiting_merchant(payment)
                _move_request_to_awaiting_merchant(
                    payment_request=payment_request,
                    user=user,
                    wallet=customer_wallet,
                    merchant_deadline=payment.merchant_confirm_expires_at,
                    payment=payment,
                )

        elif payment.method == PaymentMethod.CREDIT:
            _authorize_credit_payment(payment)

            if payment.flow_type == PaymentFlowType.QR_POS:
                _settle_credit_payment(payment)
                payment.mark_completed()
                payment_request.mark_completed_direct(
                    user=user,
                    wallet=customer_wallet,
                )
                _log_request_completed_event(
                    payment_request=payment_request,
                    user=user,
                    wallet=customer_wallet,
                    payment=payment,
                    from_status=PaymentRequestStatus.CREATED,
                )
            else:
                _mark_payment_awaiting_merchant(payment)
                _move_request_to_awaiting_merchant(
                    payment_request=payment_request,
                    user=user,
                    wallet=customer_wallet,
                    merchant_deadline=payment.merchant_confirm_expires_at,
                    payment=payment,
                )

        return payment


def verify_payment_request(payment_request: PaymentRequest, *, store=None) -> Payment:
    with transaction.atomic():
        request_obj = (
            PaymentRequest.objects.select_for_update()
            .select_related("store__merchant__user")
            .get(pk=payment_request.pk)
        )

        if store is not None and request_obj.store_id != store.id:
            raise ValidationError(
                "این درخواست پرداخت متعلق به این فروشگاه نیست.",
                code="forbidden_store",
            )

        check_and_expire_payment_request(request_obj)
        latest_payment = get_latest_payment_for_request(request_obj)

        if request_obj.status == PaymentRequestStatus.COMPLETED:
            raise ValidationError(
                "این درخواست پرداخت قبلاً نهایی شده است.",
                code="already_completed",
            )

        if request_obj.status == PaymentRequestStatus.CANCELLED:
            raise ValidationError(
                "درخواست پرداخت لغو شده است.",
                code="cancelled",
            )

        if request_obj.status == PaymentRequestStatus.EXPIRED:
            raise ValidationError(
                "درخواست پرداخت منقضی شده است.",
                code="expired",
            )

        ensure_payment_request_status(
            request_obj,
            allowed_statuses={PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION},
            error_message="پرداخت قابل نهایی‌سازی نیست یا قبلاً تایید شده است.",
            error_code="invalid_state",
        )

        payment = (
            Payment.objects.select_for_update()
            .filter(
                payment_request=request_obj,
                status=PaymentStatus.AWAITING_MERCHANT_CONFIRMATION,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        if not payment:
            raise ValidationError(
                "پرداخت مرتبط برای نهایی‌سازی پیدا نشد.",
                code="missing_payment",
            )

        actor = None
        if store and getattr(store, "merchant", None):
            actor = getattr(store.merchant, "user", None)

        create_event(
            payment_request=request_obj,
            payment=latest_payment,
            actor=actor,
            event_type=PaymentEventType.PAYMENT_VERIFY_REQUESTED,
            from_status=request_obj.status,
            to_status=request_obj.status,
            description="Merchant requested payment verification.",
            extra_data={
                "store_id": store.id if store else None,
            },
        )

        if payment.method == PaymentMethod.CASH:
            _settle_cash_payment(payment)
        elif payment.method == PaymentMethod.CREDIT:
            _settle_credit_payment(payment)
        else:
            raise ValidationError(
                "روش پرداخت پشتیبانی نمی‌شود.",
                code="unsupported_payment_method",
            )

        from_status = request_obj.status
        payment.mark_completed()
        request_obj.mark_completed(
            user=request_obj.paid_by,
            wallet=request_obj.paid_wallet,
        )
        _log_request_completed_event(
            payment_request=request_obj,
            user=request_obj.paid_by,
            wallet=request_obj.paid_wallet,
            payment=payment,
            from_status=from_status,
        )
        return payment


def rollback_payment(payment_request: PaymentRequest):
    with transaction.atomic():
        request_obj = PaymentRequest.objects.select_for_update().get(
            pk=payment_request.pk
        )

        payment = (
            Payment.objects.select_for_update()
            .filter(payment_request=request_obj)
            .order_by("-created_at", "-id")
            .first()
        )
        if not payment:
            return None

        if payment.status == PaymentStatus.COMPLETED:
            return None

        if payment.method == PaymentMethod.CASH:
            return _rollback_cash_payment(payment)

        if payment.method == PaymentMethod.CREDIT:
            return _rollback_credit_payment(payment)

        return None


def _authorize_cash_payment(payment: Payment, customer_wallet: Wallet):
    escrow_wallet = get_escrow_wallet()

    if customer_wallet.available_balance < payment.amount:
        raise ValidationError(
            "موجودی کافی نیست.",
            code="insufficient_funds",
        )

    customer_wallet.balance -= payment.amount
    escrow_wallet.balance += payment.amount
    customer_wallet.save(update_fields=["balance"])
    escrow_wallet.save(update_fields=["balance"])

    escrow_transaction = Transaction.create_success(
        payment=payment,
        payment_request=payment.payment_request,
        from_wallet=customer_wallet,
        to_wallet=escrow_wallet,
        amount=payment.amount,
        purpose=TransactionPurpose.ESCROW_DEBIT,
        description="Customer → Escrow",
    )

    payment.mark_authorized()

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        transaction=escrow_transaction,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_AUTHORIZED,
        to_status=payment.status,
        description="Cash payment authorized.",
        extra_data=build_authorized_event_extra(
            payment=payment,
            wallet_id=customer_wallet.id,
        ),
    )


def _authorize_credit_payment(payment: Payment):
    from credit.models.credit_limit import CreditLimit

    credit_limit = CreditLimit.objects.get_user_credit_limit(payment.payer)
    if not credit_limit or not credit_limit.is_active:
        raise ValidationError(
            "اعتبار فعال یافت نشد یا منقضی شده است.",
            code="credit_unavailable",
        )
    if int(credit_limit.available_limit) < int(payment.amount):
        raise ValidationError(
            "اعتبار کافی نیست.",
            code="insufficient_credit",
        )

    authorization_expires_at = credit_auth_hold_expiry()

    authorization = CreditAuthorization.objects.create(
        user=payment.payer,
        payment=payment,
        payment_request=payment.payment_request,
        amount=int(payment.amount),
        status=CreditAuthorization.Status.ACTIVE,
        expires_at=authorization_expires_at,
    )

    payment.authorization_expires_at = authorization_expires_at
    payment.mark_authorized()

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_AUTHORIZED,
        to_status=payment.status,
        description="Credit payment authorized.",
        extra_data=build_authorized_event_extra(
            payment=payment,
            wallet_id=payment.payer_wallet_id,
            extra={"credit_authorization_id": authorization.id},
        ),
    )


def _mark_payment_awaiting_merchant(payment: Payment):
    payment.merchant_confirm_expires_at = merchant_confirm_expiry()
    payment.mark_awaiting_merchant()


def _move_request_to_awaiting_merchant(
        *,
        payment_request: PaymentRequest,
        user,
        wallet,
        merchant_deadline,
        payment: Payment,
):
    from_status = payment_request.status

    payment_request.mark_awaiting_merchant(
        user=user,
        wallet=wallet,
        merchant_deadline=merchant_deadline,
    )

    create_event(
        payment_request=payment_request,
        payment=payment,
        actor=user,
        event_type=PaymentEventType.AWAITING_MERCHANT,
        from_status=from_status,
        to_status=payment_request.status,
        description="Payment request is waiting for merchant confirmation.",
        extra_data={
            "merchant_confirm_expires_at": (
                merchant_deadline.isoformat() if merchant_deadline else None
            ),
            "wallet_id": wallet.id if wallet else None,
        },
    )


def _log_request_completed_event(
        *,
        payment_request: PaymentRequest,
        user,
        wallet,
        payment: Payment,
        from_status,
):
    create_event(
        payment_request=payment_request,
        payment=payment,
        actor=user,
        event_type=PaymentEventType.PAYMENT_COMPLETED,
        from_status=from_status,
        to_status=payment_request.status,
        description="Payment request completed.",
        extra_data={
            "wallet_id": wallet.id if wallet else None,
        },
    )


def _settle_cash_payment(payment):
    customer_to_escrow_txn = Transaction.latest_success_for_payment(
        payment,
        TransactionPurpose.ESCROW_DEBIT,
    )
    if not customer_to_escrow_txn:
        raise ValidationError(
            "تراکنش انتقال به امانی برای این پرداخت پیدا نشد.",
            code="missing_escrow_transaction",
        )

    escrow_wallet = Wallet.objects.select_for_update().get(
        pk=customer_to_escrow_txn.to_wallet_id
    )
    merchant_wallet = get_merchant_gateway_wallet(payment)

    if escrow_wallet.balance < payment.amount:
        logger.error(
            "ESCROW low balance verify: need %s, have %s",
            payment.amount,
            escrow_wallet.balance,
        )
        raise ValidationError(
            "عملیات با خطا مواجه شد. لطفاً بعداً تلاش کنید.",
            code="escrow_insufficient",
        )

    escrow_wallet.balance -= payment.amount
    merchant_wallet.balance += payment.amount
    escrow_wallet.save(update_fields=["balance"])
    merchant_wallet.save(update_fields=["balance"])

    settlement_txn = Transaction.create_success(
        payment=payment,
        payment_request=payment.payment_request,
        from_wallet=escrow_wallet,
        to_wallet=merchant_wallet,
        amount=payment.amount,
        purpose=TransactionPurpose.SETTLEMENT,
        description="Escrow → Merchant",
        related_transaction=customer_to_escrow_txn,
    )

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        transaction=settlement_txn,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_SETTLED,
        description="Cash payment settled from escrow to merchant.",
        extra_data={
            "transaction_id": settlement_txn.id,
            "amount": payment.amount,
        },
    )
    return settlement_txn


def _settle_credit_payment(payment: Payment):
    auth = (
        CreditAuthorization.objects.select_for_update()
        .filter(
            payment=payment,
            payment_request=payment.payment_request,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if not auth:
        raise ValidationError(
            "Authorization not found.",
            code="missing_authorization",
        )

    if auth.status == CreditAuthorization.Status.SETTLED:
        return auth

    if auth.status != CreditAuthorization.Status.ACTIVE:
        raise ValidationError(
            "Authorization is not active.",
            code="invalid_authorization_state",
        )

    auth.status = CreditAuthorization.Status.SETTLED
    auth.save(update_fields=["status"])

    statement, _ = Statement.objects.get_or_create_current_statement(
        payment.payer
    )
    existing_line = StatementLine.all_objects.filter(
        payment=payment,
        type=StatementLineType.PURCHASE,
    ).first()
    if existing_line:
        return auth

    StatementLine.objects.create(
        statement=statement,
        type=StatementLineType.PURCHASE,
        amount=payment.amount,
        payment=payment,
        payment_request=payment.payment_request,
        description=f"Purchase {payment.payment_request.reference_code}",
    )

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_SETTLED,
        description="Credit payment settled.",
        extra_data={
            "credit_authorization_id": auth.id,
            "amount": payment.amount,
        },
    )
    return auth


def _rollback_cash_payment(payment: Payment):
    if Transaction.success_exists_for_payment(payment, TransactionPurpose.REVERSAL):
        return Transaction.latest_success_for_payment(
            payment,
            TransactionPurpose.REVERSAL,
        )

    if Transaction.success_exists_for_payment(payment, TransactionPurpose.SETTLEMENT):
        return None

    debit_transaction = Transaction.latest_success_for_payment(
        payment,
        TransactionPurpose.ESCROW_DEBIT,
    )
    if not debit_transaction:
        return None

    escrow_wallet = Wallet.objects.select_for_update().get(
        pk=debit_transaction.to_wallet_id
    )
    customer_wallet = Wallet.objects.select_for_update().get(
        pk=debit_transaction.from_wallet_id
    )

    if escrow_wallet.balance < debit_transaction.amount:
        logger.error(
            "ESCROW low balance rollback: need %s, have %s",
            debit_transaction.amount,
            escrow_wallet.balance,
        )
        raise ValidationError(
            "عملیات بازگشت وجه با خطا مواجه شد.",
            code="escrow_insufficient",
        )

    escrow_wallet.balance -= debit_transaction.amount
    customer_wallet.balance += debit_transaction.amount
    escrow_wallet.save(update_fields=["balance"])
    customer_wallet.save(update_fields=["balance"])

    reversal = Transaction.create_success(
        payment=payment,
        payment_request=payment.payment_request,
        related_transaction=debit_transaction,
        from_wallet=escrow_wallet,
        to_wallet=customer_wallet,
        amount=debit_transaction.amount,
        purpose=TransactionPurpose.REVERSAL,
        description="Escrow → Customer (reversal)",
    )

    if payment.payment_request.status == PaymentRequestStatus.CANCELLED:
        payment.mark_cancelled()
    elif payment.payment_request.status == PaymentRequestStatus.EXPIRED:
        payment.mark_expired()

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        transaction=reversal,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_ROLLBACK,
        to_status=payment.status,
        description="Cash payment rolled back.",
        extra_data={
            "transaction_id": reversal.id,
            "amount": reversal.amount,
        },
    )
    return reversal


def _rollback_credit_payment(payment: Payment):
    auth = (
        CreditAuthorization.objects.select_for_update()
        .filter(
            payment=payment,
            payment_request=payment.payment_request,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if not auth:
        return None

    if auth.status == CreditAuthorization.Status.ACTIVE:
        auth.status = CreditAuthorization.Status.RELEASED
        auth.save(update_fields=["status"])

    if payment.payment_request.status == PaymentRequestStatus.CANCELLED:
        payment.mark_cancelled()
    elif payment.payment_request.status == PaymentRequestStatus.EXPIRED:
        payment.mark_expired()

    create_event(
        payment_request=payment.payment_request,
        payment=payment,
        actor=payment.payer,
        event_type=PaymentEventType.PAYMENT_ROLLBACK,
        to_status=payment.status,
        description="Credit authorization released / rolled back.",
        extra_data={
            "credit_authorization_id": auth.id,
            "amount": payment.amount,
        },
    )
    return auth


# wallets/services/payment/payment_request_service.py

from django.db import transaction
from rest_framework.exceptions import ValidationError

from wallets.models import PaymentRequest, Wallet
from wallets.services.payment.payment_shared import (
    create_event,
    credit_auth_hold_expiry,
    ensure_payment_request_status,
    get_latest_payment_for_request,
    get_payment_method_from_wallet,
    is_terminal_payment_request_status,
    now_local,
)
from wallets.utils.choices import (
    OwnerType,
    PaymentEventType,
    PaymentFlowType,
    PaymentRequestStatus,
    PaymentStatus,
    WalletKind,
)


def create_payment_request(
        store,
        amount,
        return_url,
        customer=None,
        description="",
        external_guid=None,
        flow_type=PaymentFlowType.ONLINE,
        actor=None,
):
    created_deadline = credit_auth_hold_expiry()

    payment_request = PaymentRequest.objects.create(
        store=store,
        amount=amount,
        customer=customer,
        status=PaymentRequestStatus.CREATED,
        description=description,
        return_url=return_url,
        external_guid=external_guid,
        flow_type=flow_type,
        created_expires_at=created_deadline,
        expires_at=created_deadline,
    )

    create_event(
        payment_request=payment_request,
        event_type=PaymentEventType.PAYMENT_REQUEST_CREATED,
        actor=actor if actor is not None else getattr(customer, "user", None),
        to_status=payment_request.status,
        description="Payment request created.",
        extra_data={
            "amount": payment_request.amount,
            "flow_type": payment_request.flow_type,
            "store_id": payment_request.store_id,
        },
    )
    return payment_request


def list_eligible_wallets_for_payment_request(user, payment_request):
    wallets = Wallet.objects.filter(
        user=user,
        owner_type=OwnerType.CUSTOMER,
    ).order_by("kind")

    eligible_ids = []

    for wallet in wallets:
        if wallet.kind == WalletKind.CASH:
            if int(wallet.available_balance or 0) >= int(payment_request.amount):
                eligible_ids.append(wallet.id)
        elif wallet.kind == WalletKind.CREDIT:
            from credit.models.credit_limit import CreditLimit

            credit_limit = CreditLimit.objects.get_user_credit_limit(user)
            if (
                    credit_limit
                    and getattr(credit_limit, "is_active", False)
                    and getattr(credit_limit, "available_limit", 0) >= int(
                payment_request.amount
            )
            ):
                eligible_ids.append(wallet.id)

    return wallets.filter(id__in=eligible_ids)


def check_and_expire_payment_request(
        payment_request: PaymentRequest,
        *,
        raise_exception: bool = True,
) -> bool:
    payment_request = PaymentRequest.objects.get(pk=payment_request.pk)

    if payment_request.expires_at and payment_request.expires_at < now_local():
        if not is_terminal_payment_request_status(payment_request.status):
            expire_payment_request(payment_request)

        if raise_exception:
            raise ValidationError(
                detail="درخواست پرداخت منقضی شده است.",
                code="expired",
            )
        return True

    return False


def expire_payment_request(payment_request: PaymentRequest):
    from wallets.services.payment.payment_processing_service import rollback_payment

    with transaction.atomic():
        request_obj = PaymentRequest.objects.select_for_update().get(
            pk=payment_request.pk
        )

        if request_obj.status == PaymentRequestStatus.EXPIRED:
            return request_obj

        if request_obj.status in {
            PaymentRequestStatus.CANCELLED,
            PaymentRequestStatus.COMPLETED,
        }:
            return request_obj

        from_status = request_obj.status
        request_obj.mark_expired()
        rollback_payment(request_obj)

        latest_payment = get_latest_payment_for_request(request_obj)
        create_event(
            payment_request=request_obj,
            payment=latest_payment,
            actor=request_obj.paid_by,
            event_type=PaymentEventType.PAYMENT_EXPIRED,
            from_status=from_status,
            to_status=request_obj.status,
            description="Payment request expired.",
        )
        return request_obj


def cancel_payment_request(payment_request: PaymentRequest):
    from wallets.services.payment.payment_processing_service import rollback_payment

    with transaction.atomic():
        request_obj = PaymentRequest.objects.select_for_update().get(
            pk=payment_request.pk
        )

        if request_obj.status == PaymentRequestStatus.CANCELLED:
            return request_obj

        if request_obj.status in {
            PaymentRequestStatus.EXPIRED,
            PaymentRequestStatus.COMPLETED,
        }:
            return request_obj

        from_status = request_obj.status
        request_obj.mark_cancelled()
        rollback_payment(request_obj)

        latest_payment = get_latest_payment_for_request(request_obj)
        create_event(
            payment_request=request_obj,
            payment=latest_payment,
            actor=request_obj.paid_by,
            event_type=PaymentEventType.PAYMENT_CANCELLED,
            from_status=from_status,
            to_status=request_obj.status,
            description="Payment request cancelled.",
        )
        return request_obj


def validate_wallet_ownership(*, user, wallet):
    customer_wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)

    if (
            customer_wallet.user_id != user.id
            or customer_wallet.owner_type != OwnerType.CUSTOMER
    ):
        raise ValidationError(
            "کیف پول برای کاربر نیست.",
            code="wallet_not_owned",
        )

    return customer_wallet


def validate_payment_request_payer_access(*, payment_request, user):
    """
    Access rules:
    - If payment request is customer-bound, only that customer can pay.
    - If payment request has no customer, any authenticated customer can pay.
    """
    bound_customer = getattr(payment_request, "customer", None)

    if not bound_customer:
        return

    user_customer = getattr(user, "customer", None)
    if not user_customer or user_customer.id != bound_customer.id:
        raise ValidationError(
            "این درخواست پرداخت برای شما نیست.",
            code="payment_request_not_allowed",
        )


def ensure_request_can_be_paid(payment_request):
    ensure_payment_request_status(
        payment_request,
        allowed_statuses={PaymentRequestStatus.CREATED},
        error_message="پرداخت در این وضعیت قابل انجام نیست.",
    )


def ensure_no_active_payment_exists(payment_request):
    existing_payment = (
        payment_request.payments.select_for_update()
        .filter(
            status__in=[
                PaymentStatus.CREATED,
                PaymentStatus.AUTHORIZED,
                PaymentStatus.AWAITING_MERCHANT_CONFIRMATION,
                PaymentStatus.COMPLETED,
            ],
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if existing_payment:
        raise ValidationError(
            "این درخواست پرداخت قبلاً پردازش شده است.",
            code="already_processed",
        )
    return existing_payment


def resolve_payment_method(wallet):
    return get_payment_method_from_wallet(wallet)


# wallets/tests/partner/v1/views/test_payment_partner_api.py

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from merchants.models import Merchant
from store.authentication import StoreApiKeyAuthentication
from store.models import Store
from wallets.models import PaymentRequest, Wallet
from wallets.services.payment import pay_payment_request
from wallets.utils.choices import (
    OwnerType,
    PaymentFlowType,
    PaymentRequestStatus,
    PaymentStatus,
    WalletKind,
)
from wallets.utils.escrow import ensure_escrow_wallet_exists


@pytest.mark.django_db
class TestPartnerPaymentRequestApi:
    def _build_partner_client(self, monkeypatch, *, store, user):
        client = APIClient()

        def fake_authenticate(self, request):
            request.store = store
            request.store_api_key = None
            return user, None

        monkeypatch.setattr(
            StoreApiKeyAuthentication,
            "authenticate",
            fake_authenticate,
        )
        return client

    def test_create_online_payment_request_success(
            self,
            monkeypatch,
            store,
            merchant_user,
            customer_user,
    ):
        customer_user.profile.national_id = "1234567890"
        customer_user.profile.save(update_fields=["national_id"])

        client = self._build_partner_client(
            monkeypatch,
            store=store,
            user=merchant_user,
        )

        url = reverse("wallets_partner_v1:partner-payment-request-list")
        response = client.post(
            url,
            {
                "amount": 250000,
                "return_url": "https://merchant.example.com/callback",
                "description": "online payment request",
                "external_guid": "ORD-1001",
                "national_id": "1234567890",
                "flow_type": PaymentFlowType.ONLINE,
            },
            format="json",
        )

        assert response.status_code == 201, response.data
        assert response.data["code"] == "payment_request_created"
        assert response.data["amount"] == 250000
        assert response.data["payment_request_status"] == PaymentRequestStatus.CREATED
        assert response.data["flow_type"] == PaymentFlowType.ONLINE
        assert response.data["payment_reference_code"]
        assert response.data["merchant_confirmation_required"] is True
        assert response.data["payment_url"].endswith(
            f'{response.data["payment_reference_code"]}/'
        )

        payment_request = PaymentRequest.objects.get(
            reference_code=response.data["payment_reference_code"]
        )
        assert payment_request.store == store
        assert payment_request.customer == customer_user.customer
        assert payment_request.flow_type == PaymentFlowType.ONLINE
        assert payment_request.external_guid == "ORD-1001"

    def test_create_qr_payment_request_from_partner_api_returns_400(
            self,
            monkeypatch,
            store,
            merchant_user,
            customer_user,
    ):
        customer_user.profile.national_id = "2222222222"
        customer_user.profile.save(update_fields=["national_id"])

        client = self._build_partner_client(
            monkeypatch,
            store=store,
            user=merchant_user,
        )

        url = reverse("wallets_partner_v1:partner-payment-request-list")
        response = client.post(
            url,
            {
                "amount": 78000,
                "return_url": "https://merchant.example.com/qr-callback",
                "description": "qr payment request",
                "national_id": "2222222222",
                "flow_type": PaymentFlowType.QR_POS,
            },
            format="json",
        )

        assert response.status_code == 400, response.data
        assert "flow_type" in response.data

    def test_create_payment_request_customer_not_found_returns_404(
            self,
            monkeypatch,
            store,
            merchant_user,
    ):
        client = self._build_partner_client(
            monkeypatch,
            store=store,
            user=merchant_user,
        )

        url = reverse("wallets_partner_v1:partner-payment-request-list")
        response = client.post(
            url,
            {
                "amount": 50000,
                "return_url": "https://merchant.example.com/callback",
                "description": "missing customer",
                "national_id": "9999999999",
                "flow_type": PaymentFlowType.ONLINE,
            },
            format="json",
        )

        assert response.status_code == 404
        assert response.data["code"] == "customer_not_found"
        assert response.data["detail"] == "مشتری با این کد ملی یافت نشد."

    def test_retrieve_payment_request_detail_success(
            self,
            monkeypatch,
            store,
            merchant_user,
            customer_user,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=120000,
            return_url="https://merchant.example.com/callback",
            description="detail test",
            flow_type=PaymentFlowType.ONLINE,
        )

        client = self._build_partner_client(
            monkeypatch,
            store=store,
            user=merchant_user,
        )

        url = reverse(
            "wallets_partner_v1:partner-payment-request-detail",
            args=[payment_request.reference_code],
        )
        response = client.get(url)

        assert response.status_code == 200, response.data
        assert response.data["reference_code"] == payment_request.reference_code
        assert response.data["amount"] == 120000
        assert response.data["flow_type"] == PaymentFlowType.ONLINE
        assert response.data["merchant_confirmation_required"] is True
        assert response.data["store_id"] == store.id
        assert response.data["store_name"] == store.name

    def test_retrieve_expired_payment_request_marks_it_expired(
            self,
            monkeypatch,
            store,
            merchant_user,
            customer_user,
    ):
        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=33000,
            return_url="https://merchant.example.com/callback",
            expires_at=timezone.localtime(timezone.now()) - timezone.timedelta(
                minutes=5
            ),
            flow_type=PaymentFlowType.ONLINE,
        )

        client = self._build_partner_client(
            monkeypatch,
            store=store,
            user=merchant_user,
        )

        url = reverse(
            "wallets_partner_v1:partner-payment-request-detail",
            args=[payment_request.reference_code],
        )
        response = client.get(url)

        assert response.status_code == 200, response.data

        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.EXPIRED
        assert response.data["status"] == PaymentRequestStatus.EXPIRED

    def test_verify_online_payment_success(
            self,
            monkeypatch,
            store,
            merchant_user,
            customer_user,
            customer_cash_wallet,
    ):
        ensure_escrow_wallet_exists()

        Wallet.objects.get_or_create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            defaults={"balance": 0},
        )

        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=45000,
            return_url="https://merchant.example.com/callback",
            flow_type=PaymentFlowType.ONLINE,
        )

        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_cash_wallet,
        )
        payment.refresh_from_db()
        payment_request.refresh_from_db()

        assert payment.status == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION
        assert (
                payment_request.status
                == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        )

        client = self._build_partner_client(
            monkeypatch,
            store=store,
            user=merchant_user,
        )

        url = reverse(
            "wallets_partner_v1:partner-payment-request-verify",
            args=[payment_request.reference_code],
        )
        response = client.post(url, {}, format="json")

        assert response.status_code == 200, response.data
        assert response.data["detail"] == "پرداخت نهایی شد."
        assert response.data["code"] == "payment_verified"
        assert response.data["payment_reference_code"] == payment_request.reference_code
        assert response.data["payment_status"] == PaymentStatus.COMPLETED
        assert (
                response.data["payment_request_status"]
                == PaymentRequestStatus.COMPLETED
        )
        assert response.data["next_action"] == "none"
        assert response.data["merchant_confirmation_required"] is True
        assert response.data["amount"] == payment_request.amount

        payment.refresh_from_db()
        payment_request.refresh_from_db()
        assert payment.status == PaymentStatus.COMPLETED
        assert payment_request.status == PaymentRequestStatus.COMPLETED

    def test_verify_with_wrong_store_returns_404(
            self,
            monkeypatch,
            store,
            merchant_user,
            customer_user,
            customer_cash_wallet,
            user_factory,
    ):
        ensure_escrow_wallet_exists()

        Wallet.objects.get_or_create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            defaults={"balance": 0},
        )

        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=61000,
            return_url="https://merchant.example.com/callback",
            flow_type=PaymentFlowType.ONLINE,
        )
        pay_payment_request(
            payment_request,
            customer_user,
            customer_cash_wallet,
        )

        other_merchant_user = user_factory("merchant_user_2")
        other_merchant = Merchant.objects.create(user=other_merchant_user)
        other_store = Store.objects.create(
            name="other-store",
            merchant=other_merchant,
        )

        client = self._build_partner_client(
            monkeypatch,
            store=other_store,
            user=other_merchant_user,
        )

        url = reverse(
            "wallets_partner_v1:partner-payment-request-verify",
            args=[payment_request.reference_code],
        )
        response = client.post(url, {}, format="json")

        assert response.status_code == 404


# wallets/tests/services/test_payment.py

import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from customers.models import Customer
from wallets.models import Wallet, PaymentRequest
from wallets.services.payment import (
    check_and_expire_payment_request,
    create_payment_request,
    pay_payment_request,
    rollback_payment,
    verify_payment_request,
)
from wallets.utils.choices import (
    OwnerType,
    PaymentFlowType,
    PaymentRequestStatus,
    PaymentStatus,
    TransactionPurpose,
    TransactionStatus,
    WalletKind,
)
from wallets.utils.consts import ESCROW_USER_NAME, ESCROW_WALLET_KIND


@pytest.mark.django_db
class TestPaymentService:

    def make_env(self, store, customer_user, ensure_escrow):
        customer_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=50_000,
        )
        merchant_wallet = Wallet.objects.create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            balance=0,
        )
        escrow_wallet = Wallet.objects.get(
            user__username=ESCROW_USER_NAME,
            kind=ESCROW_WALLET_KIND,
        )
        return customer_wallet, merchant_wallet, escrow_wallet

    def test_full_payment_flow_cash(self, store, customer_user, ensure_escrow):
        customer_wallet, merchant_wallet, escrow_wallet = self.make_env(
            store, customer_user, ensure_escrow
        )
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=1234,
            return_url="https://yourshop.com",
        )

        payment = pay_payment_request(payment_request, customer_user, customer_wallet)
        payment_request.refresh_from_db()
        payment.refresh_from_db()
        escrow_wallet.refresh_from_db()

        assert payment_request.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        assert payment.status == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION
        assert escrow_wallet.balance >= 1234

        debit = payment.transactions.get(purpose=TransactionPurpose.ESCROW_DEBIT)
        assert debit.status == TransactionStatus.SUCCESS

        verified_payment = verify_payment_request(payment_request, store=store)
        payment_request.refresh_from_db()
        verified_payment.refresh_from_db()
        merchant_wallet.refresh_from_db()

        assert payment_request.status == PaymentRequestStatus.COMPLETED
        assert verified_payment.status == PaymentStatus.COMPLETED
        assert merchant_wallet.balance >= 1234

        settlement = verified_payment.transactions.get(
            purpose=TransactionPurpose.SETTLEMENT
        )
        assert settlement.status == TransactionStatus.SUCCESS

        old_balance = merchant_wallet.balance
        rollback_payment(payment_request)
        merchant_wallet.refresh_from_db()
        assert merchant_wallet.balance == old_balance

    def test_qr_cash_payment_is_finalized_immediately(
            self, store, customer_user, ensure_escrow
    ):
        customer_wallet, merchant_wallet, _ = self.make_env(
            store, customer_user, ensure_escrow
        )
        payment_request = create_payment_request(
            store=store,
            customer=None,
            amount=2000,
            return_url="https://qr.com",
            flow_type=PaymentFlowType.QR_POS,
        )

        payment = pay_payment_request(payment_request, customer_user, customer_wallet)
        payment_request.refresh_from_db()
        payment.refresh_from_db()
        merchant_wallet.refresh_from_db()

        assert payment_request.status == PaymentRequestStatus.COMPLETED
        assert payment.status == PaymentStatus.COMPLETED
        assert payment_request.paid_by == customer_user
        assert payment_request.paid_wallet == customer_wallet
        assert payment.transactions.filter(
            purpose=TransactionPurpose.ESCROW_DEBIT
        ).exists()
        assert payment.transactions.filter(
            purpose=TransactionPurpose.SETTLEMENT
        ).exists()
        assert merchant_wallet.balance >= 2000

    def test_bound_request_cannot_be_paid_by_other_customer(
            self, store, customer_user, ensure_escrow, user_factory
    ):
        other_user = user_factory("other_customer_for_service")
        Customer.objects.get_or_create(user=other_user)

        other_wallet = Wallet.objects.create(
            user=other_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=50_000,
        )

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=100,
            return_url="https://ok.com",
        )

        with pytest.raises(ValidationError) as exc:
            pay_payment_request(payment_request, other_user, other_wallet)

        assert exc.value.get_codes()[0] == "payment_request_not_allowed"

    def test_expired_payment_request(self, store, customer_user):
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=500,
            return_url="https://ok.com",
        )
        payment_request.expires_at = payment_request.expires_at.replace(year=2000)
        payment_request.save(update_fields=["expires_at"])

        with pytest.raises(ValidationError):
            check_and_expire_payment_request(payment_request)

        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.EXPIRED

    def test_insufficient_balance_cash(self, store, customer_user, ensure_escrow):
        wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=1,
        )
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=100,
            return_url="https://ok.com",
        )
        with pytest.raises(ValidationError):
            pay_payment_request(payment_request, customer_user, wallet)

    def test_pay_with_wrong_wallet_owner(self, store, customer_user, ensure_escrow):
        other = get_user_model().objects.create(username="other")
        wrong_wallet = Wallet.objects.create(
            user=other,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=5_000,
        )
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=100,
            return_url="https://ok.com",
        )
        with pytest.raises(ValidationError):
            pay_payment_request(payment_request, customer_user, wrong_wallet)

    def test_verify_wrong_status(self, store, customer_user):
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=100,
            return_url="https://ok.com",
        )
        with pytest.raises(ValidationError):
            verify_payment_request(payment_request, store=store)

    def test_double_verify(
            self, store, customer_user, customer_cash_wallet, ensure_escrow
    ):
        Wallet.objects.get_or_create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            defaults={"balance": 0},
        )

        payment_request = PaymentRequest.objects.create(
            store=store,
            customer=customer_user.customer,
            amount=10_000,
            return_url="https://callback.example.com",
        )

        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_cash_wallet,
        )

        assert payment.status == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION

        first_verified_payment = verify_payment_request(payment_request, store=store)
        payment_request.refresh_from_db()
        first_verified_payment.refresh_from_db()

        assert payment_request.status == PaymentRequestStatus.COMPLETED
        assert first_verified_payment.status == PaymentStatus.COMPLETED

        with pytest.raises(ValidationError) as exc:
            verify_payment_request(payment_request, store=store)

        assert str(exc.value.detail[0]) == "این درخواست پرداخت قبلاً نهایی شده است."
        assert exc.value.get_codes()[0] == "already_completed"

    def test_double_rollback_is_idempotent(self, store, customer_user, ensure_escrow):
        customer_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=1_000,
        )
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=100,
            return_url="https://ok.com",
        )
        pay_payment_request(payment_request, customer_user, customer_wallet)
        payment_request.mark_expired()
        rollback_payment(payment_request)
        customer_wallet.refresh_from_db()
        before = customer_wallet.balance
        rollback_payment(payment_request)
        customer_wallet.refresh_from_db()
        assert customer_wallet.balance == before

    def test_escrow_wallet_insufficient_on_verify(
            self, store, customer_user, ensure_escrow
    ):
        customer_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=10_000,
        )
        Wallet.objects.create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            balance=0,
        )
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=1000,
            return_url="https://ok.com",
        )
        payment = pay_payment_request(payment_request, customer_user, customer_wallet)
        debit = payment.transactions.get(purpose=TransactionPurpose.ESCROW_DEBIT)
        escrow_wallet = debit.to_wallet
        escrow_wallet.balance = 0
        escrow_wallet.save(update_fields=["balance"])

        with pytest.raises(ValidationError):
            verify_payment_request(payment_request, store=store)


@pytest.mark.django_db
class TestPaymentNegativePaths:

    def test_verify_without_merchant_wallet_fails_and_state_unchanged(
            self, store, customer_user, ensure_escrow
    ):
        customer_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=50_000,
        )
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=12_345,
            return_url="https://cb.com",
        )
        payment = pay_payment_request(payment_request, customer_user, customer_wallet)

        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        payment.refresh_from_db()
        assert payment.status == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION

        with pytest.raises(ValidationError):
            verify_payment_request(payment_request, store=store)

        payment_request.refresh_from_db()
        payment.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        assert payment.status == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION

    def test_verify_awaiting_but_without_related_payment(self, store, customer_user):
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=999,
            return_url="https://ok.com",
        )
        payment_request.status = PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        payment_request.save(update_fields=["status"])

        with pytest.raises(ValidationError) as exc:
            verify_payment_request(payment_request, store=store)

        assert "پرداخت مرتبط" in str(exc.value)


# wallets/tests/services/test_payment_events.py

import pytest
from rest_framework.exceptions import ValidationError

from wallets.models import PaymentEvent, Wallet
from wallets.services.payment import (
    check_and_expire_payment_request,
    create_payment_request,
    pay_payment_request,
    rollback_payment,
    verify_payment_request,
)
from wallets.utils.choices import (
    OwnerType,
    PaymentEventType,
    PaymentFlowType,
    PaymentRequestStatus,
    TransactionPurpose,
    WalletKind,
)
from wallets.utils.consts import ESCROW_USER_NAME, ESCROW_WALLET_KIND


@pytest.mark.django_db
class TestPaymentEvents:
    def _make_cash_env(self, store, customer_user):
        customer_wallet = Wallet.objects.create(
            user=customer_user,
            kind=WalletKind.CASH,
            owner_type=OwnerType.CUSTOMER,
            balance=100_000,
        )
        merchant_wallet = Wallet.objects.create(
            user=store.merchant.user,
            kind=WalletKind.MERCHANT_GATEWAY,
            owner_type=OwnerType.MERCHANT,
            balance=0,
        )
        escrow_wallet = Wallet.objects.get(
            user__username=ESCROW_USER_NAME,
            kind=ESCROW_WALLET_KIND,
        )
        return customer_wallet, merchant_wallet, escrow_wallet

    def test_create_payment_request_creates_event(
            self,
            store,
            customer_user,
    ):
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=25_000,
            return_url="https://example.com/callback",
        )

        events = PaymentEvent.objects.filter(
            payment_request=payment_request
        ).order_by("created_at", "id")

        assert events.count() == 1

        event = events.first()
        assert event.event_type == PaymentEventType.PAYMENT_REQUEST_CREATED
        assert event.payment is None
        assert event.actor == customer_user
        assert event.to_status == PaymentRequestStatus.CREATED
        assert event.extra_data["amount"] == payment_request.amount
        assert event.extra_data["flow_type"] == payment_request.flow_type
        assert event.extra_data["store_id"] == store.id

    def test_create_qr_pos_payment_request_with_merchant_actor_creates_event(
            self,
            store,
            merchant_user,
    ):
        payment_request = create_payment_request(
            store=store,
            customer=None,
            amount=18_000,
            return_url="https://example.com/pos-callback",
            flow_type=PaymentFlowType.QR_POS,
            actor=merchant_user,
        )

        event = PaymentEvent.objects.filter(
            payment_request=payment_request,
            event_type=PaymentEventType.PAYMENT_REQUEST_CREATED,
        ).order_by("-created_at", "-id").first()

        assert event is not None
        assert event.actor == merchant_user
        assert event.payment is None
        assert event.to_status == PaymentRequestStatus.CREATED
        assert event.extra_data["flow_type"] == PaymentFlowType.QR_POS
        assert event.extra_data["store_id"] == store.id
        assert event.extra_data["amount"] == payment_request.amount

    def test_online_cash_payment_creates_authorized_and_awaiting_events(
            self,
            store,
            customer_user,
            ensure_escrow,
    ):
        customer_wallet, _, _ = self._make_cash_env(store, customer_user)

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=12_345,
            return_url="https://example.com/callback",
            flow_type=PaymentFlowType.ONLINE,
        )

        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_wallet,
        )

        events = list(
            PaymentEvent.objects.filter(payment_request=payment_request)
            .order_by("created_at", "id")
        )

        event_types = [event.event_type for event in events]

        assert PaymentEventType.PAYMENT_REQUEST_CREATED in event_types
        assert PaymentEventType.PAYMENT_AUTHORIZED in event_types
        assert PaymentEventType.AWAITING_MERCHANT in event_types

        authorized_event = next(
            event for event in events
            if event.event_type == PaymentEventType.PAYMENT_AUTHORIZED
        )
        assert authorized_event.payment_id == payment.id
        assert authorized_event.actor_id == customer_user.id
        assert authorized_event.extra_data["payment_method"] == payment.method
        assert authorized_event.extra_data["flow_type"] == payment.flow_type
        assert authorized_event.extra_data["wallet_id"] == customer_wallet.id

        awaiting_event = next(
            event for event in events
            if event.event_type == PaymentEventType.AWAITING_MERCHANT
        )
        assert awaiting_event.payment_id == payment.id
        assert awaiting_event.actor_id == customer_user.id
        assert awaiting_event.to_status == PaymentRequestStatus.AWAITING_MERCHANT_CONFIRMATION
        assert awaiting_event.extra_data["wallet_id"] == customer_wallet.id
        assert awaiting_event.extra_data["merchant_confirm_expires_at"] is not None

    def test_verify_online_cash_payment_creates_verify_settle_and_complete_events(
            self,
            store,
            customer_user,
            ensure_escrow,
    ):
        customer_wallet, merchant_wallet, _ = self._make_cash_env(
            store,
            customer_user,
        )
        merchant_wallet.balance = 0
        merchant_wallet.save(update_fields=["balance"])

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=40_000,
            return_url="https://example.com/callback",
            flow_type=PaymentFlowType.ONLINE,
        )

        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_wallet,
        )

        verified_payment = verify_payment_request(
            payment_request,
            store=store,
        )

        events = list(
            PaymentEvent.objects.filter(payment_request=payment_request)
            .order_by("created_at", "id")
        )
        event_types = [event.event_type for event in events]

        assert PaymentEventType.PAYMENT_VERIFY_REQUESTED in event_types
        assert PaymentEventType.PAYMENT_SETTLED in event_types
        assert PaymentEventType.PAYMENT_COMPLETED in event_types

        verify_event = next(
            event for event in events
            if event.event_type == PaymentEventType.PAYMENT_VERIFY_REQUESTED
        )
        assert verify_event.payment_id == payment.id
        assert verify_event.actor_id == store.merchant.user_id
        assert verify_event.extra_data["store_id"] == store.id

        settled_event = next(
            event for event in events
            if event.event_type == PaymentEventType.PAYMENT_SETTLED
        )
        assert settled_event.payment_id == verified_payment.id
        assert settled_event.transaction is not None
        assert settled_event.extra_data["amount"] == verified_payment.amount
        assert settled_event.extra_data[
                   "transaction_id"] == settled_event.transaction_id

        completed_event = next(
            event for event in events
            if event.event_type == PaymentEventType.PAYMENT_COMPLETED
        )
        assert completed_event.payment_id == verified_payment.id
        assert completed_event.to_status == PaymentRequestStatus.COMPLETED

    def test_expire_created_request_creates_expired_event(
            self,
            store,
            customer_user,
    ):
        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=5_000,
            return_url="https://example.com/callback",
        )
        payment_request.expires_at = payment_request.expires_at.replace(year=2000)
        payment_request.save(update_fields=["expires_at"])

        with pytest.raises(ValidationError):
            check_and_expire_payment_request(payment_request)

        payment_request.refresh_from_db()
        assert payment_request.status == PaymentRequestStatus.EXPIRED

        expired_event = PaymentEvent.objects.filter(
            payment_request=payment_request,
            event_type=PaymentEventType.PAYMENT_EXPIRED,
        ).order_by("-created_at", "-id").first()

        assert expired_event is not None
        assert expired_event.to_status == PaymentRequestStatus.EXPIRED

    def test_expired_cash_payment_rollback_creates_single_rollback_event(
            self,
            store,
            customer_user,
            ensure_escrow,
    ):
        customer_wallet, _, _ = self._make_cash_env(store, customer_user)

        payment_request = create_payment_request(
            store=store,
            customer=customer_user.customer,
            amount=7_500,
            return_url="https://example.com/callback",
        )

        payment = pay_payment_request(
            payment_request,
            customer_user,
            customer_wallet,
        )
        payment_request.mark_expired()

        rollback_result_first = rollback_payment(payment_request)
        rollback_result_second = rollback_payment(payment_request)

        assert rollback_result_first is not None
        assert rollback_result_second is not None

        rollback_events = PaymentEvent.objects.filter(
            payment_request=payment_request,
            payment=payment,
            event_type=PaymentEventType.PAYMENT_ROLLBACK,
        )

        assert rollback_events.count() == 1

        rollback_event = rollback_events.first()
        assert rollback_event.actor_id == customer_user.id
        assert rollback_event.transaction is not None
        assert rollback_event.transaction.purpose == TransactionPurpose.REVERSAL
        assert rollback_event.extra_data["amount"] == payment.amount
