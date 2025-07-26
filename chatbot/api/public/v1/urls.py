from django.urls import path
from .views import (
    StartChatView,
    ChatView,
    UserChatSessionsView,
    ChatSessionDetailView,
)

urlpatterns = [
    path("start/", StartChatView.as_view(), name="start_chat"),
    path("chat/<int:session_id>/", ChatView.as_view(), name="chat"),
    path(
        "sessions/", UserChatSessionsView.as_view(), name="user_chat_sessions"
    ),
    path(
        "sessions/<int:session_id>/",
        ChatSessionDetailView.as_view(),
        name="chat_session_detail",
    ),
]
