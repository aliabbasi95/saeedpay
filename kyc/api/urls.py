from django.urls import path, include

app_name = 'kyc'

urlpatterns = [
    path('public/', include('kyc.api.public.urls')),
]
