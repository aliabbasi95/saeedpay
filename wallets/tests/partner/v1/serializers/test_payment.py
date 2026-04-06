# wallets/tests/public/v1/serializers/test_payment.py

import pytest

from wallets.api.partner.v1.serializers.payment import (
    PaymentRequestCreateSerializer,
)


@pytest.mark.django_db
class TestPaymentRequestCreateSerializer:

    def test_valid_data(self):
        data = {
            "amount": 1000,
            "return_url": "https://callback.com",
            "external_guid": "ORD-1",
            "national_id": "1234567890",
        }
        serializer = PaymentRequestCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["external_guid"] == "ORD-1"
        assert serializer.validated_data["national_id"] == "1234567890"

    @pytest.mark.parametrize("amount", [0, -1, -9999])
    def test_invalid_amount(self, amount):
        data = {
            "amount": amount,
            "return_url": "https://cb.com",
            "national_id": "1234567890",
        }
        serializer = PaymentRequestCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

    def test_missing_return_url(self):
        serializer = PaymentRequestCreateSerializer(
            data={"amount": 500, "national_id": "1234567890"}
        )
        assert not serializer.is_valid()
        assert "return_url" in serializer.errors

    def test_missing_national_id(self):
        serializer = PaymentRequestCreateSerializer(
            data={"amount": 500, "return_url": "https://cb.com"}
        )
        assert not serializer.is_valid()
        assert "national_id" in serializer.errors

    @pytest.mark.parametrize(
        "url",
        ["http://unsafe.com", "not-a-url", "ftp://test.com", ""],
    )
    def test_invalid_return_url(self, url):
        data = {
            "amount": 100,
            "return_url": url,
            "national_id": "1234567890",
        }
        serializer = PaymentRequestCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "return_url" in serializer.errors

    def test_optional_description(self):
        data = {
            "amount": 1000,
            "return_url": "https://ok.com",
            "national_id": "1234567890",
        }
        serializer = PaymentRequestCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        data_with_desc = {
            "amount": 500,
            "return_url": "https://cb.com",
            "description": "test desc",
            "national_id": "1234567890",
        }
        serializer_with_desc = PaymentRequestCreateSerializer(
            data=data_with_desc
        )
        assert serializer_with_desc.is_valid(), serializer_with_desc.errors
        assert serializer_with_desc.validated_data["description"] == "test desc"

    def test_description_max_length(self):
        long_desc = "a" * 256
        serializer = PaymentRequestCreateSerializer(
            data={
                "amount": 1,
                "return_url": "https://ok.com",
                "description": long_desc,
                "national_id": "1234567890",
            }
        )
        assert not serializer.is_valid()
        assert "description" in serializer.errors

    def test_type_errors(self):
        serializer = PaymentRequestCreateSerializer(
            data={
                "amount": "notint",
                "return_url": "https://ok.com",
                "national_id": "1234567890",
            }
        )
        assert not serializer.is_valid()
        assert "amount" in serializer.errors

        serializer2 = PaymentRequestCreateSerializer(
            data={
                "amount": 1,
                "return_url": 12345,
                "national_id": "1234567890",
            }
        )
        assert not serializer2.is_valid()
        assert "return_url" in serializer2.errors

    def test_extra_fields_ignored(self):
        serializer = PaymentRequestCreateSerializer(
            data={
                "amount": 100,
                "return_url": "https://cb.com",
                "foo": "bar",
                "national_id": "1234567890",
            }
        )
        assert serializer.is_valid(), serializer.errors
        assert "foo" not in serializer.validated_data

    def test_external_guid_optional_and_length(self):
        serializer = PaymentRequestCreateSerializer(
            data={
                "amount": 5,
                "return_url": "https://ok.com",
                "national_id": "1234567890",
            }
        )
        assert serializer.is_valid(), serializer.errors

        too_long = "x" * 100
        serializer2 = PaymentRequestCreateSerializer(
            data={
                "amount": 5,
                "return_url": "https://ok.com",
                "external_guid": too_long,
                "national_id": "1234567890",
            }
        )
        assert not serializer2.is_valid()
        assert "external_guid" in serializer2.errors
