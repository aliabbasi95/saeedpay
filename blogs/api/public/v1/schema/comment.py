# blogs/api/public/v1/schema/comment.py

from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)

from blogs.api.public.v1.serializers import CommentListSerializer, CommentSerializer

COMMENTS_TAG = "Content · Comments"

comment_viewset_schema = extend_schema_view(
    list=extend_schema(
        tags=[COMMENTS_TAG],
        summary="List comments",
        description=(
            "List approved root comments for an article or store. Authenticated users "
            "also see their own comments."
        ),
        responses={200: CommentListSerializer(many=True)},
        examples=[
            OpenApiExample(
                "List",
                value=[
                    {
                        "id": 101,
                        "author": {
                            "id": 3,
                            "username": "user12",
                            "first_name": "Ali",
                            "last_name": "Karimi",
                        },
                        "content": "Great article!",
                        "rating": 5,
                        "reply_count": 2,
                        "replies": [],
                        "like_count": 8,
                        "dislike_count": 1,
                        "jalali_creation_date_time": "1403/11/12 14:20",
                    }
                ],
            )
        ],
    ),
    retrieve=extend_schema(
        tags=[COMMENTS_TAG],
        summary="Retrieve a comment",
        responses={
            200: CommentSerializer,
            404: OpenApiResponse(description="Comment not found."),
        },
    ),
    create=extend_schema(
        tags=[COMMENTS_TAG],
        summary="Create a comment",
        responses={
            201: CommentSerializer,
            400: OpenApiResponse(description="Validation error."),
        },
        examples=[
            OpenApiExample(
                "CreatePayload",
                request_only=True,
                value={
                    "article": 10,
                    "store": None,
                    "reply_to": None,
                    "content": "Nice!",
                    "rating": 5,
                },
            )
        ],
    ),
    update=extend_schema(
        tags=[COMMENTS_TAG],
        summary="Update a comment",
        responses={
            200: CommentSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden."),
        },
    ),
    partial_update=extend_schema(
        tags=[COMMENTS_TAG],
        summary="Partially update a comment",
        responses={
            200: CommentSerializer,
            400: OpenApiResponse(description="Validation error."),
            403: OpenApiResponse(description="Forbidden."),
        },
    ),
    destroy=extend_schema(
        tags=[COMMENTS_TAG],
        summary="Delete a comment",
        responses={
            204: OpenApiResponse(description="Deleted."),
            403: OpenApiResponse(description="Forbidden."),
        },
    ),
)

comment_like_schema = extend_schema(
    tags=[COMMENTS_TAG],
    summary="Like a comment",
    responses={
        200: OpenApiResponse(
            description="Updated counters after liking a comment.",
            examples=[
                OpenApiExample(
                    "Counts",
                    value={"id": 101, "like_count": 9, "dislike_count": 1},
                )
            ],
        )
    },
)

comment_dislike_schema = extend_schema(
    tags=[COMMENTS_TAG],
    summary="Dislike a comment",
    responses={
        200: OpenApiResponse(
            description="Updated counters after disliking a comment.",
            examples=[
                OpenApiExample(
                    "Counts",
                    value={"id": 101, "like_count": 8, "dislike_count": 2},
                )
            ],
        )
    },
)

my_comments_schema = extend_schema(
    tags=[COMMENTS_TAG],
    summary="List my comments",
    responses={200: CommentSerializer(many=True)},
)

orphaned_comments_schema = extend_schema(
    tags=[COMMENTS_TAG],
    summary="List orphaned comments",
    parameters=[
        OpenApiParameter(
            name="ordering",
            location=OpenApiParameter.QUERY,
            type=str,
            description=(
                "created_at|-created_at|like_count|-like_count|"
                "dislike_count|-dislike_count"
            ),
        )
    ],
    responses={200: CommentListSerializer(many=True)},
)
