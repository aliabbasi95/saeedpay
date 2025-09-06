# tickets/tests/api/public/v1/test_tickets_api.py
import io
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient

from tickets.models import (
    Ticket,
    TicketCategory,
    TicketMessage,
    TicketMessageAttachment,
)
from tickets.utils.choices import TicketStatus, TicketPriority

User = get_user_model()


@pytest.mark.django_db
class TestTicketsAPI:
    @pytest.fixture
    def user(self):
        return User.objects.create(username="testuser")

    @pytest.fixture
    def other_user(self):
        return User.objects.create(username="otheruser")

    @pytest.fixture
    def api_client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    @pytest.fixture
    def other_client(self, other_user):
        client = APIClient()
        client.force_authenticate(user=other_user)
        return client

    @pytest.fixture
    def category(self):
        return TicketCategory.objects.create(name="General", icon="", color="#000")

    def create_ticket(self, user, category=None, **kwargs):
        defaults = dict(
            user=user,
            title="Help needed",
            status=TicketStatus.OPEN,
            priority=TicketPriority.NORMAL,
        )
        if category:
            defaults["category"] = category
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)

    # List / Create
    def test_list_tickets(self, api_client, user, category):
        t1 = self.create_ticket(user, category, title="First")
        t2 = self.create_ticket(user, category, title="Second")
        resp = api_client.get("/saeedpay/api/tickets/public/v1/tickets/")
        assert resp.status_code == status.HTTP_200_OK
        assert isinstance(resp.data, list)
        assert len(resp.data) == 2
        # default ordering is -id -> latest first
        assert resp.data[0]["id"] == t2.id
        assert resp.data[1]["id"] == t1.id

    def test_create_ticket_and_retrieve_list(self, api_client, category):
        payload = {
            "title": "مشکل در ورود به حساب",
            "priority": TicketPriority.HIGH,
            "category_id": category.id,
        }
        create_resp = api_client.post("/saeedpay/api/tickets/public/v1/tickets/", payload)
        assert create_resp.status_code == status.HTTP_201_CREATED
        # Ensure it's visible via list with nested category
        list_resp = api_client.get("/saeedpay/api/tickets/public/v1/tickets/")
        assert list_resp.status_code == status.HTTP_200_OK
        assert len(list_resp.data) == 1
        item = list_resp.data[0]
        assert item["title"] == "مشکل در ورود به حساب"
        assert item["priority"] == TicketPriority.HIGH
        assert item["status"] == TicketStatus.OPEN
        assert item["category"]["name"] == "General"

    # Retrieve with paginated messages
    def test_retrieve_ticket_with_paginated_messages(self, api_client, user):
        ticket = self.create_ticket(user)
        # Create 11 messages to test pagination (page_size=10)
        for i in range(11):
            TicketMessage.objects.create(
                ticket=ticket, sender=TicketMessage.Sender.USER, content=f"msg {i}"
            )
        resp = api_client.get(f"/saeedpay/api/tickets/public/v1/tickets/{ticket.id}/")
        assert resp.status_code == status.HTTP_200_OK
        assert set(resp.data.keys()) == {"ticket", "messages"}
        msgs = resp.data["messages"]
        assert set(msgs.keys()) == {"results", "pagination"}
        assert len(msgs["results"]) == 10
        assert msgs["pagination"]["count"] == 11
        # second page
        resp2 = api_client.get(f"/saeedpay/api/tickets/public/v1/tickets/{ticket.id}/?page=2")
        assert len(resp2.data["messages"]["results"]) == 1
        assert resp2.data["messages"]["pagination"]["page"] == 2

    # Add message action
    def test_add_message_with_two_attachments(self, api_client, user):
        ticket = self.create_ticket(user)
        file1 = SimpleUploadedFile(
            "note1.txt", b"hello", content_type="text/plain"
        )
        file2 = SimpleUploadedFile(
            "note2.txt", b"world", content_type="text/plain"
        )
        data = {"content": "Here are files", "files": [file1, file2]}
        resp = api_client.post(
            f"/saeedpay/api/tickets/public/v1/tickets/{ticket.id}/messages/",
            data,
            format="multipart",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert TicketMessage.objects.filter(ticket=ticket).count() == 1
        msg = TicketMessage.objects.get(ticket=ticket)
        assert TicketMessageAttachment.objects.filter(message=msg).count() == 2

    def test_add_message_more_than_two_files_rejected(self, api_client, user):
        ticket = self.create_ticket(user)
        files = [
            SimpleUploadedFile("f1.txt", b"1", content_type="text/plain"),
            SimpleUploadedFile("f2.txt", b"2", content_type="text/plain"),
            SimpleUploadedFile("f3.txt", b"3", content_type="text/plain"),
        ]
        resp = api_client.post(
            f"/saeedpay/api/tickets/public/v1/tickets/{ticket.id}/messages/",
            {"content": "too many", "files": files},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "files" in resp.data

    def test_add_message_invalid_mime_rejected(self, api_client, user):
        ticket = self.create_ticket(user)
        bad = SimpleUploadedFile("malware.bin", b"x", content_type="application/zip")
        resp = api_client.post(
            f"/saeedpay/api/tickets/public/v1/tickets/{ticket.id}/messages/",
            {"content": "bad file", "files": [bad]},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "files" in resp.data

    def test_add_message_oversized_file_rejected(self, api_client, user):
        ticket = self.create_ticket(user)
        big_bytes = b"0" * (5 * 1024 * 1024 + 1)
        big = SimpleUploadedFile("big.pdf", big_bytes, content_type="application/pdf")
        resp = api_client.post(
            f"/saeedpay/api/tickets/public/v1/tickets/{ticket.id}/messages/",
            {"content": "big file", "files": [big]},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "files" in resp.data

    def test_add_message_reply_to_must_belong_to_same_ticket(self, api_client, user):
        t1 = self.create_ticket(user)
        t2 = self.create_ticket(user)
        msg = TicketMessage.objects.create(ticket=t1, sender=TicketMessage.Sender.USER, content="hi")
        resp = api_client.post(
            f"/saeedpay/api/tickets/public/v1/tickets/{t2.id}/messages/",
            {"content": "replying", "reply_to": msg.id},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "reply_to" in resp.data

    def test_sender_must_be_user_for_owner(self, api_client, user):
        ticket = self.create_ticket(user)
        resp = api_client.post(
            f"/saeedpay/api/tickets/public/v1/tickets/{ticket.id}/messages/",
            {"content": "no", "sender": TicketMessage.Sender.STAFF},
            format="multipart",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "sender" in resp.data

    def test_other_user_cannot_access_ticket_or_add_message(self, api_client, other_client, user, other_user):
        ticket = self.create_ticket(user)
        # Other user cannot retrieve
        resp = other_client.get(f"/saeedpay/api/tickets/public/v1/tickets/{ticket.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        # Or post message
        resp2 = other_client.post(
            f"/saeedpay/api/tickets/public/v1/tickets/{ticket.id}/messages/",
            {"content": "hack"},
            format="multipart",
        )
        assert resp2.status_code == status.HTTP_404_NOT_FOUND

    # Filtering and ordering
    def test_filter_by_status_priority_category_and_ordering(self, api_client, user, category):
        cat2 = TicketCategory.objects.create(name="Billing")
        t_open = self.create_ticket(user, category, status=TicketStatus.OPEN, priority=TicketPriority.HIGH)
        t_prog = self.create_ticket(user, category, status=TicketStatus.IN_PROGRESS, priority=TicketPriority.NORMAL)
        t_res = self.create_ticket(user, cat2, status=TicketStatus.RESOLVED, priority=TicketPriority.LOW)

        # status multi
        resp = api_client.get(
            "/saeedpay/api/tickets/public/v1/tickets/?status=open&status=in_progress"
        )
        assert resp.status_code == status.HTTP_200_OK
        ids = {row["id"] for row in resp.data}
        assert ids == {t_open.id, t_prog.id}

        # priority
        resp2 = api_client.get(
            "/saeedpay/api/tickets/public/v1/tickets/?priority=high"
        )
        assert {row["id"] for row in resp2.data} == {t_open.id}

        # category
        resp3 = api_client.get(
            f"/saeedpay/api/tickets/public/v1/tickets/?category={category.id}"
        )
        assert {row["id"] for row in resp3.data} == {t_open.id, t_prog.id}

        # ordering by id asc (deterministic)
        resp4 = api_client.get(
            "/saeedpay/api/tickets/public/v1/tickets/?ordering=id"
        )
        assert resp4.data[0]["id"] == t_open.id

    def test_invalid_filter_value_returns_400(self, api_client):
        resp = api_client.get(
            "/saeedpay/api/tickets/public/v1/tickets/?status=invalid"
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "status" in resp.data

    # Auth
    def test_unauthenticated_access_denied(self, category):
        client = APIClient()
        # list
        resp = client.get("/saeedpay/api/tickets/public/v1/tickets/")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        # create
        payload = {
            "title": "x",
            "priority": TicketPriority.NORMAL,
            "category_id": category.id,
        }
        resp2 = client.post("/saeedpay/api/tickets/public/v1/tickets/", payload)
        assert resp2.status_code == status.HTTP_401_UNAUTHORIZED
