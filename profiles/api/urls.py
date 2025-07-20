# profiles/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path('public/', include('profiles.api.public.urls')),
]
