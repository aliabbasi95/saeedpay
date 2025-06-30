# customers/api/public/v1/views/auth.py
from rest_framework import generics

from customers.api.public.v1.serializers import (
    SendOTPSerializer,
    RegisterSerializer,
    LoginSerializer,
)


class SendOTPView(generics.CreateAPIView):
    serializer_class = SendOTPSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer


class LoginView(generics.CreateAPIView):
    serializer_class = LoginSerializer
