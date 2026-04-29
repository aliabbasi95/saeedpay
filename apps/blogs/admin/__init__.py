# apps/blogs/admin/__init__.py

from .article import ArticleAdmin
from .comment import CommentAdmin
from .tag import TagAdmin

__all__ = [
    "ArticleAdmin",
    "CommentAdmin",
    "TagAdmin",
]
