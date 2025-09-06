from django.urls import path, include

urlpatterns = [
    path('public/', include('contact.api.public.urls')),
]
