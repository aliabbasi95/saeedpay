# auth_api/api/public/v1/views/register_customer.py
from rest_framework import generics

from auth_api.api.public.v1.serializers import RegisterCustomerSerializer


class RegisterCustomerView(generics.CreateAPIView):
    serializer_class = RegisterCustomerSerializer
