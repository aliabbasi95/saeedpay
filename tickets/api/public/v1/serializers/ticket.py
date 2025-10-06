# tickets/api/public/v1/serializers/ticket.py

from typing import List

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from tickets.models import (
    Ticket, TicketMessage, TicketMessageAttachment,
    TicketCategory,
)

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "application/pdf",
    "text/plain",
}
MAX_ATTACHMENT_COUNT = 2
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024  # 5 MB


class TicketCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketCategory
        fields = ["id", "name", "description", "icon", "color"]


class TicketSerializer(serializers.ModelSerializer):
    category = TicketCategorySerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "title",
            "status",
            "priority",
            "category",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "created_at", "updated_at"]


class TicketCreateSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField()
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=TicketCategory.objects.all(),
        source="category",
        help_text="شناسه دسته‌بندی تیکت",
    )
    description = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text="شرح مشکل که به عنوان اولین پیام تیکت ذخیره می‌شود",
    )

    class Meta:
        model = Ticket
        fields = ["id", "title", "description", "priority", "category_id"]

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            raise serializers.ValidationError(
                {"non_field_errors": [_("کاربر احراز نشده است.")]}
            )
        open_statuses = [
            Ticket.Status.OPEN,
            Ticket.Status.IN_PROGRESS,
            Ticket.Status.WAITING_ON_USER,
            Ticket.Status.REOPENED,
        ]
        open_count = Ticket.objects.filter(
            user=user, status__in=open_statuses
        ).count()
        if open_count >= 15:
            raise serializers.ValidationError(
                {"non_field_errors": [_("شما بیش از ۱۵ تیکت باز دارید.")]}
            )
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        description = validated_data.pop("description", None)

        ticket = Ticket.objects.create(user=user, **validated_data)

        if description:
            TicketMessage.objects.create(
                ticket=ticket,
                sender=TicketMessage.Sender.USER,
                content=description,
            )

        return ticket


class TicketMessageAttachmentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)
    filename = serializers.CharField(read_only=True)

    class Meta:
        model = TicketMessageAttachment
        fields = ["id", "filename", "file", "created_at"]


class TicketMessageSerializer(serializers.ModelSerializer):
    attachments = TicketMessageAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = TicketMessage
        fields = [
            "id",
            "ticket",
            "sender",
            "content",
            "reply_to",
            "attachments",
            "created_at",
            "updated_at",
        ]


class TicketMessageCreateSerializer(serializers.ModelSerializer):
    sender = serializers.ChoiceField(
        choices=TicketMessage.Sender.choices, required=False
    )
    files = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = TicketMessage
        fields = ["sender", "content", "reply_to", "files"]

    def validate_files(self, files: List):
        if not files:
            return files
        if len(files) > MAX_ATTACHMENT_COUNT:
            raise serializers.ValidationError(
                _("حداکثر ۲ فایل می‌توانید ارسال کنید.")
            )
        for f in files:
            if getattr(f, "size", 0) > MAX_ATTACHMENT_SIZE:
                raise serializers.ValidationError(
                    _("حجم هر فایل باید حداکثر ۵ مگابایت باشد.")
                )
            ct = getattr(f, "content_type", None) or getattr(
                getattr(f, "file", None), "content_type", None
            )
            if ct not in ALLOWED_MIME_TYPES:
                raise serializers.ValidationError(_("نوع فایل مجاز نیست."))
        return files

    def validate(self, attrs):
        request = self.context.get("request")
        ticket = self.context.get("ticket")
        user = getattr(request, "user", None)

        if not ticket:
            raise serializers.ValidationError(
                {"ticket": _("تیکت نامعتبر است.")}
            )

        reply_to = attrs.get("reply_to")
        if reply_to and reply_to.ticket_id != ticket.id:
            raise serializers.ValidationError(
                {"reply_to": _("پیام ارجاع باید متعلق به همین تیکت باشد.")}
            )

        sender = attrs.get("sender")
        if not user or not user.is_authenticated:
            raise serializers.ValidationError(
                {"non_field_errors": [_("کاربر احراز نشده است.")]}
            )
        if user == ticket.user:
            attrs.setdefault("sender", TicketMessage.Sender.USER)
            if sender and sender != TicketMessage.Sender.USER:
                raise serializers.ValidationError(
                    {
                        "sender": _(
                            "ارسال پیام توسط کاربر تنها با مقدار 'user' مجاز است."
                        )
                    }
                )
        else:
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        _("فقط صاحب تیکت می‌تواند پیام ارسال کند.")]
                }
            )

        return attrs

    def create(self, validated_data):
        ticket = self.context.get("ticket")
        files = validated_data.pop("files", [])
        message = TicketMessage.objects.create(ticket=ticket, **validated_data)
        for f in files:
            try:
                TicketMessageAttachment.objects.create(message=message, file=f)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"files": e.messages})
        return message
