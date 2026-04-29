# chatbot/api/public/v1/serializers/chat.py

from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    query = serializers.CharField(
        max_length=1000,
        required=True,
        help_text="The message or question to send to the AI chatbot.",
    )


class ChatResponseSerializer(serializers.Serializer):
    answer = serializers.CharField(
        help_text="The AI chatbot's response to the user's query."
    )
