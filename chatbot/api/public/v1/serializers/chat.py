from rest_framework import serializers


class ChatRequestSerializer(serializers.Serializer):
    """
    Serializer for chat request containing the user's message/query
    """

    query = serializers.CharField(
        max_length=1000,
        help_text="The message or question to send to the AI chatbot",
        required=True,
    )


class ChatResponseSerializer(serializers.Serializer):
    """
    Serializer for chat response containing the AI's answer
    """

    answer = serializers.CharField(
        help_text="The AI chatbot's response to the user's query"
    )
