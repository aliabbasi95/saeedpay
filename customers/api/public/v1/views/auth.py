# customers/api/public/v1/views/auth.py
from rest_framework import generics

from customers.api.public.v1.serializers.otp import SendOTPSerializer
from customers.api.public.v1.serializers.register import RegisterSerializer


class SendOTPView(generics.CreateAPIView):
    serializer_class = SendOTPSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
