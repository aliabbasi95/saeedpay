# blogs/api/public/v1/schema.py
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
)
from drf_spectacular.types import OpenApiTypes

from blogs.models import Article


# Article ViewSet Schema
article_viewset_schema = extend_schema_view(
    list=extend_schema(
        summary="لیست مقالات",
        description="دریافت لیست مقالات منتشر شده با امکان فیلتر، جستجو و مرتب‌سازی",
        tags=["Articles"],
        parameters=[
            OpenApiParameter(
                name='tags',
                type={'type': 'array', 'items': {'type': 'integer'}},
                location=OpenApiParameter.QUERY,
                description='فیلتر بر اساس شناسه‌ی برچسب‌ها. می‌توانید چندین شناسه را به صورت `?tags=1&tags=2` ارسال کنید.',
                style='form',
                explode=True,
                examples=[
                    OpenApiExample(
                        "فیلتر یک برچسب",
                        value=[1],
                        summary="تک برچسب"
                    ),
                    OpenApiExample(
                        "فیلتر چند برچسب",
                        value=[1, 2, 3],
                        summary="چند برچسب"
                    ),
                ],
            ),
            OpenApiParameter(
                name="is_featured",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="فیلتر مقالات ویژه",
                examples=[
                    OpenApiExample(
                        "فقط مقالات ویژه",
                        value=True,
                    ),
                    OpenApiExample(
                        "فقط مقالات عادی",
                        value=False,
                    ),
                ],
            ),
            OpenApiParameter(
                name="status",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="فیلتر بر اساس وضعیت",
                enum=["draft", "published", "archived"],
                examples=[
                    OpenApiExample(
                        "فقط مقالات منتشر شده",
                        value="published",
                    ),
                ],
            ),
            OpenApiParameter(
                name="author",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="فیلتر بر اساس نویسنده",
                examples=[
                    OpenApiExample(
                        "مقالات نویسنده با ID 1",
                        value=1,
                    ),
                ],
            ),
            OpenApiParameter(
                name="published_after",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="مقالات منتشر شده بعد از تاریخ مشخص",
                examples=[
                    OpenApiExample(
                        "بعد از 1 ژانویه 2024",
                        value="2024-01-01T00:00:00Z",
                    ),
                ],
            ),
            OpenApiParameter(
                name="published_before",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description="مقالات منتشر شده قبل از تاریخ مشخص",
                examples=[
                    OpenApiExample(
                        "قبل از 31 دسامبر 2024",
                        value="2024-12-31T23:59:59Z",
                    ),
                ],
            ),
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="جستجو در عنوان، محتوا و خلاصه",
                examples=[
                    OpenApiExample(
                        "جستجوی کلمه کلیدی",
                        value="Django",
                    ),
                ],
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="مرتب‌سازی نتایج",
                examples=[
                    OpenApiExample(
                        "جدیدترین مقالات",
                        value="-created_at",
                    ),
                    OpenApiExample(
                        "پربازدیدترین مقالات",
                        value="-view_count",
                    ),
                    OpenApiExample(
                        "بر اساس تاریخ انتشار",
                        value="-published_at",
                    ),
                ],
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="لیست مقالات با موفقیت دریافت شد",
                examples=[
                    OpenApiExample(
                        "مثال پاسخ موفق",
                        value={
                            "count": 25,
                            "next": "http://example.com/api/blogs/public/v1/articles/?page=2",
                            "previous": None,
                            "results": [
                                {
                                    "id": 1,
                                    "title": "آموزش Django",
                                    "slug": "django-tutorial",
                                    "excerpt": "یادگیری Django از صفر تا صد",
                                    "featured_image": "/media/blog/articles/featured/django.jpg",
                                    "author": {
                                        "id": 1,
                                        "username": "admin",
                                        "first_name": "احمد",
                                        "last_name": "محمدی"
                                    },
                                    "tags": [
                                        {
                                            "id": 1,
                                            "name": "برنامه‌نویسی",
                                            "slug": "programming"
                                        }
                                    ],
                                    "is_featured": True,
                                    "view_count": 150,
                                    "published_at": "2024-01-15T10:30:00Z",
                                    "created_at": "2024-01-15T10:00:00Z"
                                }
                            ]
                        },
                    )
                ],
            ),
        },
    ),
    retrieve=extend_schema(
        summary="مشاهده جزئیات مقاله",
        description="دریافت جزئیات کامل یک مقاله با افزایش تعداد بازدید",
        tags=["Articles"],
        responses={
            200: OpenApiResponse(
                description="اطلاعات مقاله با موفقیت دریافت شد",
                examples=[
                    OpenApiExample(
                        "مثال پاسخ موفق",
                        value={
                            "id": 1,
                            "title": "آموزش Django",
                            "slug": "django-tutorial",
                            "content": "محتوای کامل مقاله با تصاویر...",
                            "rendered_content": "محتوای رندر شده با HTML تصاویر",
                            "excerpt": "یادگیری Django از صفر تا صد",
                            "featured_image": "/media/blog/articles/featured/django.jpg",
                            "author": {
                                "id": 1,
                                "username": "admin",
                                "first_name": "احمد",
                                "last_name": "محمدی"
                            },
                            "tags": [
                                {
                                    "id": 1,
                                    "name": "برنامه‌نویسی",
                                    "slug": "programming",
                                    "color": "#007bff"
                                }
                            ],
                            "images": [
                                {
                                    "id": 1,
                                    "title": "تصویر اول",
                                    "image": "/media/blog/articles/images/image1.jpg",
                                    "alt_text": "توضیح تصویر",
                                    "order": 1
                                }
                            ],
                            "is_featured": True,
                            "view_count": 151,
                            "published_at": "2024-01-15T10:30:00Z",
                            "created_at": "2024-01-15T10:00:00Z",
                            "updated_at": "2024-01-15T12:00:00Z"
                        },
                    )
                ],
            ),
            404: OpenApiResponse(description="مقاله یافت نشد"),
        },
    ),
)


# Tag ViewSet Schema
tag_viewset_schema = extend_schema_view(
    list=extend_schema(
        summary="لیست برچسب‌ها",
        description="دریافت لیست تمام برچسب‌های فعال",
        tags=["Tags"],
        parameters=[
            OpenApiParameter(
                name="search",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="جستجو در نام برچسب",
                examples=[
                    OpenApiExample(
                        "جستجوی برچسب",
                        value="برنامه‌نویسی",
                    ),
                ],
            ),
            OpenApiParameter(
                name="is_active",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="فیلتر برچسب‌های فعال",
                examples=[
                    OpenApiExample(
                        "فقط برچسب‌های فعال",
                        value=True,
                    ),
                ],
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="لیست برچسب‌ها با موفقیت دریافت شد",
                examples=[
                    OpenApiExample(
                        "مثال پاسخ موفق",
                        value=[
                            {
                                "id": 1,
                                "name": "برنامه‌نویسی",
                                "slug": "programming",
                                "description": "مقالات مربوط به برنامه‌نویسی",
                                "color": "#007bff",
                                "article_count": 15
                            }
                        ],
                    )
                ],
            ),
        },
    ),
    retrieve=extend_schema(
        summary="جزئیات برچسب",
        description="دریافت جزئیات یک برچسب خاص",
        tags=["Tags"],
        responses={
            200: OpenApiResponse(
                description="اطلاعات برچسب با موفقیت دریافت شد",
                examples=[
                    OpenApiExample(
                        "مثال پاسخ موفق",
                        value={
                            "id": 1,
                            "name": "برنامه‌نویسی",
                            "slug": "programming",
                            "description": "مقالات مربوط به برنامه‌نویسی",
                            "color": "#007bff",
                            "article_count": 15,
                            "is_active": True
                        },
                    )
                ],
            ),
            404: OpenApiResponse(description="برچسب یافت نشد"),
        },
    ),
)


# Comment ViewSet Schema
comment_viewset_schema = extend_schema_view(
    list=extend_schema(
        summary="لیست نظرات",
        description="دریافت لیست نظرات تایید شده",
        tags=["Comments"],
        parameters=[
            OpenApiParameter(
                name="article",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="فیلتر بر اساس مقاله",
                examples=[
                    OpenApiExample(
                        "نظرات مقاله با ID 1",
                        value=1,
                    ),
                ],
            ),
            OpenApiParameter(
                name="reply_to",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="فیلتر بر اساس شناسه نظر مرجع (برای دریافت پاسخ‌ها)",
                examples=[
                    OpenApiExample(
                        "نظرات اصلی (بدون پاسخ به نظر دیگر)",
                        value="null",
                    ),
                ],
            ),
        ],
        responses={
            200: OpenApiResponse(
                description="لیست نظرات با موفقیت دریافت شد",
                examples=[
                    OpenApiExample(
                        "مثال پاسخ موفق",
                        value={
                            "count": 10,
                            "results": [
                                {
                                    "id": 1,
                                    "content": "نظر بسیار مفیدی بود",
                                    "author": {
                                        "id": 1,
                                        "username": "user1",
                                        "first_name": "علی"
                                    },
                                    "article": 1,
                                    "reply_to": None,
                                    "replies": [
                                        {
                                            "id": 2,
                                            "content": "متشکرم از نظرتان",
                                            "author": {
                                                "id": 2,
                                                "username": "author"
                                            },
                                            "reply_to": 1,
                                        }
                                    ],
                                    "like_count": 5,
                                    "dislike_count": 0,
                                    "is_approved": True,
                                    "created_at": "2024-01-15T10:30:00Z"
                                }
                            ]
                        },
                    )
                ],
            ),
        },
    ),
    create=extend_schema(
        summary="ایجاد نظر جدید",
        description="ایجاد یک نظر جدید (نیاز به تایید مدیر)",
        tags=["Comments"],
        responses={
            201: OpenApiResponse(
                description="نظر با موفقیت ایجاد شد",
                examples=[
                    OpenApiExample(
                        "مثال پاسخ موفق",
                        value={
                            "id": 1,
                            "content": "نظر جدید",
                            "article": 1,
                            "reply_to": None,
                            "is_approved": False,
                            "created_at": "2024-01-15T10:30:00Z"
                        },
                    )
                ],
            ),
            400: OpenApiResponse(description="خطا در داده‌های ورودی"),
            401: OpenApiResponse(description="احراز هویت مورد نیاز است"),
        },
    ),
    my_comments=extend_schema(
        summary="نظرات من",
        description="دریافت لیست نظرات کاربر جاری",
        tags=["Comments"],
        responses={
            200: OpenApiResponse(description="لیست نظرات کاربر با موفقیت دریافت شد"),
            401: OpenApiResponse(description="احراز هویت مورد نیاز است"),
        },
    ),
    article_comments=extend_schema(
        summary="نظرات مقاله",
        description="دریافت نظرات یک مقاله خاص با پاسخ‌ها",
        tags=["Comments"],
        parameters=[
            OpenApiParameter(
                name="article_id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="شناسه مقاله",
                required=True,
                examples=[
                    OpenApiExample(
                        "نظرات مقاله با ID 1",
                        value=1,
                    ),
                ],
            ),
        ],
        responses={
            200: OpenApiResponse(description="نظرات مقاله با موفقیت دریافت شد"),
            400: OpenApiResponse(description="شناسه مقاله مورد نیاز است"),
        },
    ),
    like=extend_schema(
        summary="پسندیدن نظر",
        description="افزایش شمارنده پسند (like) برای یک نظر",
        tags=["Comments"],
        responses={
            200: OpenApiResponse(
                description="شمارنده‌های نظر به‌روزرسانی شد",
                examples=[
                    OpenApiExample(
                        "مثال پاسخ موفق",
                        value={
                            "id": 1,
                            "like_count": 6,
                            "dislike_count": 0,
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description="احراز هویت مورد نیاز است"),
            404: OpenApiResponse(description="نظر یافت نشد"),
        },
    ),
    dislike=extend_schema(
        summary="نپسندیدن نظر",
        description="افزایش شمارنده نپسند (dislike) برای یک نظر",
        tags=["Comments"],
        responses={
            200: OpenApiResponse(
                description="شمارنده‌های نظر به‌روزرسانی شد",
                examples=[
                    OpenApiExample(
                        "مثال پاسخ موفق",
                        value={
                            "id": 1,
                            "like_count": 6,
                            "dislike_count": 1,
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description="احراز هویت مورد نیاز است"),
            404: OpenApiResponse(description="نظر یافت نشد"),
        },
    ),
)
