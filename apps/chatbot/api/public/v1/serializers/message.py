# chatbot/api/public/v1/serializers/message.py

from rest_framework import serializers

from chatbot.models.message import ChatMessage


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "sender",
            "message",
            "created_at",
        ]
        read_only_fields = fields
