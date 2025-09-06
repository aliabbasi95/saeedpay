# store/api/public/v1/schema.py

from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample, OpenApiParameter
from drf_spectacular.openapi import AutoSchema
from rest_framework import status

from .serializers import StoreSerializer, StoreCreateSerializer, PublicStoreSerializer


# Store Management Schemas (Owner/Merchant)
store_list_schema = extend_schema(
    operation_id="store_list",
    summary="لیست فروشگاه‌های فروشنده",
    description="دریافت لیست تمام فروشگاه‌های متعلق به فروشنده جاری",
    responses={
        200: OpenApiResponse(
            response=StoreSerializer(many=True),
            description="لیست فروشگاه‌ها با موفقیت دریافت شد"
        ),
        401: OpenApiResponse(description="احراز هویت نشده"),
        403: OpenApiResponse(description="دسترسی مجاز نیست"),
    },
    tags=["Store · Management"]
)

store_create_schema = extend_schema(
    operation_id="store_create",
    summary="ایجاد فروشگاه جدید",
    description="ایجاد یک فروشگاه جدید برای فروشنده جاری",
    request=StoreCreateSerializer,
    responses={
        201: OpenApiResponse(
            response=StoreSerializer,
            description="فروشگاه با موفقیت ایجاد شد"
        ),
        400: OpenApiResponse(description="داده‌های ورودی نامعتبر"),
        401: OpenApiResponse(description="احراز هویت نشده"),
        403: OpenApiResponse(description="دسترسی مجاز نیست"),
    },
    examples=[
        OpenApiExample(
            "Store Creation Example",
            summary="مثال ایجاد فروشگاه",
            description="نمونه داده برای ایجاد فروشگاه جدید",
            value={
                "name": "فروشگاه نمونه",
                "address": "تهران، خیابان ولیعصر",
                "longitude": "51.3890",
                "latitude": "35.6892",
                "website_url": "https://example-store.com",
            },
            request_only=True,
        )
    ],
    tags=["Store · Management"]
)

store_retrieve_schema = extend_schema(
    operation_id="store_retrieve",
    summary="جزئیات فروشگاه",
    description="دریافت جزئیات کامل یک فروشگاه خاص",
    responses={
        200: OpenApiResponse(
            response=StoreSerializer,
            description="جزئیات فروشگاه با موفقیت دریافت شد"
        ),
        404: OpenApiResponse(description="فروشگاه یافت نشد"),
        401: OpenApiResponse(description="احراز هویت نشده"),
        403: OpenApiResponse(description="دسترسی مجاز نیست"),
    },
    tags=["Store · Management"]
)

store_update_schema = extend_schema(
    operation_id="store_update",
    summary="ویرایش فروشگاه",
    description="ویرایش اطلاعات فروشگاه (وضعیت به حالت انتظار تغییر می‌کند)",
    request=StoreSerializer,
    responses={
        200: OpenApiResponse(
            response=StoreSerializer,
            description="فروشگاه با موفقیت ویرایش شد"
        ),
        400: OpenApiResponse(description="داده‌های ورودی نامعتبر"),
        404: OpenApiResponse(description="فروشگاه یافت نشد"),
        401: OpenApiResponse(description="احراز هویت نشده"),
        403: OpenApiResponse(description="دسترسی مجاز نیست یا فروشگاه قابل ویرایش نیست"),
    },
    examples=[
        OpenApiExample(
            "Store Update Example",
            summary="مثال ویرایش فروشگاه",
            description="نمونه داده برای ویرایش فروشگاه",
            value={
                "name": "فروشگاه ویرایش شده",
                "address": "تهران، خیابان انقلاب",
                "longitude": "51.4000",
                "latitude": "35.7000",
                "website_url": "https://updated-store.com",
            },
            request_only=True,
        )
    ],
    tags=["Store · Management"]
)

store_delete_schema = extend_schema(
    operation_id="store_delete",
    summary="حذف فروشگاه",
    description="حذف یک فروشگاه از سیستم",
    responses={
        204: OpenApiResponse(description="فروشگاه با موفقیت حذف شد"),
        404: OpenApiResponse(description="فروشگاه یافت نشد"),
        401: OpenApiResponse(description="احراز هویت نشده"),
        403: OpenApiResponse(description="دسترسی مجاز نیست"),
    },
    tags=["Store · Management"]
)


# Public Store Schemas
public_store_list_schema = extend_schema(
    operation_id="public_store_list",
    summary="لیست عمومی فروشگاه‌ها",
    description="دریافت لیست فروشگاه‌های تایید شده و فعال برای عموم با قابلیت صفحه‌بندی",
    parameters=[
        OpenApiParameter(
            name='page',
            type=int,
            location=OpenApiParameter.QUERY,
            description='شماره صفحه (پیش‌فرض: 1)',
            required=False,
        ),
        OpenApiParameter(
            name='page_size',
            type=int,
            location=OpenApiParameter.QUERY,
            description='تعداد آیتم در هر صفحه (پیش‌فرض: 20، حداکثر: 100)',
            required=False,
        ),
    ],
    responses={
        200: OpenApiResponse(
            response=PublicStoreSerializer(many=True),
            description="لیست فروشگاه‌های عمومی با موفقیت دریافت شد",
            examples=[
                OpenApiExample(
                    "Paginated Response",
                    summary="پاسخ صفحه‌بندی شده",
                    description="نمونه پاسخ با اطلاعات صفحه‌بندی",
                    value={
                        "count": 150,
                        "next": "http://example.com/api/v1/public-stores/?page=2",
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "name": "فروشگاه نمونه",
                                "address": "تهران، خیابان ولیعصر",
                                "longitude": "51.3890",
                                "latitude": "35.6892",
                                "website_url": "https://example-store.com",
                                "status": "active",
                                "status_display": "فعال",
                                "logo": "http://example.com/media/store_logos/store_1_abc123.jpg",
                                "rating": 82.5
                            }
                        ]
                    },
                    response_only=True,
                )
            ]
        ),
    },
    tags=["Store · Public"]
)

public_store_retrieve_schema = extend_schema(
    operation_id="public_store_retrieve",
    summary="جزئیات عمومی فروشگاه",
    description="دریافت جزئیات یک فروشگاه تایید شده برای عموم",
    responses={
        200: OpenApiResponse(
            response=PublicStoreSerializer,
            description="جزئیات فروشگاه با موفقیت دریافت شد"
        ),
        404: OpenApiResponse(description="فروشگاه یافت نشد یا غیرفعال است"),
    },
    tags=["Store · Public"]
)
