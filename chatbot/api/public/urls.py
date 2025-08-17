from django.urls import path, include

urlpatterns = [
    path("v1/", include("chatbot.api.public.v1.urls")),
]
