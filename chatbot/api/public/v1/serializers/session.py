from rest_framework import serializers
from chatbot.models.session import ChatSession


class ChatSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatSession
        fields = [
            "id",
            "user",
            "session_key",
            "ip_address",
            "is_active",
            "created_at",
            "last_activity",
        ]
        read_only_fields = ["id", "created_at", "last_activity"]
