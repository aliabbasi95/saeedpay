# tickets/tests/models/test_tickets_models.py
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from tickets.models import TicketCategory, Ticket, TicketMessage, TicketMessageAttachment
from tickets.utils.choices import TicketStatus, TicketPriority

User = get_user_model()


@pytest.mark.django_db
class TestTicketsModels:
    @pytest.fixture
    def user(self):
        return User.objects.create(username="testuser")

    @pytest.fixture
    def category(self):
        return TicketCategory.objects.create(name="Support", description="", icon="", color="#111")

    def test_ticket_category_str(self, category):
        assert str(category) == "Support"

    def test_ticket_defaults_and_str(self, user, category):
        t = Ticket.objects.create(user=user, title="Cannot login", description="...", category=category)
        assert t.status == TicketStatus.OPEN
        assert t.priority == TicketPriority.NORMAL
        s = str(t)
        assert str(t.id) in s and "Cannot login" in s

    def test_ticket_message_str_and_reply_to(self, user):
        ticket = Ticket.objects.create(user=user, title="x", description="y")
        m1 = TicketMessage.objects.create(ticket=ticket, sender=TicketMessage.Sender.USER, content="hi")
        m2 = TicketMessage.objects.create(ticket=ticket, sender=TicketMessage.Sender.USER, content="re", reply_to=m1)
        assert f"Ticket#{ticket.id}" in str(m1)
        assert m2.reply_to_id == m1.id

    def test_ticket_message_attachment_create_with_file(self, user):
        ticket = Ticket.objects.create(user=user, title="x", description="y")
        msg = TicketMessage.objects.create(ticket=ticket, sender=TicketMessage.Sender.USER, content="file")
        f = SimpleUploadedFile("doc.txt", b"hello", content_type="text/plain")
        att = TicketMessageAttachment.objects.create(message=msg, file=f)
        assert TicketMessageAttachment.objects.filter(id=att.id).exists()
        assert "doc" in att.file.name and att.file.name.endswith(".txt")
