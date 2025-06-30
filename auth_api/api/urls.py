# auth_api/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path('public/', include('auth_api.api.public.urls')),
]
