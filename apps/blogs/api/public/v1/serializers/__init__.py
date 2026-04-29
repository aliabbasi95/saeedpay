# apps/blogs/api/public/v1/serializers/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "ArticleDetailSerializer",
    "ArticleListSerializer",
    "ArticleSectionSerializer",
    "AuthorSerializer",
    "CommentAuthorSerializer",
    "CommentCreateSerializer",
    "CommentListSerializer",
    "CommentSerializer",
    "CommentUpdateSerializer",
    "TagListSerializer",
    "TagSerializer",
]

_MODULE_MAP = {
    "AuthorSerializer": (
        "apps.blogs.api.public.v1.serializers.article",
        "AuthorSerializer",
    ),
    "ArticleSectionSerializer": (
        "apps.blogs.api.public.v1.serializers.article",
        "ArticleSectionSerializer",
    ),
    "ArticleListSerializer": (
        "apps.blogs.api.public.v1.serializers.article",
        "ArticleListSerializer",
    ),
    "ArticleDetailSerializer": (
        "apps.blogs.api.public.v1.serializers.article",
        "ArticleDetailSerializer",
    ),
    "CommentAuthorSerializer": (
        "apps.blogs.api.public.v1.serializers.comment",
        "CommentAuthorSerializer",
    ),
    "CommentSerializer": (
        "apps.blogs.api.public.v1.serializers.comment",
        "CommentSerializer",
    ),
    "CommentListSerializer": (
        "apps.blogs.api.public.v1.serializers.comment",
        "CommentListSerializer",
    ),
    "CommentCreateSerializer": (
        "apps.blogs.api.public.v1.serializers.comment",
        "CommentCreateSerializer",
    ),
    "CommentUpdateSerializer": (
        "apps.blogs.api.public.v1.serializers.comment",
        "CommentUpdateSerializer",
    ),
    "TagSerializer": (
        "apps.blogs.api.public.v1.serializers.tag",
        "TagSerializer",
    ),
    "TagListSerializer": (
        "apps.blogs.api.public.v1.serializers.tag",
        "TagListSerializer",
    ),
}

if TYPE_CHECKING:
    from .article import (
        ArticleDetailSerializer,
        ArticleListSerializer,
        ArticleSectionSerializer,
        AuthorSerializer,
    )
    from .comment import (
        CommentAuthorSerializer,
        CommentCreateSerializer,
        CommentListSerializer,
        CommentSerializer,
        CommentUpdateSerializer,
    )
    from .tag import TagListSerializer, TagSerializer


def __getattr__(name: str) -> Any:
    try:
        module_path, attr_name = _MODULE_MAP[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_path)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)
