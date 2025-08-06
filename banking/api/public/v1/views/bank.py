# banking/api/public/v1/views/bank.py

from drf_spectacular.utils import extend_schema_view, extend_schema, OpenApiParameter
from drf_spectacular.openapi import AutoSchema
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from banking.models import Bank
from banking.api.public.v1.serializers import (
    BankSerializer,
    BankDetailSerializer,
)


@extend_schema_view(
    list=extend_schema(
        summary="List all banks",
        description=(
            "Retrieve a list of all available banks in the system. "
            "This endpoint returns basic bank information including name, logo, and brand color. "
            "Useful for displaying bank options in forms or interfaces."
        ),
        tags=["Banks"],
        responses={
            200: BankSerializer(many=True),
        },
    ),
    retrieve=extend_schema(
        summary="Get bank details",
        description=(
            "Retrieve detailed information about a specific bank by its ID. "
            "This endpoint returns all bank information including creation and update timestamps. "
            "Useful for getting complete bank information for display or processing."
        ),
        tags=["Banks"],
        parameters=[
            OpenApiParameter(
                name='id',
                type=int,
                location=OpenApiParameter.PATH,
                description='Unique integer identifier for the bank'
            ),
        ],
        responses={
            200: BankDetailSerializer,
            404: {
                "description": "Bank not found",
                "examples": {
                    "application/json": {
                        "detail": "Not found."
                    }
                }
            },
        },
    ),
)
class BankViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for managing bank information.
    
    This viewset provides read-only access to bank data, allowing users to:
    - List all available banks
    - Retrieve detailed information about specific banks
    
    Banks are used as reference data for bank card management and payment processing.
    """
    queryset = Bank.objects.all()
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return BankDetailSerializer
        return BankSerializer
