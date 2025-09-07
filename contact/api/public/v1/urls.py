# contact/api/public/v1/urls.py

from django.urls import path

from contact.api.public.v1.views.contact import ContactCreateView

urlpatterns = [
    path(
        "contact/",
        ContactCreateView.as_view(),
        name="contact-create"
    ),
]
