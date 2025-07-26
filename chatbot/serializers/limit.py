from rest_framework import serializers
from chatbot.models.limit import ChatLimit


class ChatLimitSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatLimit
        fields = [
            "id",
            "session_key",
            "date",
            "message_count",
            "max_messages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
