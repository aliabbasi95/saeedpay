# auth_api/api/public/v1/views/auth.py

from datetime import timedelta

from django.conf import settings
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from auth_api.api.public.v1.schema import (
    LOGIN_SCHEMA,
    LOGOUT_SCHEMA,
    REFRESH_SCHEMA,
    SEND_OTP_SCHEMA,
    SEND_USER_OTP_SCHEMA,
    REGISTER_CUSTOMER_SCHEMA,
    REGISTER_MERCHANT_SCHEMA,
    CHANGE_PASSWORD_SCHEMA,
    RESET_PASSWORD_SCHEMA,
)
from auth_api.api.public.v1.serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    RegisterCustomerSerializer,
    RegisterMerchantSerializer,
    ResetPasswordSerializer,
    SendOTPSerializer,
    SendUserOTPSerializer,
)
from auth_api.api.public.v1.views.mixins import IssueTokensResponseMixin
from auth_api.services.tokens import rotate_refresh_cookie
from auth_api.utils.cookies import set_refresh_cookie, delete_refresh_cookie
from auth_api.utils.throttles import OTPPhoneRateThrottle
from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin

MAX_SESSION_LIFETIME = getattr(
    settings, "MAX_SESSION_LIFETIME", timedelta(hours=24)
)


class AuthViewSet(
    ScopedThrottleByActionMixin,
    IssueTokensResponseMixin,
    viewsets.GenericViewSet
):
    """
    Route-based Authentication endpoints (router + per-action schema/throttling/permissions).

    Endpoints (all POST):
    - /auth/login/
    - /auth/logout/
    - /auth/token/refresh/
    - /auth/send-otp/
    - /auth/user/send-otp/              (requires auth)
    - /auth/register/customer/
    - /auth/register/merchant/
    - /auth/change-password/            (requires auth)
    - /auth/reset-password/
    """

    throttle_scope_map = {
        "login": "auth-login",
        "logout": "auth-logout",
        "refresh": "auth-refresh",
        "send_otp": "auth-otp",
        "send_user_otp": "auth-otp",
        "register_customer": "auth-register",
        "register_merchant": "auth-register",
        "change_password": "auth-change-password",
        "reset_password": "auth-reset-password",
        "default": None,
    }

    # ---------- permissions per action ----------
    def get_permissions(self):
        public_actions = {
            "login",
            "logout",
            "refresh",
            "send_otp",
            "register_customer",
            "register_merchant",
            "reset_password",
        }
        if self.action in public_actions:
            return [AllowAny()]
        return [IsAuthenticated()]

    # ---------- serializers per action ----------
    def _serializer_map(self):
        return {
            "login": LoginSerializer,
            "send_otp": SendOTPSerializer,
            "send_user_otp": SendUserOTPSerializer,
            "register_customer": RegisterCustomerSerializer,
            "register_merchant": RegisterMerchantSerializer,
            "change_password": ChangePasswordSerializer,
            "reset_password": ResetPasswordSerializer,
        }

    def get_serializer_class(self):
        return self._serializer_map().get(self.action)

    def get_serializer(self, *args, **kwargs):
        # Always attach request to serializer context
        kwargs.setdefault("context", {})
        kwargs["context"].setdefault("request", self.request)
        return super().get_serializer(*args, **kwargs)

    # ---------- extra throttles per action (phone-level) ----------
    def get_throttles(self):
        throttles = super().get_throttles()
        if self.action in {"send_otp", "send_user_otp", "reset_password"}:
            throttles.append(OTPPhoneRateThrottle())
        return throttles

    # ---------- helpers ----------
    def _ok(self, detail, status_code=status.HTTP_200_OK):
        return Response({"detail": detail}, status=status_code)

    # ===================== Actions =====================

    @LOGIN_SCHEMA
    @action(detail=False, methods=["post"], url_path="login")
    def login(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        return self.build_tokens_response(ser, user)

    @LOGOUT_SCHEMA
    @action(detail=False, methods=["post"], url_path="logout")
    def logout(self, request):
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "sp_refresh")
        refresh_str = request.COOKIES.get(cookie_name)
        if refresh_str:
            try:
                token = RefreshToken(refresh_str)
                try:
                    token.blacklist()
                except Exception:
                    pass
            except TokenError:
                pass
        resp = self._ok("خروج انجام شد.", status.HTTP_205_RESET_CONTENT)
        delete_refresh_cookie(resp)
        return resp

    @REFRESH_SCHEMA
    @action(detail=False, methods=["post"], url_path="token/refresh")
    def refresh(self, request):
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "sp_refresh")
        try:
            access, new_refresh_str = rotate_refresh_cookie(
                request,
                max_session_lifetime=MAX_SESSION_LIFETIME,
                cookie_name=cookie_name,
            )
        except ValueError as e:
            resp = Response(
                {"detail": str(e)}, status=status.HTTP_401_UNAUTHORIZED
            )
            resp.delete_cookie(cookie_name, path="/")
            return resp
        except Exception:
            return Response(
                {"detail": "خطا در پردازش توکن."},
                status=status.HTTP_400_BAD_REQUEST
            )

        resp = Response(
            {"access": access, "token_type": "Bearer"},
            status=status.HTTP_200_OK
        )
        set_refresh_cookie(resp, new_refresh_str)
        return resp

    @SEND_OTP_SCHEMA
    @action(detail=False, methods=["post"], url_path="send-otp")
    def send_otp(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return self._ok("کد تأیید با موفقیت ارسال شد.")

    @SEND_USER_OTP_SCHEMA
    @action(detail=False, methods=["post"], url_path="user/send-otp")
    def send_user_otp(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return self._ok("کد تأیید با موفقیت ارسال شد.")

    @REGISTER_CUSTOMER_SCHEMA
    @action(detail=False, methods=["post"], url_path="register/customer")
    def register_customer(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        return self.build_tokens_response(ser, user)

    @REGISTER_MERCHANT_SCHEMA
    @action(detail=False, methods=["post"], url_path="register/merchant")
    def register_merchant(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        return self.build_tokens_response(ser, user)

    @CHANGE_PASSWORD_SCHEMA
    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return self._ok("رمز عبور با موفقیت تغییر یافت.")

    @RESET_PASSWORD_SCHEMA
    @action(detail=False, methods=["post"], url_path="reset-password")
    def reset_password(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return self._ok("رمز عبور با موفقیت بازنشانی شد.")
