import pytest
from chatbot.serializers import ChatRequestSerializer
from django.conf import settings

@pytest.mark.django_db
def test_serializer_validation():
    data = {"query": "Hello"}
    serializer = ChatRequestSerializer(data=data)
    assert serializer.is_valid()
    serializer = ChatRequestSerializer(data={})
    assert not serializer.is_valid()
    assert "query" in serializer.errors 