from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


class DummyLLMResponse:
    def __init__(self, payload=None, text="pong", status_code=200):
        self._payload = payload if payload is not None else {"answer": "pong"}
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def mock_llm_requests_post():
    """
    Patch the exact requests.post imported/used by:
      chatbot/api/v1/views/session.py

    This prevents real network calls to localhost:8001 during tests.
    """
    with patch(
        "chatbot.api.public.v1.views.session.requests.post",
        return_value=DummyLLMResponse({"answer": "pong"}),
    ):
        yield


@pytest.fixture
def test_user(db):
    User = get_user_model()
    username = getattr(settings, "TEST_CHATBOT_USERNAME", "09149257695")
    password = getattr(settings, "TEST_CHATBOT_PASSWORD", "kuaghyA8921347@")
    user, _ = User.objects.get_or_create(username=username)
    user.set_password(password)
    user.save()
    return user, password


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_token(api_client, test_user):
    user, password = test_user
    url = reverse("auth_api_public_v1:auth-login")
    response = api_client.post(
        url, {"phone_number": user.username, "password": password}
    )
    assert response.status_code == 200
    return response.data["access"], user
