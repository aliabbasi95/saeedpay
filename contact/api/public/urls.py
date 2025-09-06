from django.urls import path, include

urlpatterns = [
    path('v1/', include('contact.api.public.v1.urls')),
]
