# auth_api/api/public/v1/views/login.py
from rest_framework import generics

from auth_api.api.public.v1.serializers import SendOTPSerializer


class SendOTPView(generics.CreateAPIView):
    serializer_class = SendOTPSerializer
