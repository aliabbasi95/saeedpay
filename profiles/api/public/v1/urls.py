# merchants/api/public/v1/urls.py

from django.urls import path

from .views import ProfileView

app_name = "profiles_public_v1"

urlpatterns = [
    path('profile/', ProfileView.as_view(), name='profile-view'),
]
