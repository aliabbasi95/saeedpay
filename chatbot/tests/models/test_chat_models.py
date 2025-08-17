import pytest
from django.contrib.auth import get_user_model
from chatbot.models import ChatSession, ChatMessage


@pytest.mark.django_db
def test_placeholder():
    # Add model tests for chatbot app here
    assert True


@pytest.mark.django_db
def test_create_chat_session_and_message():
    User = get_user_model()
    user = User.objects.create(username="testuser")
    session = ChatSession.objects.create(
        user=user, session_key="abc123", ip_address="127.0.0.1"
    )
    msg = ChatMessage.objects.create(
        session=session, sender="user", message="Hello, world!"
    )
    assert msg.session == session
    assert msg.sender == "user"
    assert msg.message == "Hello, world!"
    assert str(session).startswith(f"ChatSession #{session.pk}")
    assert str(msg).startswith("user @")
