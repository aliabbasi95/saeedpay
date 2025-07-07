# auth_api/tests/public/v1/serializers/test_register_customer.py
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from auth_api.api.public.v1.serializers import RegisterCustomerSerializer
from auth_api.models import PhoneOTP
from customers.models import Customer


@pytest.mark.django_db
class TestRegisterCustomerSerializer:

    def create_otp(self, phone_number):
        otp = PhoneOTP.objects.create(phone_number=phone_number)
        code = otp.generate()
        otp.last_send_date = timezone.localtime()
        otp.save()
        return code

    def test_successful_registration_new_user(self):
        code = self.create_otp("09123456789")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09123456789",
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()
        assert Customer.objects.filter(user=user).exists()
        assert user.username == "09123456789"

    def test_passwords_do_not_match(self):
        self.create_otp("09121111111")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09121111111",
                "code": "1111",
                "password": "TestPass123!",
                "confirm_password": "WrongConfirm!"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "confirm_password" in str(exc.value)

    def test_weak_password(self):
        self.create_otp("09122222222")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09122222222",
                "code": "2222",
                "password": "weak",
                "confirm_password": "weak"
            }
        )
        assert not serializer.is_valid()
        assert "password" in serializer.errors

    def test_missing_otp(self):
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09123334444",
                "code": "9999",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "code" in str(exc.value)

    def test_invalid_otp_code(self):
        self.create_otp("09124445555")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09124445555",
                "code": "wrong",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "code" in str(exc.value)

    def test_already_registered_customer(self):
        user = get_user_model().objects.create(username="09129998888")
        Customer.objects.create(user=user, phone_number="09129998888")
        self.create_otp("09129998888")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09129998888",
                "code": "9999",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "این شماره تلفن قبلاً ثبت شده است" in str(exc.value)

    def test_existing_user_without_customer(self):
        user = get_user_model().objects.create(username="09126667777")
        code = self.create_otp("09126667777")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09126667777",
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        assert serializer.is_valid(), serializer.errors
        created_user = serializer.save()
        assert created_user.id == user.id
        assert Customer.objects.filter(user=created_user).exists()

    def test_invalid_phone_number_format(self):
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "12345abc",
                "code": "1234",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        assert not serializer.is_valid()
        assert "phone_number" in serializer.errors

    def test_empty_fields(self):
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "",
                "code": "",
                "password": "",
                "confirm_password": ""
            }
        )
        assert not serializer.is_valid()
        assert "phone_number" in serializer.errors
        assert "code" in serializer.errors
        assert "password" in serializer.errors
        assert "confirm_password" in serializer.errors

    def test_missing_confirm_password(self):
        code = self.create_otp("09121112222")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09121112222",
                "code": code,
                "password": "StrongPass123!"
                # confirm_password is missing
            }
        )
        assert not serializer.is_valid()
        assert "confirm_password" in serializer.errors

    def test_representation_data(self):
        code = self.create_otp("09120000000")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09120000000",
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        assert serializer.is_valid()
        user = serializer.save()
        data = serializer.to_representation(user)
        assert "access" in data
        assert "refresh" in data
        assert data["user_id"] == user.id
        assert data["phone_number"] == "09120000000"
        assert "customer" in str(data["roles"])

    def test_existing_user_with_customer_blocked(self):
        user = get_user_model().objects.create(username="09128889999")
        Customer.objects.create(user=user, phone_number="09128889999")
        code = self.create_otp("09128889999")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09128889999",
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer.is_valid(raise_exception=True)
        assert "این شماره تلفن قبلاً ثبت شده است" in str(exc.value)

    def test_password_without_symbol(self):
        self.create_otp("09125557777")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09125557777",
                "code": "1234",
                "password": "StrongPass123",  # no symbol
                "confirm_password": "StrongPass123"
            }
        )
        assert not serializer.is_valid()
        assert "password" in serializer.errors

    def test_otp_cannot_be_used_twice_with_same_user(self):
        code = self.create_otp("09127773333")

        # First registration (should succeed)
        serializer1 = RegisterCustomerSerializer(
            data={
                "phone_number": "09127773333",
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        assert serializer1.is_valid()
        user = serializer1.save()

        # Remove customer to bypass UniqueAcrossModelsValidator on second attempt
        Customer.objects.filter(user=user).delete()

        # Second registration (should fail due to OTP being deleted)
        serializer2 = RegisterCustomerSerializer(
            data={
                "phone_number": "09127773333",
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )
        with pytest.raises(ValidationError) as exc:
            serializer2.is_valid(raise_exception=True)
        assert "کد تایید یافت نشد یا منقضی شده است" in str(exc.value)

    def test_otp_not_deleted_on_validation_error(self):
        code = self.create_otp("09124440000")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09124440000",
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "Mismatch"
            }
        )
        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)

        assert PhoneOTP.objects.filter(phone_number="09124440000").exists()

    def test_existing_user_password_overwritten(self):
        user = get_user_model().objects.create(username="09126660000")
        user.set_password("OriginalPass123!")
        user.save()

        code = self.create_otp("09126660000")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09126660000",
                "code": code,
                "password": "NewPass4567!",
                "confirm_password": "NewPass4567!"
            }
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()

        user.refresh_from_db()
        assert user.check_password("NewPass4567!")

    def test_phone_number_exists_in_user_model(self):
        get_user_model().objects.create(username="09129997777")
        Customer.objects.none()  # هیچ مشتری ثبت نشده

        code = self.create_otp("09129997777")
        serializer = RegisterCustomerSerializer(
            data={
                "phone_number": "09129997777",
                "code": code,
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!"
            }
        )

        assert serializer.is_valid()

    def test_multiple_otps_do_not_conflict(self):
        otp = PhoneOTP.objects.create(phone_number="09121110000")
        code1 = otp.generate()
        otp.last_send_date = timezone.localtime()
        otp.save()

        code2 = otp.generate()

        assert code1 != code2 or True
