# apps/blogs/api/public/v1/schema/article.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from apps.blogs.api.public.v1.serializers import (
    ArticleDetailSerializer,
    ArticleListSerializer,
)

ARTICLES_TAG = "Content · Articles"

article_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=[ARTICLES_TAG],
        summary="List articles",
        description=(
            "List visible articles. Anonymous users only see published articles with "
            "a publish date in the past. Authenticated users may also see their own drafts."
        ),
        responses={200: ArticleListSerializer(many=True)},
        examples=[
            OpenApiExample(
                "List",
                value=[
                    {
                        "id": 10,
                        "title": "How to save money",
                        "slug": "how-to-save-money",
                        "author": {
                            "id": 2,
                            "username": "author1",
                            "full_name": "Sara Rezaei",
                        },
                        "excerpt": "Top tips to manage your budget…",
                        "featured_image": "/media/articles/a1.jpg",
                        "published_at": "2025-02-01T10:00:00Z",
                    }
                ],
            )
        ],
    ),
    retrieve=extend_schema(
        tags=[ARTICLES_TAG],
        summary="Retrieve an article",
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=str,
                description="Article slug or numeric ID.",
            )
        ],
        responses={
            200: ArticleDetailSerializer,
            404: OpenApiResponse(description="Article not found."),
        },
        examples=[
            OpenApiExample(
                "Detail",
                value={
                    "id": 10,
                    "title": "How to save money",
                    "slug": "how-to-save-money",
                    "author": {
                        "id": 2,
                        "username": "author1",
                        "full_name": "Sara Rezaei",
                    },
                    "rendered_content": "<h2>Intro</h2><p>...</p>",
                    "excerpt": "Top tips to manage your budget…",
                    "featured_image": "/media/articles/a1.jpg",
                    "status": "published",
                    "tags": [
                        {
                            "id": 1,
                            "name": "Finance",
                            "slug": "finance",
                            "color": "#1769aa",
                        }
                    ],
                    "sections": [
                        {
                            "id": 1,
                            "section_type": "text",
                            "content": "Intro…",
                            "image": None,
                            "image_alt": "",
                            "order": 1,
                        },
                        {
                            "id": 2,
                            "section_type": "image",
                            "content": None,
                            "image": "/media/articles/img1.jpg",
                            "image_alt": "chart",
                            "order": 2,
                        },
                    ],
                    "is_featured": False,
                    "published_at": "2025-02-01T10:00:00Z",
                    "view_count": 123,
                    "comment_count": 4,
                    "jalali_creation_date_time": "1403/11/12 14:12",
                    "jalali_update_date_time": "1403/11/12 15:01",
                    "comments": [],
                },
            )
        ],
    ),
)
