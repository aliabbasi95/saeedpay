# customers/api/public/v1/views/login.py
from rest_framework.permissions import AllowAny

from auth_api.api.public.v1.serializers import LoginSerializer
from lib.cas_auth.views import PublicAPIView


class LoginView(PublicAPIView):
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    def perform_save(self, serializer):
        super().perform_save(serializer)
        self.response_data = serializer.data
