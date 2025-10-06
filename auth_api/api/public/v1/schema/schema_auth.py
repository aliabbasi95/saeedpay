# auth_api/api/public/v1/schema_auth.py
# Centralized OpenAPI schemas for AuthViewSet actions.

from drf_spectacular.utils import (
    extend_schema,
    OpenApiResponse,
    OpenApiExample,
)

LOGIN_SCHEMA = extend_schema(
    tags=["Authentication"],
    request=None,  # serializer is inferred from view.get_serializer_class()
    responses={
        200: OpenApiResponse(
            description="Login success with JWT tokens.",
            examples=[OpenApiExample(
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
            )],
        ),
        400: OpenApiResponse(
            description="Invalid phone or password.",
            examples=[OpenApiExample(
                "InvalidCredentials",
                value={"detail": "شماره تلفن یا رمز عبور اشتباه است."}
            )],
        ),
    },
    summary="Login",
    description="Authenticate by phone/password. Returns access token and sets refresh cookie.",
)

LOGOUT_SCHEMA = extend_schema(
    tags=["Authentication"],
    request=None,
    responses={
        205: OpenApiResponse(
            description="Logout successful.",
            examples=[
                OpenApiExample("Success", value={"detail": "خروج انجام شد."})],
        ),
        200: OpenApiResponse(
            description="Logout successful (legacy).",
            examples=[OpenApiExample(
                "SuccessLegacy", value={"detail": "خروج انجام شد."}
            )],
        ),
    },
    summary="Logout",
    description="Blacklists current refresh token (if present) and clears the refresh cookie.",
)

REFRESH_SCHEMA = extend_schema(
    tags=["Authentication"],
    request=None,
    responses={
        200: OpenApiResponse(
            description="New access token issued.",
            examples=[OpenApiExample(
                "Rotated",
                value={
                    "access": "eyJhbGciOiJIUzI1NiIs...", "token_type": "Bearer"
                }
            )],
        ),
        401: OpenApiResponse(
            description="Session expired or token invalid.",
            examples=[OpenApiExample(
                "Expired",
                value={
                    "detail": "طول عمر نشست تمام شده است. دوباره وارد شوید."
                }
            )],
        ),
    },
    summary="Rotate refresh token",
    description="Rotate refresh cookie → new access + new refresh cookie, with max session lifetime enforcement.",
)

SEND_OTP_SCHEMA = extend_schema(
    tags=["Authentication"],
    request=None,
    responses={
        200: OpenApiResponse(
            description="OTP sent.",
            examples=[OpenApiExample(
                "Sent", value={"detail": "کد تأیید با موفقیت ارسال شد."}
            )],
        ),
        400: OpenApiResponse(
            description="OTP already sent.",
            examples=[OpenApiExample(
                "Alive",
                value={"phone_number": ["کد تایید شما ارسال شده است."]}
            )],
        ),
    },
    summary="Send OTP",
    description="Send verification code to a raw phone number (anonymous).",
)

SEND_USER_OTP_SCHEMA = extend_schema(
    tags=["Authentication"],
    request=None,
    responses={
        200: OpenApiResponse(
            description="OTP sent.",
            examples=[OpenApiExample(
                "Sent", value={"detail": "کد تأیید با موفقیت ارسال شد."}
            )],
        ),
        400: OpenApiResponse(
            description="OTP already sent / invalid phone.",
            examples=[OpenApiExample(
                "Alive",
                value={"phone_number": ["کد تایید شما ارسال شده است."]}
            )],
        ),
    },
    summary="Send OTP (current user)",
    description="Send OTP to authenticated user's profile phone.",
)

REGISTER_CUSTOMER_SCHEMA = extend_schema(
    tags=["Authentication"],
    request=None,
    responses={
        201: OpenApiResponse(
            description="User registered successfully.",
            examples=[OpenApiExample(
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
            )],
        ),
        400: OpenApiResponse(
            description="Validation failed.",
            examples=[
                OpenApiExample(
                    "Duplicate",
                    value={
                        "phone_number": "این شماره تلفن قبلاً به عنوان مشتری ثبت شده است."
                    }
                ),
                OpenApiExample(
                    "OTPInvalid",
                    value={"code": "کد تایید اشتباه یا منقضی شده است."}
                ),
            ],
        ),
    },
    summary="Register (customer)",
)

REGISTER_MERCHANT_SCHEMA = extend_schema(
    tags=["Authentication"],
    request=None,
    responses={
        201: OpenApiResponse(
            description="User registered successfully.",
            examples=[OpenApiExample(
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
            )],
        ),
        400: OpenApiResponse(
            description="Validation failed.",
            examples=[
                OpenApiExample(
                    "Duplicate",
                    value={
                        "phone_number": "این شماره تلفن قبلاً به عنوان فروشنده ثبت شده است."
                    }
                ),
                OpenApiExample(
                    "OTPInvalid",
                    value={"code": "کد تایید اشتباه یا منقضی شده است."}
                ),
            ],
        ),
    },
    summary="Register (merchant)",
)

CHANGE_PASSWORD_SCHEMA = extend_schema(
    tags=["Authentication"],
    request=None,
    responses={
        200: OpenApiResponse(
            description="Password changed successfully.",
            examples=[OpenApiExample(
                "Success", value={"detail": "رمز عبور با موفقیت تغییر یافت."}
            )],
        ),
        400: OpenApiResponse(
            description="Validation failed.",
            examples=[
                OpenApiExample(
                    "WrongCurrent",
                    value={"current_password": "رمز عبور فعلی اشتباه است."}
                ),
                OpenApiExample(
                    "SameAsOld",
                    value={
                        "new_password": "رمز عبور جدید نباید با رمز عبور فعلی یکسان باشد."
                    }
                ),
            ],
        ),
    },
    summary="Change password",
)

RESET_PASSWORD_SCHEMA = extend_schema(
    tags=["Authentication"],
    request=None,
    responses={
        200: OpenApiResponse(
            description="Password reset successfully.",
            examples=[OpenApiExample(
                "Success", value={"detail": "رمز عبور با موفقیت بازنشانی شد."}
            )],
        ),
        400: OpenApiResponse(
            description="Validation failed.",
            examples=[
                OpenApiExample(
                    "NotFound",
                    value={
                        "phone_number": "کاربری با این شماره تلفن یافت نشد."
                    }
                ),
                OpenApiExample(
                    "OTPInvalid",
                    value={"code": "کد تایید اشتباه یا منقضی شده است."}
                ),
            ],
        ),
    },
    summary="Reset password (OTP)",
)
