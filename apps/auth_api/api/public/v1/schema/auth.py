# apps/auth_api/api/public/v1/schema/auth.py

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema

from apps.auth_api.api.public.v1.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    RegisterCustomerSerializer,
    RegisterMerchantSerializer,
    ResetPasswordSerializer,
    SendOTPSerializer,
    SendUserOTPSerializer,
)

AUTH_TAG = "Authentication"

LOGIN_SCHEMA = extend_schema(
    tags=[AUTH_TAG],
    summary="Login",
    description=(
        "Authenticate a user using phone number and password. "
        "Returns an access token and sets the refresh token cookie."
    ),
    request=LoginSerializer,
    responses={
        200: OpenApiResponse(
            description="Login successful.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "user_id": 123,
                        "phone_number": "09123456789",
                        "roles": ["customer"],
                        "first_name": "Ali",
                        "last_name": "Ahmadi",
                        "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                        "token_type": "Bearer",
                    },
                )
            ],
        ),
        400: OpenApiResponse(
            description="Invalid credentials or inactive account.",
            examples=[
                OpenApiExample(
                    "InvalidCredentials",
                    value={"detail": "شماره تلفن یا رمز عبور اشتباه است."},
                ),
                OpenApiExample(
                    "InactiveAccount",
                    value={"detail": "حساب کاربری شما غیرفعال است."},
                ),
            ],
        ),
    },
)

LOGOUT_SCHEMA = extend_schema(
    tags=[AUTH_TAG],
    summary="Logout",
    description=(
        "Blacklist the current refresh token if present and clear the refresh cookie."
    ),
    request=None,
    responses={
        205: OpenApiResponse(
            description="Logout successful.",
            examples=[
                OpenApiExample(
                    "Success205",
                    value={"detail": "خروج انجام شد."},
                )
            ],
        ),
        200: OpenApiResponse(
            description="Legacy success response.",
            examples=[
                OpenApiExample(
                    "Success200",
                    value={"detail": "خروج انجام شد."},
                )
            ],
        ),
    },
)

REFRESH_SCHEMA = extend_schema(
    tags=[AUTH_TAG],
    summary="Refresh access token",
    description=(
        "Rotate the refresh cookie and issue a new access token. "
        "Session lifetime limits are enforced."
    ),
    request=None,
    responses={
        200: OpenApiResponse(
            description="Token refreshed successfully.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "access": "eyJhbGciOiJIUzI1NiIs...",
                        "token_type": "Bearer",
                    },
                )
            ],
        ),
        401: OpenApiResponse(
            description="Refresh token is invalid or session has expired.",
            examples=[
                OpenApiExample(
                    "ExpiredSession",
                    value={"detail": "طول عمر نشست تمام شده است. دوباره وارد شوید."},
                )
            ],
        ),
        400: OpenApiResponse(
            description="Token processing error.",
            examples=[
                OpenApiExample(
                    "ProcessingError",
                    value={"detail": "خطا در پردازش توکن."},
                )
            ],
        ),
    },
)

SEND_OTP_SCHEMA = extend_schema(
    tags=[AUTH_TAG],
    summary="Send OTP",
    description="Send a verification code to a phone number for anonymous flows.",
    request=SendOTPSerializer,
    responses={
        200: OpenApiResponse(
            description="OTP sent successfully.",
            examples=[
                OpenApiExample(
                    "Sent",
                    value={"detail": "کد تأیید با موفقیت ارسال شد."},
                )
            ],
        ),
        400: OpenApiResponse(
            description="Validation error or OTP already active.",
            examples=[
                OpenApiExample(
                    "AlreadySent",
                    value={"phone_number": ["کد تایید شما ارسال شده است."]},
                ),
                OpenApiExample(
                    "InvalidPhoneNumber",
                    value={"phone_number": ["شماره تلفن معتبر نیست."]},
                ),
                OpenApiExample(
                    "SendFailed",
                    value={"phone_number": ["ارسال کد با خطا مواجه شد."]},
                ),
            ],
        ),
    },
)

SEND_USER_OTP_SCHEMA = extend_schema(
    tags=[AUTH_TAG],
    summary="Send OTP for current user",
    description="Send a verification code to the authenticated user's phone number.",
    request=SendUserOTPSerializer,
    responses={
        200: OpenApiResponse(
            description="OTP sent successfully.",
            examples=[
                OpenApiExample(
                    "Sent",
                    value={"detail": "کد تأیید با موفقیت ارسال شد."},
                )
            ],
        ),
        400: OpenApiResponse(
            description="Validation error or OTP already active.",
            examples=[
                OpenApiExample(
                    "AlreadySent",
                    value={"phone_number": ["کد تایید شما ارسال شده است."]},
                ),
                OpenApiExample(
                    "InvalidPhoneNumber",
                    value={"phone_number": ["شماره تلفن معتبر نیست."]},
                ),
                OpenApiExample(
                    "SendFailed",
                    value={"phone_number": ["ارسال کد با خطا مواجه شد."]},
                ),
            ],
        ),
    },
)

REGISTER_CUSTOMER_SCHEMA = extend_schema(
    tags=[AUTH_TAG],
    summary="Register customer",
    description=(
        "Register a new customer account using phone number, OTP, and password. "
        "Returns an access token and sets the refresh token cookie."
    ),
    request=RegisterCustomerSerializer,
    responses={
        200: OpenApiResponse(
            description="Customer registered successfully.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "user_id": 456,
                        "phone_number": "09120001122",
                        "roles": ["customer"],
                        "first_name": "",
                        "last_name": "",
                        "access": "eyJhbGciOiJIUzI1NiIs...",
                        "token_type": "Bearer",
                    },
                )
            ],
        ),
        400: OpenApiResponse(
            description="Validation failed.",
            examples=[
                OpenApiExample(
                    "DuplicatePhone",
                    value={
                        "phone_number": "این شماره تلفن قبلاً به عنوان مشتری ثبت شده است."
                    },
                ),
                OpenApiExample(
                    "PasswordMismatch",
                    value={"confirm_password": "رمز عبور و تکرار آن یکسان نیستند."},
                ),
                OpenApiExample(
                    "OTPInvalid",
                    value={"code": "کد تایید اشتباه یا منقضی شده است."},
                ),
            ],
        ),
    },
)

REGISTER_MERCHANT_SCHEMA = extend_schema(
    tags=[AUTH_TAG],
    summary="Register merchant",
    description=(
        "Register a new merchant account using phone number, OTP, and password. "
        "Returns an access token and sets the refresh token cookie."
    ),
    request=RegisterMerchantSerializer,
    responses={
        200: OpenApiResponse(
            description="Merchant registered successfully.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={
                        "user_id": 789,
                        "phone_number": "09123334455",
                        "roles": ["merchant"],
                        "first_name": "",
                        "last_name": "",
                        "access": "eyJhbGciOiJIUzI1NiIs...",
                        "token_type": "Bearer",
                    },
                )
            ],
        ),
        400: OpenApiResponse(
            description="Validation failed.",
            examples=[
                OpenApiExample(
                    "DuplicatePhone",
                    value={
                        "phone_number": "این شماره تلفن قبلاً به عنوان فروشنده ثبت شده است."
                    },
                ),
                OpenApiExample(
                    "PasswordMismatch",
                    value={"confirm_password": "رمز عبور و تکرار آن یکسان نیستند."},
                ),
                OpenApiExample(
                    "OTPInvalid",
                    value={"code": "کد تایید اشتباه یا منقضی شده است."},
                ),
            ],
        ),
    },
)

CHANGE_PASSWORD_SCHEMA = extend_schema(
    tags=[AUTH_TAG],
    summary="Change password",
    description="Change the password of the authenticated user.",
    request=ChangePasswordSerializer,
    responses={
        200: OpenApiResponse(
            description="Password changed successfully.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={"detail": "رمز عبور با موفقیت تغییر یافت."},
                )
            ],
        ),
        400: OpenApiResponse(
            description="Validation failed.",
            examples=[
                OpenApiExample(
                    "WrongCurrentPassword",
                    value={"current_password": "رمز عبور فعلی اشتباه است."},
                ),
                OpenApiExample(
                    "PasswordMismatch",
                    value={
                        "confirm_password": "رمز عبور جدید و تکرار آن یکسان نیستند."
                    },
                ),
                OpenApiExample(
                    "SameAsCurrent",
                    value={
                        "new_password": "رمز عبور جدید نباید با رمز عبور فعلی یکسان باشد."
                    },
                ),
            ],
        ),
    },
)

RESET_PASSWORD_SCHEMA = extend_schema(
    tags=[AUTH_TAG],
    summary="Reset password",
    description="Reset a user's password using phone number, OTP, and a new password.",
    request=ResetPasswordSerializer,
    responses={
        200: OpenApiResponse(
            description="Password reset successfully.",
            examples=[
                OpenApiExample(
                    "Success",
                    value={"detail": "رمز عبور با موفقیت بازنشانی شد."},
                )
            ],
        ),
        400: OpenApiResponse(
            description="Validation failed.",
            examples=[
                OpenApiExample(
                    "UserNotFound",
                    value={"phone_number": "کاربری با این شماره تلفن یافت نشد."},
                ),
                OpenApiExample(
                    "PasswordMismatch",
                    value={
                        "confirm_password": "رمز عبور جدید و تکرار آن یکسان نیستند."
                    },
                ),
                OpenApiExample(
                    "OTPInvalid",
                    value={"code": "کد تایید اشتباه یا منقضی شده است."},
                ),
            ],
        ),
    },
)
