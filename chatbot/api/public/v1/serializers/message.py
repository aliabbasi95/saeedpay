from rest_framework import serializers
from chatbot.models.message import ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "session",
            "sender",
            "message",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
