# apps/chatbot/api/urls.py

from django.urls import include, path

urlpatterns = [
    path("public/", include("apps.chatbot.api.public.urls")),
]
