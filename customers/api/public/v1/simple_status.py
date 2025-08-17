from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from customers.models.customer import Customer
from merchants.models.merchant import Merchant
from .schema import simple_status_schema

@simple_status_schema
class SimpleStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        active_users_count = Customer.objects.count()
        contracted_merchants_count = Merchant.objects.count()
        return Response({
            "کاربر فعال": active_users_count,
            "فروشگاه طرف قرارداد": contracted_merchants_count,
        })
