# credit/tests/unit/serializers/test_credit_serializers.py

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from persiantools.jdatetime import JalaliDate

from credit.api.public.v1.serializers.credit import (
    CreditLimitSerializer,
    StatementLineSerializer,
    StatementListSerializer,
    StatementDetailSerializer,
    CloseStatementResponseSerializer,
)
from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.utils.choices import StatementLineType, StatementStatus

pytestmark = pytest.mark.django_db

User = get_user_model()


# ───────────────────────────── Helpers ───────────────────────────── #

def jalali_today_ym():
    t = JalaliDate.today()
    return t.year, t.month


def next_jalali_ym(y, m):
    """Return next Jalali year,month with simple month roll-over."""
    if m == 12:
        return y + 1, 1
    return y, m + 1


# ───────────────────────────── CreditLimitSerializer ───────────────────────────── #

class TestCreditLimitSerializer:
    def test_serialize_fields_and_types(
            self, user, active_credit_limit_factory
    ):
        """Serializer exposes declared fields and method fields have correct types."""
        limit = active_credit_limit_factory(
            user=user, is_active=True, approved_limit=1_000_000,
        )
        data = CreditLimitSerializer(limit).data

        for f in (
                "id", "user", "approved_limit", "available_limit", "is_active",
                "is_approved", "expiry_date", "created_at", "updated_at",
                "reference_code",
        ):
            assert f in data

        assert isinstance(data["available_limit"], int)
        assert isinstance(data["is_approved"], bool)

    def test_method_fields_match_model_properties(
            self, user, active_credit_limit_factory, current_statement_factory
    ):
        """available_limit & is_approved reflect model properties."""
        limit = active_credit_limit_factory(
            user=user, is_active=True, approved_limit=1_000_000
        )
        stmt = current_statement_factory(user=user, opening_balance=0)
        stmt.add_line(StatementLineType.PURCHASE, 120_000)
        stmt.refresh_from_db()

        ser = CreditLimitSerializer(limit)
        assert ser.data["available_limit"] == limit.available_limit == 880_000
        assert ser.data["is_approved"] == limit.is_approved

    def test_create_ignores_read_only_reference_code(self, user):
        """reference_code is read-only on create and must be ignored."""
        payload = {
            "user": user.pk,
            "approved_limit": 123_456,
            "is_active": False,
            "expiry_date": (timezone.localdate() + timezone.timedelta(
                days=10
            )).isoformat(),
            "reference_code": "CR-HACK",
        }
        ser = CreditLimitSerializer(data=payload)
        assert ser.is_valid(), ser.errors
        obj = ser.save()
        assert obj.reference_code != "CR-HACK"
        assert obj.user_id == user.id

    def test_update_ignores_read_only_fields(
            self, user, active_credit_limit_factory
    ):
        """Updating must not allow changing read-only fields."""
        limit = active_credit_limit_factory(
            user=user, is_active=False, approved_limit=111
        )
        payload = {"reference_code": "CR-HACK", "approved_limit": 222}
        ser = CreditLimitSerializer(instance=limit, data=payload, partial=True)
        assert ser.is_valid(), ser.errors
        obj = ser.save()
        obj.refresh_from_db()
        assert obj.approved_limit == 222
        assert obj.reference_code != "CR-HACK"


# ───────────────────────────── StatementLineSerializer ───────────────────────────── #

class TestStatementLineSerializer:
    def test_create_purchase_normalizes_sign_and_respects_read_only(
            self, user
    ):
        """PURCHASE positive in payload must be stored negative; transaction is read-only."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT,
            opening_balance=0
        )

        payload = {
            "statement": stmt.pk,
            "type": StatementLineType.PURCHASE,
            "amount": 12_345,  # +ve -> should be stored as -12_345
            "transaction": 777,  # read_only -> ignored
            "description": "buy",
        }
        ser = StatementLineSerializer(data=payload)
        assert ser.is_valid(), ser.errors
        obj = ser.save()
        obj.refresh_from_db()
        assert obj.type == StatementLineType.PURCHASE
        assert obj.amount == -12_345
        assert obj.transaction_id is None

        stmt.refresh_from_db()
        assert stmt.total_debit == 12_345
        assert stmt.total_credit == 0
        assert stmt.closing_balance == -12_345

    def test_create_payment_positive_only(self, user):
        """PAYMENT amount must be stored as positive regardless of sign in payload."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT,
            opening_balance=0
        )

        payload = {
            "statement": stmt.pk, "type": StatementLineType.PAYMENT,
            "amount": -4_000
        }
        ser = StatementLineSerializer(data=payload)
        assert ser.is_valid(), ser.errors
        line = ser.save()
        line.refresh_from_db()
        assert line.amount == 4_000

    def test_zero_amount_rejected(self, user):
        """Amount 0 must be rejected by serializer."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        ser = StatementLineSerializer(
            data={
                "statement": stmt.pk, "type": StatementLineType.PURCHASE,
                "amount": 0
            }
        )
        assert not ser.is_valid()
        assert "amount" in ser.errors

    def test_type_not_allowed_on_pending_statement(self, user):
        """On non-current statements, business rule blocks creating lines at save()."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.PENDING_PAYMENT,
            opening_balance=0
        )
        ser = StatementLineSerializer(
            data={
                "statement": stmt.pk, "type": StatementLineType.PURCHASE,
                "amount": 1000
            }
        )
        assert ser.is_valid(), ser.errors
        with pytest.raises(Exception):
            ser.save()

    def test_update_ignores_read_only_fields_partial(self, user):
        """PATCH must not modify read-only fields; only editable fields change."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        )

        snapshot = {
            "id": line.id,
            "is_voided": line.is_voided,
            "voided_at": line.voided_at,
            "void_reason": line.void_reason,
            "reverses_id": line.reverses_id,
            "created_at": line.created_at,
        }

        ser = StatementLineSerializer(
            instance=line, data={
                "description": "new", "amount": 20_000
            }, partial=True
        )
        assert ser.is_valid(), ser.errors
        obj = ser.save()
        obj.refresh_from_db()

        assert obj.description == "new"
        assert obj.amount == -20_000  # normalized for PURCHASE
        assert obj.id == snapshot["id"]
        assert obj.is_voided == snapshot["is_voided"]
        assert obj.voided_at == snapshot["voided_at"]
        assert obj.void_reason == snapshot["void_reason"]
        assert obj.reverses_id == snapshot["reverses_id"]
        assert obj.created_at == snapshot["created_at"]

    # ─── Added coverage for conditional unique (INTEREST) ─── #

    def test_create_second_interest_rejected_when_first_is_active(self, user):
        """Creating another INTEREST while one active exists must fail (non_field_errors)."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.INTEREST, amount=1_000
        )  # active

        ser = StatementLineSerializer(
            data={
                "statement": stmt.id, "type": StatementLineType.INTEREST,
                "amount": 2_000
            }
        )
        assert not ser.is_valid()
        assert "non_field_errors" in ser.errors

    def test_create_second_interest_allowed_if_first_is_voided(self, user):
        """If the existing INTEREST is voided, creating a new INTEREST is allowed."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.INTEREST, amount=1_000,
            is_voided=True
        )

        ser = StatementLineSerializer(
            data={
                "statement": stmt.id, "type": StatementLineType.INTEREST,
                "amount": 2_000
            }
        )
        assert ser.is_valid(), ser.errors

    def test_partial_update_to_interest_rejected_if_active_interest_exists(
            self, user
    ):
        """Turning a non-interest line into INTEREST via PATCH must be rejected if an active exists."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.INTEREST, amount=1_000
        )  # active
        other = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.FEE, amount=2_000
        )

        ser = StatementLineSerializer(
            instance=other, data={
                "type": StatementLineType.INTEREST
            }, partial=True
        )
        assert not ser.is_valid()
        assert "non_field_errors" in ser.errors

    def test_partial_update_to_interest_allowed_if_setting_is_voided_true(
            self, user
    ):
        """PATCH to INTEREST is allowed when is_voided=True in payload (not active)."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.INTEREST, amount=1_000
        )  # active
        other = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.FEE, amount=2_000
        )

        ser = StatementLineSerializer(
            instance=other,
            data={"type": StatementLineType.INTEREST, "is_voided": True},
            partial=True,
        )
        assert ser.is_valid(), ser.errors

    def test_partial_update_non_interest_to_non_interest_does_not_require_is_voided(
            self, user
    ):
        """PATCH between non-interest types should not require 'is_voided' and must validate cleanly."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PAYMENT, amount=10_000
        )

        ser = StatementLineSerializer(
            instance=line, data={"type": StatementLineType.FEE}, partial=True
        )
        assert ser.is_valid(), ser.errors


# ───────────────────────────── StatementListSerializer ───────────────────────────── #

class TestStatementListSerializer:
    def test_minimal_fields_and_read_only(self, user):
        """List serializer exposes minimal fields; read-only cannot be updated."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT,
            opening_balance=0, total_debit=0, total_credit=0, closing_balance=0
        )
        data = StatementListSerializer(stmt).data
        for f in (
                "id", "user", "year", "month", "reference_code", "status",
                "opening_balance", "closing_balance", "total_debit",
                "total_credit",
                "due_date", "created_at", "updated_at",
        ):
            assert f in data

        ser = StatementListSerializer(
            instance=stmt, data={"reference_code": "ST-HACK"}, partial=True
        )
        assert ser.is_valid(), ser.errors
        obj = ser.save()
        obj.refresh_from_db()
        assert obj.reference_code != "ST-HACK"


# ───────────────────────────── StatementDetailSerializer ───────────────────────────── #

class TestStatementDetailSerializer:
    def test_includes_lines_and_normalized_amounts(self, user):
        """Detail serializer includes nested lines; amounts normalized by type."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT,
            opening_balance=0
        )

        l1 = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        )
        l2 = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PAYMENT, amount=-3_000
        )
        l1.refresh_from_db()
        l2.refresh_from_db()

        data = StatementDetailSerializer(stmt).data
        assert "lines" in data and isinstance(data["lines"], list) and len(
            data["lines"]
        ) == 2

        by_id = {item["id"]: item for item in data["lines"]}
        assert by_id[l1.id]["type"] == StatementLineType.PURCHASE and \
               by_id[l1.id]["amount"] < 0
        assert by_id[l2.id]["type"] == StatementLineType.PAYMENT and \
               by_id[l2.id]["amount"] > 0

    def test_read_only_nested_lines(self, user):
        """Nested 'lines' is read-only in detail serializer."""
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT,
            opening_balance=0
        )
        ser = StatementDetailSerializer(
            instance=stmt, data={
                "lines": [
                    {"type": StatementLineType.PURCHASE, "amount": 1_000}]
            }, partial=True
        )
        assert ser.is_valid(), ser.errors
        obj = ser.save()
        assert obj.lines.count() == 0


# ───────────────────────────── CloseStatementResponseSerializer ───────────────────────────── #

class TestCloseStatementResponseSerializer:
    def test_accepts_boolean_true_false(self):
        """BooleanField accepts True/False and common truthy/falsey strings."""
        ok_payloads = [
            {"success": True}, {"success": False},
            {"success": "true"}, {"success": "false"},
            {"success": 1}, {"success": 0},
        ]
        for p in ok_payloads:
            ser = CloseStatementResponseSerializer(data=p)
            assert ser.is_valid(), ser.errors
            assert isinstance(ser.validated_data["success"], bool)

    def test_rejects_non_boolean_garbage(self):
        """Invalid non-boolean strings are rejected."""
        ser = CloseStatementResponseSerializer(data={"success": "foo"})
        assert not ser.is_valid()
        assert "success" in ser.errors


# ───────────────────────────── Patch-safety smoke tests ───────────────────────────── #

class TestStatementLineSerializerPatchedValidators:
    def test_partial_update_does_not_require_is_voided(self, user):
        """PATCH without 'is_voided' should validate cleanly (no KeyError)."""
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PAYMENT, amount=10_000
        )

        ser = StatementLineSerializer(
            instance=line, data={"type": StatementLineType.FEE}, partial=True
        )
        assert ser.is_valid(), ser.errors

    def test_partial_update_to_interest_respects_conditional_unique(
            self, user
    ):
        """PATCH to INTEREST must fail if an active INTEREST exists on the same statement."""
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user, year=today.year, month=today.month,
            status=StatementStatus.CURRENT
        )
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.INTEREST, amount=1_000
        )  # active
        other = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.FEE, amount=2_000
        )

        ser = StatementLineSerializer(
            instance=other, data={
                "type": StatementLineType.INTEREST
            }, partial=True
        )
        assert not ser.is_valid()
        assert "non_field_errors" in ser.errors

    def test_read_only_transaction_is_ignored_on_write(self, user):
        """Passing read-only 'transaction' should be ignored and not appear in validated_data."""
        today = JalaliDate.today()
        stmt = Statement.objects.create(
            user=user,
            year=today.year,
            month=today.month,
            status=StatementStatus.CURRENT
        )
        ser = StatementLineSerializer(
            data={
                "statement": stmt.id,
                "type": StatementLineType.PURCHASE,
                "amount": 12_345,
                "transaction": 999999
            }
        )
        assert ser.is_valid(), ser.errors
        assert "transaction" not in ser.validated_data


# ───────────────────────────── Extra hardening tests ───────────────────────────── #

class TestStatementLineSerializerHardening:
    def test_create_interest_cannot_bypass_uniqueness_with_is_voided_true_payload(
            self, user
    ):
        """
        Creating INTEREST with is_voided=True in payload must NOT bypass conditional uniqueness,
        because is_voided is read-only. If an active INTEREST exists, creation must be rejected.
        """
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        # existing active interest
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.INTEREST, amount=1_000
        )

        ser = StatementLineSerializer(
            data={
                "statement": stmt.id, "type": StatementLineType.INTEREST,
                "amount": 2_000, "is_voided": True
            }
        )
        assert not ser.is_valid()
        assert "non_field_errors" in ser.errors  # must still reject

    def test_patch_to_interest_with_is_voided_true_does_not_persist_is_voided_change(
            self, user
    ):
        """
        On PATCH, providing is_voided=True in payload can influence validation logic,
        but the persisted value must remain unchanged (read-only).
        """
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        # No other interest lines; we convert a FEE line to INTEREST with is_voided=True in payload.
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.FEE, amount=2_000
        )
        original_is_voided = line.is_voided  # usually False by default

        ser = StatementLineSerializer(
            instance=line,
            data={"type": StatementLineType.INTEREST, "is_voided": True},
            partial=True,
        )
        assert ser.is_valid(), ser.errors
        obj = ser.save()
        obj.refresh_from_db()

        # type changed to INTEREST
        assert obj.type == StatementLineType.INTEREST
        # is_voided must remain the original value (read-only)
        assert obj.is_voided == original_is_voided

    def test_patch_change_statement_rejected_if_target_has_active_interest(
            self, user
    ):
        """
        Moving a line to another statement which already has an active INTEREST must be rejected.
        Destination statement must be a different year/month to satisfy (user,year,month) DB unique.
        """
        y, m = jalali_today_ym()
        y2, m2 = next_jalali_ym(y, m)

        stmt_src = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        stmt_dst = Statement.objects.create(
            user=user, year=y2, month=m2, status=StatementStatus.CURRENT
        )

        # target has active interest
        StatementLine.objects.create(
            statement=stmt_dst, type=StatementLineType.INTEREST, amount=1_000
        )

        # line in source statement
        line = StatementLine.objects.create(
            statement=stmt_src, type=StatementLineType.FEE, amount=2_000
        )

        ser = StatementLineSerializer(
            instance=line,
            data={
                "statement": stmt_dst.id, "type": StatementLineType.INTEREST
            },
            partial=True,
        )
        assert not ser.is_valid()
        assert "non_field_errors" in ser.errors

    def test_patch_change_statement_allowed_if_target_has_no_active_interest(
            self, user
    ):
        """
        Moving a line to another statement without an active INTEREST should be allowed.
        Destination statement must be a different year/month to satisfy (user,year,month) DB unique.
        """
        y, m = jalali_today_ym()
        y2, m2 = next_jalali_ym(y, m)

        stmt_src = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        stmt_dst = Statement.objects.create(
            user=user, year=y2, month=m2, status=StatementStatus.CURRENT
        )

        line = StatementLine.objects.create(
            statement=stmt_src, type=StatementLineType.FEE, amount=2_000
        )

        ser = StatementLineSerializer(
            instance=line,
            data={
                "statement": stmt_dst.id, "type": StatementLineType.INTEREST
            },
            partial=True,
        )
        assert ser.is_valid(), ser.errors
        obj = ser.save()
        obj.refresh_from_db()
        assert obj.statement_id == stmt_dst.id
        assert obj.type == StatementLineType.INTEREST

    def test_patch_to_interest_with_string_truthy_is_handled_for_validation_but_not_persisted(
            self, user
    ):
        """
        Passing 'is_voided' as 'true'/'false' strings should only affect validation logic (skip/enable unique),
        but must not change persisted is_voided (read-only).
        """
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.FEE, amount=2_000
        )
        original_is_voided = line.is_voided

        ser = StatementLineSerializer(
            instance=line, data={
                "type": StatementLineType.INTEREST, "is_voided": "true"
            }, partial=True
        )
        assert ser.is_valid(), ser.errors
        saved = ser.save()
        saved.refresh_from_db()
        assert saved.is_voided == original_is_voided

    def test_partial_update_to_interest_rejected_when_is_voided_false_explicit(
            self, user
    ):
        """
        Even if payload explicitly sets is_voided=False, PATCH to INTEREST must be rejected
        when an active INTEREST already exists on the same statement.
        """
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        # existing active interest
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.INTEREST, amount=1_000
        )

        # another non-interest line we try to turn into INTEREST with is_voided=False (explicit)
        other = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.FEE, amount=2_000
        )

        ser = StatementLineSerializer(
            instance=other,
            data={"type": StatementLineType.INTEREST, "is_voided": False},
            partial=True,
        )
        assert not ser.is_valid()
        assert "non_field_errors" in ser.errors

    def test_patch_attempt_to_set_read_only_transaction_is_ignored_and_not_persisted(
            self, user
    ):
        """
        On PATCH, providing 'transaction' must be ignored:
        - not present in validated_data,
        - not persisted to DB (transaction_id remains unchanged).
        """
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        line = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        )
        original_tx_id = line.transaction_id  # usually None

        ser = StatementLineSerializer(
            instance=line,
            data={"transaction": 123456, "description": "patched desc"},
            partial=True,
        )
        assert ser.is_valid(), ser.errors
        # transaction should not appear in validated_data
        assert "transaction" not in ser.validated_data

        saved = ser.save()
        saved.refresh_from_db()
        assert saved.transaction_id == original_tx_id
        assert saved.description == "patched desc"

    def test_patch_change_type_payment_to_purchase_normalizes_amount(
            self, user
    ):
        """
        Changing type from PAYMENT -> PURCHASE on PATCH must re-normalize amount:
        - PAYMENT is stored positive.
        - PURCHASE is stored negative.
        """
        y, m = jalali_today_ym()
        stmt = Statement.objects.create(
            user=user, year=y, month=m, status=StatementStatus.CURRENT
        )
        # start with PAYMENT; even if created with negative, model/logic should store positive
        payment = StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PAYMENT, amount=-4_000
        )
        payment.refresh_from_db()
        assert payment.amount == 4_000  # sanity

        # now PATCH to PURCHASE with amount=2000 → must store as -2000
        ser = StatementLineSerializer(
            instance=payment,
            data={"type": StatementLineType.PURCHASE, "amount": 2_000},
            partial=True,
        )
        assert ser.is_valid(), ser.errors
        obj = ser.save()
        obj.refresh_from_db()
        assert obj.type == StatementLineType.PURCHASE
        assert obj.amount == -2_000
