# chatbot/api/urls.py

from django.urls import include, path

urlpatterns = [
    path("public/", include("chatbot.api.public.urls")),
]
