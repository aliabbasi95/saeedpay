# wallets/tests/public/v1/serializers/test_payment.py

import pytest

from wallets.api.partner.v1.serializers.payment import \
    PaymentRequestCreateSerializer


@pytest.mark.django_db
class TestPaymentRequestCreateSerializer:

    def test_valid_data(self):
        data = {
            "amount": 1000, "return_url": "https://callback.com",
            "external_guid": "ORD-1"
        }
        s = PaymentRequestCreateSerializer(data=data)
        assert s.is_valid(), s.errors
        assert s.validated_data["external_guid"] == "ORD-1"

    @pytest.mark.parametrize("amount", [0, -1, -9999])
    def test_invalid_amount(self, amount):
        data = {"amount": amount, "return_url": "https://cb.com"}
        s = PaymentRequestCreateSerializer(data=data)
        assert not s.is_valid()
        assert "amount" in s.errors

    def test_missing_return_url(self):
        s = PaymentRequestCreateSerializer(data={"amount": 500})
        assert not s.is_valid()
        assert "return_url" in s.errors

    @pytest.mark.parametrize(
        "url", ["http://unsafe.com", "not-a-url", "ftp://test.com", ""]
    )
    def test_invalid_return_url(self, url):
        data = {"amount": 100, "return_url": url}
        s = PaymentRequestCreateSerializer(data=data)
        assert not s.is_valid()
        assert "return_url" in s.errors

    def test_optional_description(self):
        data = {"amount": 1000, "return_url": "https://ok.com"}
        s = PaymentRequestCreateSerializer(data=data)
        assert s.is_valid()
        data_with_desc = {
            "amount": 500, "return_url": "https://cb.com",
            "description": "test desc"
        }
        s2 = PaymentRequestCreateSerializer(data=data_with_desc)
        assert s2.is_valid()
        assert s2.validated_data["description"] == "test desc"

    def test_description_max_length(self):
        long_desc = "a" * 256
        s = PaymentRequestCreateSerializer(
            data={
                "amount": 1, "return_url": "https://ok.com",
                "description": long_desc
            }
        )
        assert not s.is_valid()
        assert "description" in s.errors

    def test_type_errors(self):
        s = PaymentRequestCreateSerializer(
            data={"amount": "notint", "return_url": "https://ok.com"}
        )
        assert not s.is_valid() and "amount" in s.errors

        s2 = PaymentRequestCreateSerializer(
            data={"amount": 1, "return_url": 12345}
        )
        assert not s2.is_valid() and "return_url" in s2.errors

    def test_extra_fields_ignored(self):
        s = PaymentRequestCreateSerializer(
            data={"amount": 100, "return_url": "https://cb.com", "foo": "bar"}
        )
        assert s.is_valid()
        assert "foo" not in s.validated_data

    def test_external_guid_optional_and_length(self):
        s = PaymentRequestCreateSerializer(
            data={"amount": 5, "return_url": "https://ok.com"}
        )
        assert s.is_valid()

        too_long = "x" * 100
        s2 = PaymentRequestCreateSerializer(
            data={
                "amount": 5, "return_url": "https://ok.com",
                "external_guid": too_long
            }
        )
        assert not s2.is_valid()
        assert "external_guid" in s2.errors
