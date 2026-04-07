# wallets/services/payment_event.py

from wallets.models import PaymentEvent


def create_payment_event(
        *,
        payment_request,
        event_type,
        payment=None,
        transaction=None,
        actor=None,
        from_status=None,
        to_status=None,
        description="",
        extra_data=None,
):
    return PaymentEvent.objects.create(
        payment_request=payment_request,
        payment=payment,
        transaction=transaction,
        actor=actor,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        description=description,
        extra_data=extra_data or {},
    )
