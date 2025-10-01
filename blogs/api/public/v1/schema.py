# blogs/api/public/v1/schema.py

from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
    OpenApiExample,
)

from blogs.api.public.v1.serializers import (
    ArticleListSerializer,
    ArticleDetailSerializer,
    CommentListSerializer,
    CommentSerializer,
)
from blogs.api.public.v1.serializers.tag import (
    TagSerializer,
    TagListSerializer,
)

# ---------- Article ----------
article_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=["Articles"],
        summary="List articles",
        description=(
            "List visible articles. Anonymous: published & published_at<=now. "
            "Authenticated: includes own drafts."
        ),
        responses={200: ArticleListSerializer(many=True)},
        examples=[OpenApiExample(
            "List",
            value=[{
                "id": 10, "title": "How to save money",
                "slug": "how-to-save-money",
                "author": {
                    "id": 2, "username": "author1", "full_name": "Sara Rezaei"
                },
                "excerpt": "Top tips to manage your budget…",
                "featured_image": "/media/articles/a1.jpg",
                "published_at": "2025-02-01T10:00:00Z"
            }]
        )],
    ),
    retrieve=extend_schema(
        tags=["Articles"],
        summary="Get article",
        parameters=[OpenApiParameter(
            name="slug", location=OpenApiParameter.PATH, type=str,
            description="Slug or numeric ID of the article"
        )],
        responses={
            200: ArticleDetailSerializer,
            404: OpenApiResponse(description="Article not found"),
        },
        examples=[OpenApiExample(
            "Detail",
            value={
                "id": 10, "title": "How to save money",
                "slug": "how-to-save-money",
                "author": {
                    "id": 2, "username": "author1", "full_name": "Sara Rezaei"
                },
                "rendered_content": "<h2>Intro</h2><p>...</p>",
                "excerpt": "Top tips to manage your budget…",
                "featured_image": "/media/articles/a1.jpg",
                "status": "published",
                "tags": [{
                    "id": 1, "name": "Finance", "slug": "finance",
                    "color": "#1769aa"
                }],
                "sections": [
                    {
                        "id": 1, "section_type": "text", "content": "Intro…",
                        "image": None, "image_alt": "", "order": 1
                    },
                    {
                        "id": 2, "section_type": "image", "content": None,
                        "image": "/media/articles/img1.jpg",
                        "image_alt": "chart", "order": 2
                    }
                ],
                "is_featured": False, "published_at": "2025-02-01T10:00:00Z",
                "view_count": 123, "comment_count": 4,
                "jalali_creation_date_time": "1403/11/12 14:12",
                "jalali_update_date_time": "1403/11/12 15:01",
                "comments": []
            }
        )],
    ),
)

# ---------- Comment ----------
comment_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=["Comments"],
        summary="List comments",
        description="List approved root comments for an article/store. Authenticated users also see their own.",
        responses={200: CommentListSerializer(many=True)},
        examples=[OpenApiExample(
            "List",
            value=[{
                "id": 101,
                "author": {
                    "id": 3, "username": "user12", "first_name": "Ali",
                    "last_name": "Karimi"
                },
                "content": "Great article!",
                "rating": 5, "reply_count": 2,
                "replies": [],
                "like_count": 8, "dislike_count": 1,
                "jalali_creation_date_time": "1403/11/12 14:20"
            }]
        )],
    ),
    retrieve=extend_schema(
        tags=["Comments"],
        summary="Get comment",
        responses={
            200: CommentSerializer,
            404: OpenApiResponse(description="Not found")
        },
    ),
    create=extend_schema(
        tags=["Comments"],
        summary="Create comment",
        responses={
            201: CommentSerializer,
            400: OpenApiResponse(description="Validation error")
        },
        examples=[OpenApiExample(
            "CreatePayload",
            request_only=True,
            value={
                "article": 10, "store": None, "reply_to": None,
                "content": "Nice!", "rating": 5
            }
        )],
    ),
    update=extend_schema(
        tags=["Comments"], summary="Update comment",
        responses={
            200: CommentSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Forbidden")
        },
    ),
    partial_update=extend_schema(
        tags=["Comments"], summary="Partially update comment",
        responses={
            200: CommentSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Forbidden")
        },
    ),
    destroy=extend_schema(
        tags=["Comments"], summary="Delete comment",
        responses={
            204: OpenApiResponse(description="Deleted"),
            403: OpenApiResponse(description="Forbidden")
        },
    ),
)

# Extra actions (comments)
comment_like_schema = extend_schema(
    tags=["Comments"], summary="Like a comment",
    responses={
        200: OpenApiResponse(
            description="Counters after like",
            examples=[OpenApiExample(
                "Counts",
                value={"id": 101, "like_count": 9, "dislike_count": 1}
            )]
        )
    }
)
comment_dislike_schema = extend_schema(
    tags=["Comments"], summary="Dislike a comment",
    responses={
        200: OpenApiResponse(
            description="Counters after dislike",
            examples=[OpenApiExample(
                "Counts",
                value={"id": 101, "like_count": 8, "dislike_count": 2}
            )]
        )
    }
)
my_comments_schema = extend_schema(
    tags=["Comments"], summary="My comments",
    responses={200: CommentSerializer(many=True)}
)
orphaned_comments_schema = extend_schema(
    tags=["Comments"], summary="Orphaned comments",
    parameters=[OpenApiParameter(
        name="ordering", location=OpenApiParameter.QUERY, type=str,
        description="created_at|-created_at|like_count|-like_count|dislike_count|-dislike_count"
    )],
    responses={200: CommentListSerializer(many=True)}
)

# ---------- Tag ----------
tag_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=["Tags"],
        summary="List tags",
        responses={200: TagListSerializer(many=True)},
        examples=[OpenApiExample(
            "List", value=[{
                "id": 1, "name": "Finance", "slug": "finance",
                "color": "#1769aa"
            }]
        )],
    ),
    retrieve=extend_schema(
        tags=["Tags"],
        summary="Get tag",
        responses={
            200: TagSerializer, 404: OpenApiResponse(description="Not found")
        },
        examples=[OpenApiExample(
            "Detail", value={
                "id": 1, "name": "Finance", "slug": "finance",
                "description": "Money & budgeting",
                "color": "#1769aa", "is_active": True, "article_count": 42
            }
        )],
    ),
)
