from django.urls import path, include

app_name = 'kyc_public'

urlpatterns = [
    path('v1/', include('kyc.api.public.v1.urls')),
]
