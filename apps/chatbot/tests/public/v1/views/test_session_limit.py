# apps/chatbot/tests/public/v1/views/test_session_limit.py

import pytest
from django.conf import settings
from django.urls import reverse

# api_client fixture and related helpers are defined in test_chat_api.py


# Anonymous users should be limited to this many chat sessions (default 2)
SESSION_LIMIT = getattr(settings, "CHATBOT_SESSION_LIMIT", 2)


@pytest.mark.django_db
def test_anonymous_user_session_creation_limit(api_client):
    """Anonymous user can only create up to SESSION_LIMIT chat sessions."""
    url = reverse("chatbot_public_v1:chat-session-list")
    created_ids = []

    # Create sessions up to the limit – all should succeed.
    for _ in range(SESSION_LIMIT):
        resp = api_client.post(url)
        assert resp.status_code == 201
        created_ids.append(resp.data["id"])

    # Attempt to create one more session – should be forbidden.
    resp = api_client.post(url)
    assert resp.status_code == 403
    assert "limited" in resp.data["detail"].lower()

    # Verify the session list only returns the allowed number of sessions.
    list_url = reverse("chatbot_public_v1:chat-session-list")
    list_resp = api_client.get(list_url)
    assert list_resp.status_code == 200
    sessions = (
        list_resp.data["sessions"]
        if isinstance(list_resp.data, dict) and "sessions" in list_resp.data
        else list_resp.data
    )

    assert len(sessions) == SESSION_LIMIT


@pytest.mark.django_db
def test_anonymous_user_can_access_existing_sessions_after_limit(api_client):
    """Reaching the creation limit must NOT block access to already created sessions."""
    url = reverse("chatbot_public_v1:chat-session-list")
    session_ids = [api_client.post(url).data["id"] for _ in range(SESSION_LIMIT)]
    # Hit the limit
    api_client.post(url)

    # Access detail for each existing session – should be allowed.
    for sid in session_ids:
        detail_url = reverse("chatbot_public_v1:chat-session-detail", args=[sid])
        resp = api_client.get(detail_url)
        assert resp.status_code == 200
        returned = resp.data.get("session_id") or resp.data.get("id")
        assert returned == sid


@pytest.mark.django_db
def test_authenticated_user_unlimited_session_creation(api_client, auth_token):
    """Authenticated users are not subject to the anonymous session limit."""
    token, _ = auth_token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    url = reverse("chatbot_public_v1:chat-session-list")

    for _ in range(SESSION_LIMIT + 3):  # create more than the anonymous limit
        resp = api_client.post(url)
        assert resp.status_code == 201
