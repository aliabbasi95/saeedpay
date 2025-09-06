# credit/tests/api/test_credit_views.py

import json
from unittest.mock import Mock

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

import credit.api.public.v1.views.credit as views_mod
from credit.models.statement import Statement
from credit.models.statement_line import StatementLine
from credit.utils.choices import StatementStatus, StatementLineType
from wallets.utils.choices import TransactionStatus, WalletKind

pytestmark = pytest.mark.django_db


# ----------------------------- Helpers ----------------------------- #

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


def _as_json(resp):
    try:
        return json.loads(resp.content.decode())
    except Exception:
        return {}


# ------------------------- CreditLimit Views ------------------------ #

class TestCreditLimitListView:
    url_name = "credit_limit_list"

    def test_requires_auth(self, api_client):
        url = reverse(self.url_name)
        resp = api_client.get(url)
        # With SessionAuthentication (no CSRF), unauthenticated requests are 401
        assert resp.status_code == 401

    def test_lists_only_current_user_limits_in_desc_order(
            self, auth_client, user, user_factory, active_credit_limit_factory
    ):
        """
        Only current user's limits should be listed, ordered by -created_at.
        We create one inactive (older) and one active (newer) for the same user
        to avoid the 'only one active per user' uniqueness violation.
        """
        older = active_credit_limit_factory(
            user=user, approved_limit=100, is_active=False
        )
        newer = active_credit_limit_factory(
            user=user, approved_limit=200, is_active=True
        )
        other_user = user_factory()
        active_credit_limit_factory(user=other_user, is_active=True)

        url = reverse(self.url_name)
        resp = auth_client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        # NOTE: CreditLimitListView is not paginated; response is a flat list.
        assert isinstance(data, list)
        assert len(data) == 2

        ids = [item["id"] for item in data]
        assert ids == [newer.id, older.id]
        assert "available_limit" in data[0] and "is_approved" in data[0]


class TestCreditLimitDetailView:
    url_name = "credit_limit_detail"

    def test_requires_auth(
            self, api_client, active_credit_limit_factory, user
    ):
        limit = active_credit_limit_factory(user=user)
        url = reverse(self.url_name, args=[limit.id])
        resp = api_client.get(url)
        assert resp.status_code == 401

    def test_own_object_ok_other_user_404(
            self, auth_client, user, user_factory, active_credit_limit_factory
    ):
        mine = active_credit_limit_factory(user=user)
        other_user = user_factory()
        other = active_credit_limit_factory(user=other_user)

        url = reverse(self.url_name, args=[mine.id])
        resp = auth_client.get(url)
        assert resp.status_code == 200
        assert resp.json()["id"] == mine.id

        url2 = reverse(self.url_name, args=[other.id])
        resp2 = auth_client.get(url2)
        assert resp2.status_code == 404


# --------------------------- Statement Views (paginated) ------------ #

class TestStatementListView:
    url_name = "statement_list"

    def test_requires_auth(self, api_client):
        url = reverse(self.url_name)
        resp = api_client.get(url)
        assert resp.status_code == 401

    def test_lists_only_current_user_paginated_and_ordered(
            self, auth_client, user, user_factory, settings
    ):
        """
        Ensures pagination works and results are ordered by (-year, -month, -created_at).
        Also avoids violating the unique (user, year, month) constraint.
        """
        PAGE_SIZE = settings.REST_FRAMEWORK["PAGE_SIZE"]

        # Build 12 unique (year, month) pairs for the same user: 1404/1..12, 1405/1..
        base_year, base_month = 1404, 1
        statements = []
        for i in range(25):
            y = base_year + ((base_month - 1 + i) // 12)
            m = ((base_month - 1 + i) % 12) + 1
            statements.append(
                Statement.objects.create(
                    user=user, year=y, month=m, status=StatementStatus.CURRENT
                )
            )

        # Another user's statements shouldn't appear
        other = user_factory()
        for i in range(3):
            y = 1404 + (i // 12)
            m = (i % 12) + 1
            Statement.objects.create(
                user=other, year=y, month=m, status=StatementStatus.CURRENT
            )

        url = reverse(self.url_name)
        resp = auth_client.get(url, {"page": 1})
        assert resp.status_code == 200

        data = resp.json()
        # PageNumberPagination returns dict with 'count', 'results', ...
        assert isinstance(data, dict) and "results" in data
        results = data["results"]

        # Page size respected
        assert len(results) == PAGE_SIZE

        # Verify ordering: last created pair (largest year/month) first
        # We generated ascending; response must be descending.
        returned_pairs = [(item["year"], item["month"]) for item in results]
        expected_pairs_desc = sorted(
            [(s.year, s.month) for s in statements],
            key=lambda t: (t[0], t[1]),
            reverse=True,
        )[:PAGE_SIZE]
        assert returned_pairs == expected_pairs_desc

    def test_respects_page_size_and_max_cap(self, auth_client, user, settings):
        """
        If client requests a page_size greater than MAX_PAGE_SIZE, we clamp it.
        """
        # Match values you set in StandardResultsSetPagination
        MAX_PAGE_SIZE = 100

        # Create 60 unique statements for the same user
        base_year, base_month = 1404, 1
        for i in range(120):
            y = base_year + ((base_month - 1 + i) // 12)
            m = ((base_month - 1 + i) % 12) + 1
            Statement.objects.create(
                user=user, year=y, month=m, status=StatementStatus.CURRENT
            )

        url = reverse(self.url_name)
        # Ask for larger than MAX_PAGE_SIZE; expect it to clamp to MAX_PAGE_SIZE
        resp = auth_client.get(
            url, {"page": 1, "page_size": MAX_PAGE_SIZE + 100}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == MAX_PAGE_SIZE


class TestStatementDetailView:
    url_name = "statement_detail"

    def test_requires_auth(self, api_client, user):
        stmt = Statement.objects.create(
            user=user, year=1404, month=1, status=StatementStatus.CURRENT
        )
        url = reverse(self.url_name, args=[stmt.id])
        resp = api_client.get(url)
        assert resp.status_code == 401

    def test_own_ok_other_404_and_lines_prefetched(
            self, auth_client, user, user_factory
    ):
        stmt = Statement.objects.create(
            user=user, year=1404, month=1, status=StatementStatus.CURRENT
        )
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=10_000
        )
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PAYMENT, amount=3_000
        )
        other = user_factory()
        stmt_other = Statement.objects.create(
            user=other, year=1404, month=1, status=StatementStatus.CURRENT
        )

        url = reverse(self.url_name, args=[stmt.id])
        resp = auth_client.get(url)
        assert resp.status_code == 200
        payload = resp.json()
        assert isinstance(payload.get("lines"), list) and len(
            payload["lines"]
        ) == 2

        url2 = reverse(self.url_name, args=[stmt_other.id])
        resp2 = auth_client.get(url2)
        assert resp2.status_code == 404


# ------------------------- StatementLine List (paginated) ---------- #

class TestStatementLineListView:
    url_name = "statement_line_list"

    def test_requires_auth(self, api_client):
        url = reverse(self.url_name)
        resp = api_client.get(url)
        assert resp.status_code == 401

    def test_lists_only_users_lines_paginated_and_desc_order(
            self, auth_client, user, user_factory
    ):
        stmt = Statement.objects.create(
            user=user, year=1404, month=1, status=StatementStatus.CURRENT
        )
        # Make 30 lines for 'user'
        made = []
        for i in range(30):
            made.append(
                StatementLine.objects.create(
                    statement=stmt,
                    type=StatementLineType.PURCHASE if i % 2 == 0 else StatementLineType.PAYMENT,
                    amount=1000 + i,
                )
            )
        # Others' lines must be excluded
        other_user = user_factory()
        stmt_other = Statement.objects.create(
            user=other_user, year=1404, month=1, status=StatementStatus.CURRENT
        )
        StatementLine.objects.create(
            statement=stmt_other, type=StatementLineType.FEE, amount=999
        )

        url = reverse(self.url_name)

        # page_size = 10 (override)
        resp = auth_client.get(url, {"page_size": 10})
        assert resp.status_code == 200
        payload = resp.json()
        assert set(payload.keys()) == {"count", "next", "previous", "results"}
        assert payload["count"] == 30
        assert len(payload["results"]) == 10

        expected_ids_p1 = [obj.id for obj in reversed(made)][0:10]
        returned_ids_p1 = [item["id"] for item in payload["results"]]
        assert returned_ids_p1 == expected_ids_p1

        # page=2
        resp2 = auth_client.get(url, {"page_size": 10, "page": 2})
        assert resp2.status_code == 200
        payload2 = resp2.json()
        assert len(payload2["results"]) == 10
        expected_ids_p2 = [obj.id for obj in reversed(made)][10:20]
        returned_ids_p2 = [item["id"] for item in payload2["results"]]
        assert returned_ids_p2 == expected_ids_p2

        # page=3 (last 10)
        resp3 = auth_client.get(url, {"page_size": 10, "page": 3})
        assert resp3.status_code == 200
        payload3 = resp3.json()
        assert len(payload3["results"]) == 10
        expected_ids_p3 = [obj.id for obj in reversed(made)][20:30]
        returned_ids_p3 = [item["id"] for item in payload3["results"]]
        assert returned_ids_p3 == expected_ids_p3

    def test_can_filter_by_statement_id_with_pagination(
            self, auth_client, user
    ):
        s1 = Statement.objects.create(
            user=user, year=1404, month=1, status=StatementStatus.CURRENT
        )
        s2 = Statement.objects.create(
            user=user, year=1404, month=2, status=StatementStatus.CURRENT
        )
        # 15 lines in s1, 5 lines in s2
        for i in range(15):
            StatementLine.objects.create(
                statement=s1, type=StatementLineType.PURCHASE, amount=100 + i
            )
        for i in range(5):
            StatementLine.objects.create(
                statement=s2, type=StatementLineType.PAYMENT, amount=200 + i
            )

        url = reverse(self.url_name)

        # filter by s2 + page_size=3 => first page 3 items
        r = auth_client.get(url, {"statement_id": s2.id, "page_size": 3})
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 5
        assert len(data["results"]) == 3
        # second page => remaining 2
        r2 = auth_client.get(
            url, {"statement_id": s2.id, "page_size": 3, "page": 2}
        )
        assert r2.status_code == 200
        data2 = r2.json()
        assert data2["count"] == 5
        assert len(data2["results"]) == 2

    def test_filter_does_not_leak_others_lines_even_with_page_params(
            self, auth_client, user, user_factory, settings
    ):
        """
        Filtering by a statement_id owned by another user must not leak lines.
        With pagination params, page=1 should return 200 and empty results.
        """
        # My statement (no lines needed here)
        mine = Statement.objects.create(
            user=user, year=1404, month=1, status=StatementStatus.CURRENT
        )

        # Other user's statement + a line in it
        other_user = user_factory()
        others_stmt = Statement.objects.create(
            user=other_user, year=1404, month=2, status=StatementStatus.CURRENT
        )
        StatementLine.objects.create(
            statement=others_stmt, type=StatementLineType.PURCHASE, amount=999
        )

        url = reverse(self.url_name)
        # page=1 guarantees 200 with empty results instead of NotFound(404).
        resp = auth_client.get(
            url, {"statement_id": others_stmt.id, "page": 1, "page_size": 5}
        )
        assert resp.status_code == 200

        payload = resp.json()
        assert isinstance(payload, dict) and "results" in payload
        assert payload["results"] == []
        assert payload.get("count", 0) == 0


# ----------------------------- AddPurchase ------------------------- #

class TestAddPurchaseView:
    url_name = "add_purchase"

    def _mock_transaction(
            self,
            user_id,
            *,
            status=TransactionStatus.SUCCESS,
            from_wallet_kind=WalletKind.CREDIT,
            belongs=True,
    ):
        trx = Mock()
        trx.id = 123
        trx.status = status
        from_wallet = Mock()
        from_wallet.kind = from_wallet_kind
        from_wallet.user_id = user_id if belongs else 999_999
        trx.from_wallet = from_wallet
        to_wallet = Mock()
        to_wallet.user_id = 777
        trx.to_wallet = to_wallet
        return trx

    def test_requires_auth(self, api_client):
        url = reverse(self.url_name)
        resp = api_client.post(url, {})
        assert resp.status_code == 401

    def test_missing_transaction_id_returns_400(self, auth_client):
        url = reverse(self.url_name)
        resp = auth_client.post(url, {}, format="json")
        assert resp.status_code == 400
        assert _as_json(resp).get("error") == "transaction_id is required"

    def test_forbidden_when_transaction_not_users_from_wallet(
            self, auth_client, user, mocker
    ):
        trx = self._mock_transaction(user.id, belongs=False)
        mocker.patch.object(views_mod, "get_object_or_404", return_value=trx)

        url = reverse(self.url_name)
        resp = auth_client.post(url, {"transaction_id": 123}, format="json")
        assert resp.status_code == 403
        assert _as_json(resp).get(
            "error"
        ) == "transaction does not belong to user"

    def test_bad_request_when_wallet_not_credit(
            self, auth_client, user, mocker
    ):
        trx = self._mock_transaction(user.id, from_wallet_kind="NON_CREDIT")
        mocker.patch.object(views_mod, "get_object_or_404", return_value=trx)

        url = reverse(self.url_name)
        resp = auth_client.post(url, {"transaction_id": 123}, format="json")
        assert resp.status_code == 400
        assert _as_json(resp).get(
            "error"
        ) == "transaction is not from a credit wallet"

    def test_bad_request_when_transaction_not_success(
            self, auth_client, user, mocker
    ):
        trx = self._mock_transaction(user.id, status=TransactionStatus.PENDING)
        mocker.patch.object(views_mod, "get_object_or_404", return_value=trx)

        url = reverse(self.url_name)
        resp = auth_client.post(url, {"transaction_id": 123}, format="json")
        assert resp.status_code == 400
        assert _as_json(resp).get("error") == "transaction must be SUCCESS"

    def test_success_calls_usecase_and_returns_201(
            self, auth_client, user, mocker
    ):
        trx = self._mock_transaction(user.id)
        mocker.patch.object(views_mod, "get_object_or_404", return_value=trx)
        uc_mock = mocker.patch.object(
            views_mod.StatementUseCases,
            "record_successful_purchase_from_transaction",
        )

        url = reverse(self.url_name)
        resp = auth_client.post(
            url,
            {"transaction_id": 123, "description": "My Purchase"},
            format="json",
        )
        assert resp.status_code == 201
        assert _as_json(resp).get("success") is True
        uc_mock.assert_called_once_with(
            transaction_id=trx.id, description="My Purchase"
        )

    def test_usecase_exception_returns_400(self, auth_client, user, mocker):
        trx = self._mock_transaction(user.id)
        mocker.patch.object(views_mod, "get_object_or_404", return_value=trx)

        def _raise(*args, **kwargs):
            raise RuntimeError("boom")

        mocker.patch.object(
            views_mod.StatementUseCases,
            "record_successful_purchase_from_transaction",
            side_effect=_raise,
        )

        url = reverse(self.url_name)
        resp = auth_client.post(url, {"transaction_id": 123}, format="json")
        assert resp.status_code == 400
        assert "error" in _as_json(resp)


# ------------------------------ AddPayment ------------------------- #

class TestAddPaymentView:
    url_name = "add_payment"

    def _mock_transaction(
            self, *, user_id_from, user_id_to, status=TransactionStatus.SUCCESS
    ):
        trx = Mock()
        trx.id = 456
        trx.status = status
        from_wallet = Mock()
        from_wallet.user_id = user_id_from
        trx.from_wallet = from_wallet
        to_wallet = Mock()
        to_wallet.user_id = user_id_to
        trx.to_wallet = to_wallet
        return trx

    def test_requires_auth(self, api_client):
        url = reverse(self.url_name)
        resp = api_client.post(url, {})
        assert resp.status_code == 401

    def test_amount_required_integer_and_positive(self, auth_client):
        url = reverse(self.url_name)

        assert auth_client.post(url, {}, format="json").status_code == 400

        resp = auth_client.post(url, {"amount": "abc"}, format="json")
        assert resp.status_code == 400
        assert _as_json(resp).get("error") == "amount must be integer"

        resp2 = auth_client.post(url, {"amount": 0}, format="json")
        assert resp2.status_code == 400
        assert _as_json(resp2).get("error") == "amount must be > 0"

    def test_with_transaction_must_be_success_and_belong_to_user(
            self, auth_client, user, user_factory, mocker
    ):
        other = user_factory()

        trx_not_success = self._mock_transaction(
            user_id_from=user.id, user_id_to=user.id,
            status=TransactionStatus.FAILED
        )
        mocker.patch.object(
            views_mod, "get_object_or_404", return_value=trx_not_success
        )
        url = reverse(self.url_name)
        resp = auth_client.post(
            url, {"amount": 1000, "transaction_id": 456}, format="json"
        )
        assert resp.status_code == 400
        assert _as_json(resp).get("error") == "transaction must be SUCCESS"

        trx_not_belong = self._mock_transaction(
            user_id_from=other.id, user_id_to=other.id,
            status=TransactionStatus.SUCCESS
        )
        mocker.patch.object(
            views_mod, "get_object_or_404", return_value=trx_not_belong
        )
        resp2 = auth_client.post(
            url, {"amount": 1000, "transaction_id": 456}, format="json"
        )
        assert resp2.status_code == 403
        assert _as_json(resp2).get(
            "error"
        ) == "transaction does not belong to user"

    def test_success_calls_usecase_and_returns_201(
            self, auth_client, user, mocker
    ):
        uc_mock = mocker.patch.object(
            views_mod.StatementUseCases, "record_payment_on_current_statement"
        )
        url = reverse(self.url_name)
        resp = auth_client.post(
            url, {"amount": 2500, "description": "My Payment"}, format="json"
        )
        assert resp.status_code == 201
        assert _as_json(resp).get("success") is True
        uc_mock.assert_called_once()
        kwargs = uc_mock.call_args.kwargs
        assert kwargs["user"] == user
        assert kwargs["amount"] == 2500
        assert kwargs["payment_transaction"] is None

    def test_success_with_transaction_passes_trx_and_description(
            self, auth_client, user, mocker
    ):
        trx = self._mock_transaction(user_id_from=user.id, user_id_to=999)
        mocker.patch.object(views_mod, "get_object_or_404", return_value=trx)
        uc_mock = mocker.patch.object(
            views_mod.StatementUseCases, "record_payment_on_current_statement"
        )
        url = reverse(self.url_name)
        payload = {"amount": 3500, "transaction_id": 456, "description": "Pay"}
        resp = auth_client.post(url, payload, format="json")
        assert resp.status_code == 201
        uc_mock.assert_called_once()
        kwargs = uc_mock.call_args.kwargs
        assert kwargs["payment_transaction"] is not None
        assert kwargs["description"] == "Pay"

    def test_usecase_exception_returns_400(self, auth_client, mocker):
        mocker.patch.object(
            views_mod.StatementUseCases,
            "record_payment_on_current_statement",
            side_effect=RuntimeError("oops"),
        )
        url = reverse(self.url_name)
        resp = auth_client.post(url, {"amount": 1000}, format="json")
        assert resp.status_code == 400
        assert "error" in _as_json(resp)


# ---------------------------- CloseStatement ----------------------- #

class TestCloseStatementView:
    url_name = "close_statement"

    def test_requires_auth(self, api_client):
        url = reverse(self.url_name)
        resp = api_client.post(url, {})
        assert resp.status_code == 401

    def test_no_current_statement_returns_400(self, auth_client, mocker):
        mocker.patch.object(
            views_mod.Statement.objects, "get_current_statement",
            return_value=None
        )
        url = reverse(self.url_name)
        resp = auth_client.post(url, {}, format="json")
        assert resp.status_code == 400
        assert _as_json(resp).get("error") == "No current statement"

    def test_successful_close_returns_200(self, auth_client, mocker):
        stmt = Mock()
        mocker.patch.object(
            views_mod.Statement.objects, "get_current_statement",
            return_value=stmt
        )
        url = reverse(self.url_name)
        resp = auth_client.post(url, {}, format="json")
        assert resp.status_code == 200
        assert _as_json(resp).get("success") is True
        stmt.close_statement.assert_called_once()

    def test_close_raises_returns_400(self, auth_client, mocker):
        stmt = Mock()
        stmt.close_statement.side_effect = RuntimeError("cannot close")
        mocker.patch.object(
            views_mod.Statement.objects, "get_current_statement",
            return_value=stmt
        )
        url = reverse(self.url_name)
        resp = auth_client.post(url, {}, format="json")
        assert resp.status_code == 400
        assert "error" in _as_json(resp)


class TestStatementListViewMore:
    url_name = "statement_list"

    def test_next_and_previous_links_exist_when_paginated(
            self, auth_client, user, settings
    ):
        """
        Ensure 'next' and 'previous' links behave as expected on the first and middle pages.
        """
        # create 13 statements => 3 pages (5,5,3)
        base_year, base_month = 1404, 1
        for i in range(63):
            y = base_year + ((base_month - 1 + i) // 12)
            m = ((base_month - 1 + i) % 12) + 1
            Statement.objects.create(
                user=user, year=y, month=m, status=StatementStatus.CURRENT
            )

        url = reverse(self.url_name)

        # page 1 -> has next, no previous
        r1 = auth_client.get(url, {"page": 1})
        j1 = r1.json()
        assert j1["next"] is not None
        assert j1["previous"] is None

        # page 2 -> has both next and previous
        r2 = auth_client.get(url, {"page": 2})
        j2 = r2.json()
        assert j2["next"] is not None
        assert j2["previous"] is not None

    def test_page_out_of_range_returns_404(self, auth_client, user, settings):
        """
        DRF PageNumberPagination returns 404 when requesting a page out of range.
        """
        settings.REST_FRAMEWORK["PAGE_SIZE"] = 10
        # only 3 items => 1 page
        for i in range(3):
            Statement.objects.create(
                user=user, year=1404, month=i + 1,
                status=StatementStatus.CURRENT
            )

        url = reverse(self.url_name)
        resp = auth_client.get(url, {"page": 999})
        assert resp.status_code == 404


class TestStatementLineListViewMore:
    url_name = "statement_line_list"

    def test_respects_max_page_size_cap(self, auth_client, user, settings):
        """
        Asking for more than max_page_size should clamp to max_page_size (100 by our StandardPagination).
        """
        settings.REST_FRAMEWORK[
            "PAGE_SIZE"] = 10  # default doesn't matter when page_size is given
        # one statement with 150 lines
        stmt = Statement.objects.create(
            user=user, year=1404, month=1, status=StatementStatus.CURRENT
        )
        for i in range(150):
            StatementLine.objects.create(
                statement=stmt,
                type=StatementLineType.PURCHASE if i % 2 == 0 else StatementLineType.FEE,
                amount=1000 + i,
            )

        url = reverse(self.url_name)
        resp = auth_client.get(url, {"page_size": 10_000})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 100  # clamped to max_page_size

    def test_non_integer_statement_id_filter_returns_empty_200(
            self, auth_client, user
    ):
        """
        Our view does not validate statement_id type; a non-integer won't match any rows.
        Expect 200 OK with empty results (not a 400).
        """
        # ensure the user has at least one statement/line so base queryset is non-empty
        stmt = Statement.objects.create(
            user=user, year=1404, month=1, status=StatementStatus.CURRENT
        )
        StatementLine.objects.create(
            statement=stmt, type=StatementLineType.PURCHASE, amount=1234
        )

        url = reverse(self.url_name)
        resp = auth_client.get(url, {"statement_id": "not-an-int", "page": 1})
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["results"] == []


class TestAddPurchaseViewMore:
    url_name = "add_purchase"

    def test_uses_default_description_when_omitted(
            self, auth_client, user, mocker
    ):
        """
        If 'description' is omitted, the view should pass 'Purchase' to the use case.
        """
        trx = Mock()
        trx.id = 123
        trx.status = TransactionStatus.SUCCESS
        trx.from_wallet = Mock(user_id=user.id, kind=WalletKind.CREDIT)
        trx.to_wallet = Mock(user_id=999)
        mocker.patch.object(views_mod, "get_object_or_404", return_value=trx)

        uc_mock = mocker.patch.object(
            views_mod.StatementUseCases,
            "record_successful_purchase_from_transaction"
        )
        url = reverse(self.url_name)
        resp = auth_client.post(url, {"transaction_id": 123}, format="json")
        assert resp.status_code == 201
        uc_mock.assert_called_once()
        assert uc_mock.call_args.kwargs["description"] == "Purchase"


class TestAddPaymentViewMore:
    url_name = "add_payment"

    def test_uses_default_description_when_omitted(
            self, auth_client, mocker, user
    ):
        """
        If 'description' is omitted, the view should pass 'Payment' to the use case.
        """
        uc_mock = mocker.patch.object(
            views_mod.StatementUseCases, "record_payment_on_current_statement"
        )
        url = reverse(self.url_name)
        resp = auth_client.post(url, {"amount": 1234}, format="json")
        assert resp.status_code == 201
        uc_mock.assert_called_once()
        assert uc_mock.call_args.kwargs["description"] == "Payment"
