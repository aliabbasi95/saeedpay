# customers/api/public/v1/views/login.py

from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.permissions import AllowAny

from auth_api.api.public.v1.views.mixins import IssueTokensResponseMixin
from auth_api.api.public.v1.serializers import LoginSerializer
from lib.cas_auth.views import PublicAPIView


@extend_schema(
    request=LoginSerializer,
    responses={
        200: OpenApiResponse(
            description="Login success response with JWT tokens."
        ),
        400: OpenApiResponse(description="Invalid phone number or password."),
    },
    tags=["Authentication"]
)
class LoginView(IssueTokensResponseMixin, PublicAPIView):
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    def perform_save(self, serializer):
        user = serializer.save()
        self.response = self.build_tokens_response(serializer, user)
