import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from chatbot.models import ChatSession
from .test_chat_api import api_client, auth_token, test_user

User = get_user_model()


@pytest.fixture
def user1(db):
    user = User(username="user1")
    user.set_password("password1")
    user.save()
    return user


@pytest.fixture
def user2(db):
    user = User(username="user2")
    user.set_password("password2")
    user.save()
    return user


@pytest.fixture
def client_user1(api_client, user1):
    api_client.force_authenticate(user=user1)
    return api_client


@pytest.fixture
def client_user2(api_client, user2):
    api_client.force_authenticate(user=user2)
    return api_client


@pytest.fixture
def anonymous_client1(api_client):
    return api_client


@pytest.fixture
def anonymous_client2(api_client):
    # Create a new, distinct APIClient for the second anonymous user
    return APIClient()


@pytest.fixture
def session_user1(db, user1):
    return ChatSession.objects.create(user=user1)


@pytest.fixture
def session_anonymous1(db):
    return ChatSession.objects.create(session_key="anon_key_1")


@pytest.mark.django_db
def test_authenticated_user_cannot_access_another_users_session_detail(
    client_user2, session_user1
):
    """
    Ensure an authenticated user cannot access the chat session details of another user.
    """
    url = reverse("chat_session_detail", kwargs={"session_id": session_user1.id})
    response = client_user2.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_anonymous_user_cannot_access_authenticated_users_session_detail(
    anonymous_client1, session_user1
):
    """
    Ensure an anonymous user cannot access the chat session details of an authenticated user.
    """
    url = reverse("chat_session_detail", kwargs={"session_id": session_user1.id})
    # Simulate session for the anonymous client
    session = anonymous_client1.session
    session["session_key"] = "any_key"
    session.save()
    response = anonymous_client1.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_authenticated_user_cannot_access_anonymous_users_session_detail(
    client_user1, session_anonymous1
):
    """
    Ensure an authenticated user cannot access the chat session details of an anonymous user.
    """
    url = reverse(
        "chat_session_detail",
        kwargs={"session_id": session_anonymous1.id},
    )
    response = client_user1.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_anonymous_user_cannot_access_another_anonymous_users_session_detail(
    anonymous_client2, session_anonymous1
):
    """
    Ensure an anonymous user cannot access the chat session details of another anonymous user.
    """
    url = reverse(
        "chat_session_detail",
        kwargs={"session_id": session_anonymous1.id},
    )
    # Simulate session for the second anonymous client
    session = anonymous_client2.session
    session["session_key"] = "anon_key_2"
    session.save()
    response = anonymous_client2.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_user_can_only_see_their_own_sessions_in_list(client_user1, user2, session_user1):
    """
    Ensure that the session list endpoint only returns sessions belonging to the authenticated user.
    """
    ChatSession.objects.create(user=user2)
    ChatSession.objects.create(session_key="some_other_key")

    url = reverse("user_chat_sessions")
    response = client_user1.get(url)
    assert response.status_code == 200
    assert len(response.data["sessions"]) == 1
    assert response.data["sessions"][0]["session_id"] == session_user1.id 