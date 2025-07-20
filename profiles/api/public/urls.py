# profiles/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path('v1/', include('profiles.api.public.v1.urls')),
]
