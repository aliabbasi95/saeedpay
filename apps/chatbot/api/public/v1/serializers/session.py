# chatbot/api/public/v1/serializers/session.py

from drf_spectacular.utils import OpenApiTypes, extend_schema_field
from rest_framework import serializers

from chatbot.api.public.v1.serializers.message import ChatMessageSerializer
from chatbot.models.session import ChatSession


class ChatSessionSerializer(serializers.ModelSerializer):
    last_activity_at = serializers.SerializerMethodField(read_only=True)

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_last_activity_at(self, obj):
        return getattr(obj, "last_msg_at", None) or getattr(
            obj, "last_message_at", None
        )

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "user",
            "session_key",
            "ip_address",
            "is_active",
            "created_at",
            "last_activity_at",
        ]
        read_only_fields = fields


class ChatSessionDetailSerializer(serializers.ModelSerializer):
    last_activity_at = serializers.SerializerMethodField(read_only=True)
    messages = serializers.SerializerMethodField(read_only=True)

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_last_activity_at(self, obj):
        return getattr(obj, "last_msg_at", None) or getattr(
            obj, "last_message_at", None
        )

    @extend_schema_field(ChatMessageSerializer(many=True))
    def get_messages(self, obj):
        return ChatMessageSerializer(obj.messages.all(), many=True).data

    class Meta:
        model = ChatSession
        fields = [
            "id",
            "created_at",
            "is_active",
            "last_activity_at",
            "messages",
        ]
        read_only_fields = fields
