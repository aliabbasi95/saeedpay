# credit/api/public/v1/views/statement_line.py
# Read-only ViewSet for user's statement lines (with optional statement_id filter).

from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import mixins, viewsets

from credit.api.public.v1.serializers.credit import StatementLineSerializer
from credit.models.statement_line import StatementLine


@extend_schema(
    tags=["Statement Lines"],
    summary="List/Retrieve user's statement lines",
    description="Optionally filter by ?statement_id=...",
    parameters=[
        OpenApiParameter(
            name="statement_id",
            location=OpenApiParameter.QUERY,
            required=False,
            type=OpenApiTypes.INT,
            description="Filter by a specific statement id",
        )
    ],
)
class StatementLineViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet
):
    """
    list:     Paginated list of statement lines; optional filter by statement_id.
    retrieve: Single line owned by the user (via parent statement).
    """
    serializer_class = StatementLineSerializer
    lookup_field = "pk"

    def get_queryset(self):
        qs = (
            StatementLine.objects
            .select_related("statement", "transaction")
            .only(
                "id", "statement_id", "type", "amount",
                "transaction_id", "description",
                "is_voided", "voided_at", "void_reason", "reverses_id",
                "created_at",
                "statement__user_id",
            )
            .filter(statement__user=self.request.user)
            .order_by("-created_at")
        )
        sid = self.request.query_params.get("statement_id")
        if sid is not None:
            try:
                sid = int(sid)
            except (TypeError, ValueError):
                return StatementLine.objects.none()
            qs = qs.filter(statement_id=sid)
        return qs
