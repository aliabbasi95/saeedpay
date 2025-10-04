# credit/api/public/v1/schema/credit_limit.py

from drf_spectacular.utils import extend_schema, extend_schema_view

from credit.api.public.v1.serializers.credit import CreditLimitSerializer

credit_limit_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=["Credit · Limits"],
        summary="List user's credit limits (unpaginated)",
        responses={200: CreditLimitSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["Credit · Limits"],
        summary="Retrieve a credit limit",
        responses={200: CreditLimitSerializer},
    ),
)
