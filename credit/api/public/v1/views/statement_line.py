# credit/api/public/v1/views/statement_line.py

from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from credit.api.public.v1.schema import statement_line_viewset_schema
from credit.api.public.v1.serializers import StatementLineSerializer
from credit.models.statement_line import StatementLine
from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin


@statement_line_viewset_schema
class StatementLineViewSet(
    ScopedThrottleByActionMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    list:     Paginated list of statement lines; optional filter by statement_id.
    retrieve: Single line owned by the user (via parent statement).
    """
    permission_classes = [IsAuthenticated]
    serializer_class = StatementLineSerializer
    lookup_field = "pk"

    throttle_scope_map = {
        "default": "credit-statement-lines-read",
        "list": "credit-statement-lines-read",
        "retrieve": "credit-statement-lines-read",
    }

    def get_queryset(self):
        qs = (
            StatementLine.objects
            .select_related("statement", "transaction")
            .only(
                "id",
                "statement_id",
                "type",
                "amount",
                "transaction_id",
                "description",
                "is_voided",
                "voided_at",
                "void_reason",
                "reverses_id",
                "created_at",
                "statement__user_id",
            )
            .filter(statement__user=self.request.user)
            .order_by("-created_at")
        )
        sid = self.request.query_params.get("statement_id")
        if sid is not None:
            try:
                qs = qs.filter(statement_id=int(sid))
            except (TypeError, ValueError):
                # Return empty if invalid filter value
                return StatementLine.objects.none()
        return qs
