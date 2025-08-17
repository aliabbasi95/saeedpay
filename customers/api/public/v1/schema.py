from drf_spectacular.utils import OpenApiResponse, OpenApiTypes, extend_schema
from rest_framework import serializers

class SimpleStatusResponseSerializer(serializers.Serializer):
    کاربر_فعال = serializers.IntegerField(help_text="تعداد کاربران فعال")
    فروشگاه_طرف_قرارداد = serializers.IntegerField(help_text="تعداد فروشگاه‌های طرف قرارداد")

simple_status_schema = extend_schema(
    summary="دریافت تعداد کاربران فعال و فروشگاه‌های طرف قرارداد",
    description="این سرویس تعداد کاربران فعال و فروشگاه‌های طرف قرارداد را برمی‌گرداند.",
    responses={200: SimpleStatusResponseSerializer},
)
