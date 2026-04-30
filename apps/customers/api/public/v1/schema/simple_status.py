# apps/customers/api/public/v1/schema/simple_status.py

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers


class SimpleStatusResponseSerializer(serializers.Serializer):
    active_users = serializers.IntegerField(help_text="Number of active users.")
    contracted_merchants = serializers.IntegerField(
        help_text="Number of contracted merchants."
    )
    customer_satisfaction = serializers.FloatField(
        help_text="Customer satisfaction percentage."
    )


simple_status_schema = extend_schema(
    tags=["Public · Platform"],
    summary="Get public platform stats",
    description=(
        "Return public platform statistics including active users, contracted "
        "merchants, and customer satisfaction percentage."
    ),
    responses={
        200: OpenApiResponse(
            response=SimpleStatusResponseSerializer,
            description="Public platform stats returned successfully.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "active_users": 1200,
                        "contracted_merchants": 85,
                        "customer_satisfaction": 92.5,
                    },
                )
            ],
        )
    },
)
