# tickets/tests/serializers/test_tickets_serializers.py
import io
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIRequestFactory

from tickets.models import Ticket, TicketCategory, TicketMessage, TicketMessageAttachment
from tickets.api.public.v1.serializers.ticket import (
    TicketCreateSerializer,
    TicketMessageCreateSerializer,
)
from tickets.utils.choices import TicketStatus, TicketPriority

User = get_user_model()


@pytest.mark.django_db
class TestTicketSerializers:
    @pytest.fixture
    def user(self):
        return User.objects.create(username="u1")

    @pytest.fixture
    def other_user(self):
        return User.objects.create(username="u2")

    @pytest.fixture
    def category(self):
        return TicketCategory.objects.create(name="General")

    @pytest.fixture
    def rf(self):
        return APIRequestFactory()

    def test_ticket_create_serializer_requires_auth(self, rf, category):
        req = rf.post("/")  # no user
        ser = TicketCreateSerializer(
            data={"title": "t", "priority": TicketPriority.NORMAL, "category_id": category.id},
            context={"request": req},
        )
        assert not ser.is_valid()
        assert "non_field_errors" in ser.errors

    def test_ticket_create_serializer_open_limit(self, rf, user):
        # create 15 open tickets
        for _ in range(15):
            Ticket.objects.create(user=user, title="t", status=Ticket.Status.OPEN)
        req = rf.post("/")
        req.user = user
        ser = TicketCreateSerializer(
            data={"title": "x", "description": "y", "priority": TicketPriority.HIGH},
            context={"request": req},
        )
        assert not ser.is_valid()
        assert "non_field_errors" in ser.errors

    def test_ticket_create_serializer_success(self, rf, user, category):
        req = rf.post("/")
        req.user = user
        ser = TicketCreateSerializer(
            data={"title": "t", "description": "d", "priority": TicketPriority.LOW, "category_id": category.id},
            context={"request": req},
        )
        assert ser.is_valid(), ser.errors
        obj = ser.save(user=user)
        assert isinstance(obj, Ticket)
        assert obj.user == user
        assert obj.status == TicketStatus.OPEN

    def test_message_serializer_sender_and_reply_validation(self, rf, user):
        t1 = Ticket.objects.create(user=user, title="t", description="d")
        t2 = Ticket.objects.create(user=user, title="t2", description="d2")
        other_msg = TicketMessage.objects.create(ticket=t1, sender=TicketMessage.Sender.USER, content="x")

        req = rf.post("/")
        req.user = user
        ser = TicketMessageCreateSerializer(
            data={"sender": TicketMessage.Sender.STAFF, "content": "bad", "reply_to": other_msg.id},
            context={"request": req, "ticket": t2},
        )
        assert not ser.is_valid()
        # reply_to invalid and sender invalid
        assert "reply_to" in ser.errors or "sender" in ser.errors

    def test_message_serializer_requires_owner(self, rf, user, other_user):
        ticket = Ticket.objects.create(user=user, title="t", description="d")
        req = rf.post("/")
        req.user = other_user
        ser = TicketMessageCreateSerializer(
            data={"sender": TicketMessage.Sender.USER, "content": "hi"},
            context={"request": req, "ticket": ticket},
        )
        assert not ser.is_valid()
        assert "non_field_errors" in ser.errors

    def test_message_serializer_files_rules(self, rf, user):
        ticket = Ticket.objects.create(user=user, title="t", description="d")
        req = rf.post("/")
        req.user = user

        # Too many files
        files = [
            SimpleUploadedFile("f1.txt", b"1", content_type="text/plain"),
            SimpleUploadedFile("f2.txt", b"2", content_type="text/plain"),
            SimpleUploadedFile("f3.txt", b"3", content_type="text/plain"),
        ]
        ser = TicketMessageCreateSerializer(
            data={"sender": TicketMessage.Sender.USER, "content": "x", "files": files},
            context={"request": req, "ticket": ticket},
        )
        assert not ser.is_valid()
        assert "files" in ser.errors

        # Oversized
        big = SimpleUploadedFile("big.pdf", b"0" * (5 * 1024 * 1024 + 1), content_type="application/pdf")
        ser2 = TicketMessageCreateSerializer(
            data={"sender": TicketMessage.Sender.USER, "content": "x", "files": [big]},
            context={"request": req, "ticket": ticket},
        )
        assert not ser2.is_valid()
        assert "files" in ser2.errors

        # Invalid mime
        bad = SimpleUploadedFile("malware.bin", b"x", content_type="application/zip")
        ser3 = TicketMessageCreateSerializer(
            data={"sender": TicketMessage.Sender.USER, "content": "x", "files": [bad]},
            context={"request": req, "ticket": ticket},
        )
        assert not ser3.is_valid()
        assert "files" in ser3.errors

    def test_message_serializer_creates_attachments(self, rf, user):
        ticket = Ticket.objects.create(user=user, title="t", description="d")
        req = rf.post("/")
        req.user = user
        f1 = SimpleUploadedFile("a.txt", b"a", content_type="text/plain")
        f2 = SimpleUploadedFile("b.txt", b"b", content_type="text/plain")
        ser = TicketMessageCreateSerializer(
            data={"sender": TicketMessage.Sender.USER, "content": "ok", "files": [f1, f2]},
            context={"request": req, "ticket": ticket},
        )
        assert ser.is_valid(), ser.errors
        msg = ser.save()
        assert TicketMessage.objects.filter(id=msg.id).exists()
        assert TicketMessageAttachment.objects.filter(message=msg).count() == 2
