# apps/chatbot/api/public/urls.py

from django.urls import include, path

urlpatterns = [
    path("v1/", include("apps.chatbot.api.public.v1.urls")),
]
