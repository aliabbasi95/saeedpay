# apps/tickets/filters.py
from django_filters import rest_framework as filters

from apps.tickets.models import Ticket
from apps.tickets.utils.choices import TicketPriority, TicketStatus


class TicketFilter(filters.FilterSet):
    status = filters.MultipleChoiceFilter(
        field_name="status", choices=TicketStatus.choices
    )
    priority = filters.MultipleChoiceFilter(
        field_name="priority", choices=TicketPriority.choices
    )
    category = filters.NumberFilter(field_name="category_id")

    class Meta:
        model = Ticket
        fields = ["status", "priority", "category"]
