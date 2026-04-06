# wallets/api/payment_responses.py

from rest_framework import status
from rest_framework.response import Response

from wallets.utils.choices import PaymentFlowType, PaymentStatus


def _get_payment_request_status(payment_request):
    if not payment_request:
        return None
    return getattr(payment_request, "status", None)


def _get_payment_status(payment):
    if not payment:
        return None
    return getattr(payment, "status", None)


def _get_payment_reference_code(payment_request):
    if not payment_request:
        return None
    return getattr(payment_request, "reference_code", None)


def _get_transaction_reference_code(payment):
    if not payment:
        return None
    return getattr(payment, "operation_reference_code", None) or ""


def _get_return_url(payment_request):
    if not payment_request:
        return None
    return getattr(payment_request, "return_url", None)


def _get_amount(payment_request):
    if not payment_request:
        return None
    return getattr(payment_request, "amount", None)


def _get_merchant_confirmation_required(payment_request):
    if not payment_request:
        return None
    return payment_request.flow_type == PaymentFlowType.ONLINE


def _get_next_action(payment):
    if not payment:
        return None

    if payment.status == PaymentStatus.AWAITING_MERCHANT_CONFIRMATION:
        return "waiting_for_store_confirmation"

    return "none"


def build_payment_response_payload(
        *,
        detail,
        code,
        payment_request=None,
        payment=None,
        transaction_reference_code=None,
        next_action=None,
        merchant_confirmation_required=None,
        extra=None,
):
    payload = {
        "detail": detail,
        "code": code,
        "payment_reference_code": _get_payment_reference_code(payment_request),
        "payment_request_status": _get_payment_request_status(payment_request),
        "payment_status": _get_payment_status(payment),
        "transaction_reference_code": (
            _get_transaction_reference_code(payment)
            if transaction_reference_code is None
            else transaction_reference_code
        ),
        "next_action": (
            _get_next_action(payment)
            if next_action is None
            else next_action
        ),
        "merchant_confirmation_required": (
            _get_merchant_confirmation_required(payment_request)
            if merchant_confirmation_required is None
            else merchant_confirmation_required
        ),
        "return_url": _get_return_url(payment_request),
        "amount": _get_amount(payment_request),
    }

    if extra:
        payload.update(extra)

    return payload


def payment_success_response(
        *,
        detail,
        code,
        payment_request=None,
        payment=None,
        http_status=status.HTTP_200_OK,
        transaction_reference_code=None,
        next_action=None,
        merchant_confirmation_required=None,
        extra=None,
):
    payload = build_payment_response_payload(
        detail=detail,
        code=code,
        payment_request=payment_request,
        payment=payment,
        transaction_reference_code=transaction_reference_code,
        next_action=next_action,
        merchant_confirmation_required=merchant_confirmation_required,
        extra=extra,
    )
    return Response(payload, status=http_status)


def payment_error_response(
        *,
        detail,
        code,
        http_status,
        payment_request=None,
        payment=None,
        transaction_reference_code=None,
        next_action=None,
        merchant_confirmation_required=None,
        extra=None,
):
    payload = build_payment_response_payload(
        detail=detail,
        code=code,
        payment_request=payment_request,
        payment=payment,
        transaction_reference_code=transaction_reference_code,
        next_action=next_action,
        merchant_confirmation_required=merchant_confirmation_required,
        extra=extra,
    )
    return Response(payload, status=http_status)
