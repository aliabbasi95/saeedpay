# blogs/api/public/v1/schema/tag.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from blogs.api.public.v1.serializers import TagListSerializer, TagSerializer

tag_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=["Blogs · Tags"],
        summary="List tags",
        responses={200: TagListSerializer(many=True)},
        examples=[
            OpenApiExample(
                "List",
                value=[
                    {"id": 1, "name": "Finance", "slug": "finance", "color": "#1769aa"}
                ],
            )
        ],
    ),
    retrieve=extend_schema(
        tags=["Blogs · Tags"],
        summary="Retrieve a tag",
        responses={
            200: TagSerializer,
            404: OpenApiResponse(description="Tag not found."),
        },
        examples=[
            OpenApiExample(
                "Detail",
                value={
                    "id": 1,
                    "name": "Finance",
                    "slug": "finance",
                    "description": "Money & budgeting",
                    "color": "#1769aa",
                    "is_active": True,
                    "article_count": 42,
                },
            )
        ],
    ),
)
