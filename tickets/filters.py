# tickets/filters.py
from django_filters import rest_framework as filters

from tickets.models import Ticket
from tickets.utils.choices import TicketStatus, TicketPriority


class TicketFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(field_name="status", choices=TicketStatus.choices)
    priority = filters.MultipleChoiceFilter(field_name="priority", choices=TicketPriority.choices)
    category = filters.NumberFilter(field_name="category_id")

    class Meta:
        model = Ticket
        fields = ["status", "priority", "category"]
