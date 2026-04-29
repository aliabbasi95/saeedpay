# apps/blogs/api/public/v1/urls.py

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.blogs.api.public.v1.views import (
    ArticleViewSet,
    CommentViewSet,
    TagViewSet,
)

router = DefaultRouter()
router.register(r"articles", ArticleViewSet, basename="article")
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"comments", CommentViewSet, basename="comment")

urlpatterns = [
    path("", include(router.urls)),
]
