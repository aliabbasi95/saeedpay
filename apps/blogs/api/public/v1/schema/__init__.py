# blogs/api/public/v1/schema/__init__.py

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "article_viewset_schema",
    "comment_dislike_schema",
    "comment_like_schema",
    "comment_viewset_schema",
    "my_comments_schema",
    "orphaned_comments_schema",
    "tag_viewset_schema",
]

_MODULE_MAP = {
    "article_viewset_schema": (
        "blogs.api.public.v1.schema.article",
        "article_viewset_schema",
    ),
    "comment_viewset_schema": (
        "blogs.api.public.v1.schema.comment",
        "comment_viewset_schema",
    ),
    "comment_like_schema": (
        "blogs.api.public.v1.schema.comment",
        "comment_like_schema",
    ),
    "comment_dislike_schema": (
        "blogs.api.public.v1.schema.comment",
        "comment_dislike_schema",
    ),
    "my_comments_schema": (
        "blogs.api.public.v1.schema.comment",
        "my_comments_schema",
    ),
    "orphaned_comments_schema": (
        "blogs.api.public.v1.schema.comment",
        "orphaned_comments_schema",
    ),
    "tag_viewset_schema": (
        "blogs.api.public.v1.schema.tag",
        "tag_viewset_schema",
    ),
}

if TYPE_CHECKING:
    from .article import article_viewset_schema
    from .comment import (
        comment_dislike_schema,
        comment_like_schema,
        comment_viewset_schema,
        my_comments_schema,
        orphaned_comments_schema,
    )
    from .tag import tag_viewset_schema


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
