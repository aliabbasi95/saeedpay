# store/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path('public/', include('store.api.public.urls')),
]
