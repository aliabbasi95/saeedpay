# chatbot/tests/public/v1/views/test_chat_api.py


import pytest
from django.conf import settings
from django.urls import reverse

from chatbot.models import ChatSession


@pytest.mark.django_db
def test_anonymous_user_message_limit(api_client):
    url = reverse("chatbot_public_v1:chat-session-list")
    response = api_client.post(url)
    assert response.status_code == 201
    session_id = response.data["id"]
    chat_url = reverse("chatbot_public_v1:chat-session-chat", args=[session_id])
    for i in range(settings.CHATBOT_HISTORY_LIMIT):
        resp = api_client.post(chat_url, {"query": f"msg {i}"}, format="json")
        assert resp.status_code == 200
    resp = api_client.post(chat_url, {"query": "msg extra"}, format="json")
    assert resp.status_code == 403
    assert (
        f"limited to {settings.CHATBOT_HISTORY_LIMIT} messages" in resp.data["detail"]
    )


@pytest.mark.django_db
def test_anonymous_user_limit_exactly_limit(api_client):
    url = reverse("chatbot_public_v1:chat-session-list")
    response = api_client.post(url)
    session_id = response.data["id"]
    chat_url = reverse("chatbot_public_v1:chat-session-chat", args=[session_id])
    for i in range(settings.CHATBOT_HISTORY_LIMIT - 1):
        resp = api_client.post(chat_url, {"query": f"msg {i}"}, format="json")
        assert resp.status_code == 200
    resp = api_client.post(
        chat_url, {"query": f"msg {settings.CHATBOT_HISTORY_LIMIT - 1}"}, format="json"
    )
    assert resp.status_code == 200
    resp = api_client.post(chat_url, {"query": "msg extra"}, format="json")
    assert resp.status_code == 403
    assert (
        f"limited to {settings.CHATBOT_HISTORY_LIMIT} messages" in resp.data["detail"]
    )


@pytest.mark.django_db
def test_anonymous_user_limit_resets_new_session(api_client):
    url = reverse("chatbot_public_v1:chat-session-list")
    response1 = api_client.post(url)
    session_id1 = response1.data["id"]
    chat_url1 = reverse("chatbot_public_v1:chat-session-chat", args=[session_id1])
    for i in range(settings.CHATBOT_HISTORY_LIMIT):
        resp = api_client.post(chat_url1, {"query": f"msg {i}"}, format="json")
        assert resp.status_code == 200
    response2 = api_client.post(url)
    session_id2 = response2.data["id"]
    chat_url2 = reverse("chatbot_public_v1:chat-session-chat", args=[session_id2])
    resp = api_client.post(chat_url2, {"query": "first message"}, format="json")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_authenticated_user_unlimited_messages(api_client, auth_token):
    token, user = auth_token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    url = reverse("chatbot_public_v1:chat-session-list")
    response = api_client.post(url)
    session_id = response.data["id"]
    chat_url = reverse("chatbot_public_v1:chat-session-chat", args=[session_id])
    for i in range(settings.CHATBOT_HISTORY_LIMIT * 2):  # unlimited for auth user
        resp = api_client.post(chat_url, {"query": f"msg {i}"}, format="json")
        assert resp.status_code == 200


@pytest.mark.django_db
def test_message_history(api_client):
    url = reverse("chatbot_public_v1:chat-session-list")
    response = api_client.post(url)
    session_id = response.data["id"]
    chat_url = reverse("chatbot_public_v1:chat-session-chat", args=[session_id])
    # Send more messages than the history limit
    for i in range(settings.CHATBOT_HISTORY_LIMIT + 2):
        api_client.post(chat_url, {"query": f"msg {i}"}, format="json")
    detail_url = reverse("chatbot_public_v1:chat-session-detail", args=[session_id])
    resp = api_client.get(detail_url)
    assert resp.status_code == 200
    assert "messages" in resp.data
    assert len(resp.data["messages"]) == settings.CHATBOT_HISTORY_LIMIT * 2


@pytest.mark.django_db
def test_cannot_access_other_users_sessions(api_client, auth_token):
    token, user = auth_token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    url = reverse("chatbot_public_v1:chat-session-list")
    response = api_client.post(url)
    session_id = response.data["id"]
    api_client.credentials()  # Remove auth
    detail_url = reverse("chatbot_public_v1:chat-session-detail", args=[session_id])
    resp = api_client.get(detail_url)
    assert resp.status_code in (403, 404)
    chat_url = reverse("chatbot_public_v1:chat-session-chat", args=[session_id])
    resp = api_client.post(chat_url, {"query": "hack"}, format="json")
    assert resp.status_code in (403, 404)


@pytest.mark.django_db
def test_session_key_isolation(api_client):
    url = reverse("chatbot_public_v1:chat-session-list")
    resp1 = api_client.post(url)
    resp2 = api_client.post(url)
    session_id1 = resp1.data["id"]
    session_id2 = resp2.data["id"]
    chat_url1 = reverse("chatbot_public_v1:chat-session-chat", args=[session_id1])
    chat_url2 = reverse("chatbot_public_v1:chat-session-chat", args=[session_id2])
    api_client.post(chat_url1, {"query": "msg1"}, format="json")
    api_client.post(chat_url2, {"query": "msg2"}, format="json")
    detail_url1 = reverse("chatbot_public_v1:chat-session-detail", args=[session_id1])
    detail_url2 = reverse("chatbot_public_v1:chat-session-detail", args=[session_id2])
    resp1 = api_client.get(detail_url1)
    resp2 = api_client.get(detail_url2)
    assert "msg1" in str(resp1.data)
    assert "msg2" in str(resp2.data)


@pytest.mark.django_db
def test_authenticated_user_session_list(api_client, auth_token):
    token, user = auth_token
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    url = reverse("chatbot_public_v1:chat-session-list")
    session_ids = []
    for _ in range(3):
        resp = api_client.post(url)
        session_ids.append(resp.data["id"])
    list_url = reverse("chatbot_public_v1:chat-session-list")
    resp = api_client.get(list_url)
    assert resp.status_code == 200
    returned_ids = [s.get("session_id", s.get("id")) for s in resp.data]
    for sid in session_ids:
        assert sid in returned_ids


@pytest.mark.django_db
def test_anonymous_user_session_list_isolated(api_client):
    url = reverse("chatbot_public_v1:chat-session-list")
    resp1 = api_client.post(url)
    resp2 = api_client.post(url)
    session_id1 = resp1.data["id"]
    session_id2 = resp2.data["id"]
    list_url = reverse("chatbot_public_v1:chat-session-list")
    resp = api_client.get(list_url)
    assert resp.status_code == 200
    session_ids = [s.get("session_id", s.get("id")) for s in resp.data]
    assert session_id1 in session_ids or session_id2 in session_ids


@pytest.mark.django_db
def test_access_after_session_delete(api_client):
    url = reverse("chatbot_public_v1:chat-session-list")
    resp = api_client.post(url)
    session_id = resp.data["id"]
    chat_url = reverse("chatbot_public_v1:chat-session-chat", args=[session_id])
    ChatSession.objects.filter(id=session_id).delete()
    resp = api_client.post(chat_url, {"query": "msg after delete"}, format="json")
    assert resp.status_code in (403, 404)
