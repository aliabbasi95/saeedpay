# contact/api/public/v1/views/contact.py

from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from contact.api.public.v1.schema import contact_create_schema
from contact.api.public.v1.serializers.contact import ContactCreateSerializer


class ContactCreateView(APIView):
    permission_classes = [AllowAny]
    serializer_class = ContactCreateSerializer

    @contact_create_schema
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
