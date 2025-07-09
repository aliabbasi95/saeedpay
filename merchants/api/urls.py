# merchants/api/public/urls.py
from django.urls import include, path

urlpatterns = [
    path('public/', include('merchants.api.public.urls')),
]
