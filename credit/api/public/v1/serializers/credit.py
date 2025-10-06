# credit/api/public/v1/serializers/credit.py

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db.models.constants import LOOKUP_SEP
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from credit.models.credit_limit import CreditLimit
from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.utils.choices import StatementLineType

User = get_user_model()


# ───────────────────────────── CreditLimit ───────────────────────────── #

class CreditLimitSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    available_limit = serializers.SerializerMethodField()
    is_approved = serializers.SerializerMethodField()

    class Meta:
        model = CreditLimit
        fields = [
            "id",
            "user",
            "approved_limit",
            "available_limit",
            "is_active",
            "is_approved",
            "expiry_date",
            "created_at",
            "updated_at",
            "reference_code",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "reference_code"]

    @extend_schema_field(serializers.IntegerField)
    def get_available_limit(self, obj) -> int:
        return obj.available_limit

    @extend_schema_field(serializers.BooleanField)
    def get_is_approved(self, obj) -> bool:
        return obj.is_approved


# ───────────────────── Helpers: conditional unique (PATCH-safe) ───────────────────── #

def extract_condition_field_names_from_q(condition: Q) -> set[str]:
    """
    Return the set of model field names referenced in a Q() tree (without lookups).
    Example: ('is_voided', False) → 'is_voided', ('type__in', [...]) → 'type'.
    """
    names: set[str] = set()

    def walk(node: Q) -> None:
        for child in getattr(node, "children", []):
            if isinstance(child, Q):
                walk(child)
            else:
                key = child[0]
                names.add(key.split(LOOKUP_SEP, 1)[0])

    if isinstance(condition, Q):
        walk(condition)
    return names


def _condition_matches_q(condition: Q, values: dict) -> bool:
    """
    Minimal evaluator to check if a Q condition holds for the current input values.
    Supports equality (field) and __in lookup; AND/OR via Q; negation via ~Q.
    This is enough for our case: Q(is_voided=False, type=INTEREST).
    """
    if not isinstance(condition, Q):
        return True

    def eval_node(node: Q) -> bool:
        result = True  # for AND
        for child in node.children:
            if isinstance(child, Q):
                child_res = eval_node(child)
            else:
                key, expected = child
                field, lookup = (key.split(LOOKUP_SEP, 1) + ["exact"])[:2]
                actual = values.get(field, None)

                if lookup == "exact":
                    child_res = (actual == expected)
                elif lookup == "in":
                    try:
                        child_res = (actual in expected)
                    except TypeError:
                        child_res = False
                else:
                    # unsupported lookup → be conservative (treat as False)
                    child_res = False

            if node.connector == Q.OR:
                # For OR, lazy accumulate (any True)
                result = result or child_res
            else:
                # For AND, all must be True
                result = result and child_res

        return not result if node.negated else result

    return eval_node(condition)


class PartialSafeConditionalUniqueTogetherValidator(UniqueTogetherValidator):
    """
    Wrapper around DRF's UniqueTogetherValidator (with condition) that is safe for PATCH:
    - On partial update, fills missing required/condition fields from the instance.
    - On create, fills remaining condition fields from model defaults (or None).
    """

    @classmethod
    def from_existing(cls, original: UniqueTogetherValidator, model):
        # Constructor signature varies across DRF versions; avoid unexpected kwargs.
        wrapped = cls(
            queryset=original.queryset,
            fields=tuple(original.fields),
            message=getattr(original, "message", None),
        )
        # Set condition after init so we’re compatible with older DRF signatures.
        wrapped.condition = getattr(original, "condition", None)

        # Prefer DRF-provided condition_fields; otherwise derive them from the Q condition.
        condition_fields = getattr(original, "condition_fields", None)
        if not condition_fields and getattr(wrapped, "condition", None):
            condition_fields = extract_condition_field_names_from_q(
                wrapped.condition
            )

        wrapped.condition_fields = list(condition_fields or [])
        wrapped.serializer_field_names = getattr(
            original, "serializer_field_names", wrapped.fields
        )
        wrapped.child = getattr(original, "child", None)
        wrapped._model = model
        return wrapped

    def __call__(self, attrs, serializer):
        filled = dict(attrs)
        needed = set(self.fields) | set(self.condition_fields or [])

        # 1) برای فیلدهای شرطی، ابتدا از initial_data بخوان (حتی اگر read_only باشند)
        initial = getattr(serializer, "initial_data", {}) or {}
        for name in (self.condition_fields or []):
            if name not in filled and name in initial:
                filled[name] = initial[name]

        # 2) در PATCH، اگر هنوز چیزی کم است از instance پر کن
        instance = getattr(serializer, "instance", None)
        if getattr(serializer, "partial", False) and instance is not None:
            for name in needed:
                if name not in filled:
                    filled[name] = getattr(instance, name, None)

        # 3) اگر باز هم در فیلدهای شرطی چیزی کم بود، از default مدل پر کن (CREATE)
        for name in (self.condition_fields or []):
            if name in filled:
                continue
            try:
                mf = self._model._meta.get_field(name)
                default = mf.default() if callable(mf.default) else mf.default
            except Exception:
                default = None
            filled[name] = default

        # 4) اگر شرط روی ورودی فعلی برقرار نیست، چک یونیک را skip کن
        if getattr(self, "condition", None) and not _condition_matches_q(
                self.condition, filled
        ):
            return None

        return super().__call__(filled, serializer)


# ───────────────────────────── Statement / Lines ───────────────────────────── #

class StatementLineSerializer(serializers.ModelSerializer):
    """
    - Rejects amount == 0 (fail-fast).
    - Read-only fields are enforced.
    - Ensures at most one active (is_voided=False) INTEREST line per statement.
    - Wraps DRF's conditional UniqueTogetherValidator to be PATCH-safe.
    """
    transaction = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = StatementLine
        fields = [
            "id",
            "statement",
            "type",
            "amount",
            "transaction",
            "created_at",
            "description",
            "is_voided",
            "voided_at",
            "void_reason",
            "reverses",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "is_voided",
            "voided_at",
            "void_reason",
            "reverses",
        ]

    # Reject zero amount early
    def validate_amount(self, value: int) -> int:
        if value == 0:
            raise serializers.ValidationError("Amount must be non-zero.")
        return value

    # Make conditional unique validators PATCH-safe
    def get_validators(self):
        base = super().get_validators()
        patched = []
        for v in base:
            if isinstance(v, UniqueTogetherValidator) and getattr(
                    v, "condition", None
            ):
                patched.append(
                    PartialSafeConditionalUniqueTogetherValidator.from_existing(
                        v, model=self.Meta.model
                    )
                )
            else:
                patched.append(v)
        return patched

    # Single active INTEREST guard (serializer-level, for both create & partial update)
    def validate(self, attrs):
        attrs = super().validate(attrs)

        instance = getattr(self, "instance", None)
        statement = attrs.get("statement") or (
            instance.statement if instance else None)
        line_type = attrs.get("type") or (instance.type if instance else None)

        # Resolve is_voided with priority: attrs -> initial_data -> instance -> model default
        if "is_voided" in attrs:
            is_voided = attrs["is_voided"]
        else:
            initial = getattr(self, "initial_data", {}) or {}
            if "is_voided" in initial:
                is_voided = initial["is_voided"]
            elif instance is not None:
                is_voided = instance.is_voided
            else:
                mf = StatementLine._meta.get_field("is_voided")
                is_voided = mf.default() if callable(
                    mf.default
                ) else mf.default

        if statement and line_type == StatementLineType.INTEREST and is_voided is False:
            qs = StatementLine.objects.filter(
                statement=statement,
                type=StatementLineType.INTEREST,
                is_voided=False,
            )
            if instance:
                qs = qs.exclude(pk=instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {
                        "non_field_errors": [
                            "Only one active INTEREST line is allowed per statement."]
                    }
                )

        return attrs


class StatementListSerializer(serializers.ModelSerializer):
    """Minimal list view of statements (no nested lines)."""
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Statement
        fields = [
            "id",
            "user",
            "year",
            "month",
            "reference_code",
            "status",
            "opening_balance",
            "closing_balance",
            "total_debit",
            "total_credit",
            "due_date",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "reference_code", "created_at", "updated_at"]


class StatementDetailSerializer(serializers.ModelSerializer):
    """Detail view with read-only nested lines."""
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    lines = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Statement
        fields = [
            "id",
            "user",
            "year",
            "month",
            "reference_code",
            "opening_balance",
            "closing_balance",
            "total_debit",
            "total_credit",
            "due_date",
            "paid_at",
            "closed_at",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reference_code",
            "created_at",
            "updated_at",
            "lines"
        ]

    @extend_schema_field(StatementLineSerializer(many=True))
    def get_lines(self, obj):
        return StatementLineSerializer(obj.lines.all(), many=True).data


class CloseStatementResponseSerializer(serializers.Serializer):
    """Simple success flag for 'close statement' action."""
    success = serializers.BooleanField(
        help_text="Whether the current statement was successfully closed"
    )
