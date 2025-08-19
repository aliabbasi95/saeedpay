# chatbot/api/urls.py

from django.urls import path, include

urlpatterns = [
    path("public/", include("chatbot.api.public.urls")),
]
