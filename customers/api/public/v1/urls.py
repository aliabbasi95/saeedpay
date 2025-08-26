# customers/api/public/v1/urls.py
from django.urls import path
from .views.simple_status import SimpleStatusView

urlpatterns = [
    path("simple-status/", SimpleStatusView.as_view(), name="simple_status"),
]
