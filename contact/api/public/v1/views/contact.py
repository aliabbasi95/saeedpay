# contact/api/public/v1/views/contact.py

from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny

from contact.api.public.v1.schema import contact_create_schema
from contact.api.public.v1.serializers.contact import ContactCreateSerializer
from lib.erp_base.rest.throttling import ScopedThrottleByActionMixin


class ContactCreateView(ScopedThrottleByActionMixin, CreateAPIView):
    """
    Public endpoint to submit a contact message.
    """
    permission_classes = [AllowAny]
    serializer_class = ContactCreateSerializer
    throttle_scope_map = {
        "POST": "contact-create",
        "default": None,
    }

    @contact_create_schema
    def post(self, request, *args, **kwargs):
        # Use DRF's CreateAPIView implementation (validation + save + 201)
        return super().post(request, *args, **kwargs)
