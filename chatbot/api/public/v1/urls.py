# chatbot/api/public/v1/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from chatbot.api.public.v1.views import ChatSessionViewSet

app_name = "chatbot_public_v1"

router = DefaultRouter()
router.register("sessions", ChatSessionViewSet, basename="chat-session")

urlpatterns = [
    path("", include(router.urls)),
]
