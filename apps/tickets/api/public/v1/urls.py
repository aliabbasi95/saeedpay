# tickets/api/public/v1/urls.py

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from tickets.api.public.v1.views import TicketViewSet
from tickets.api.public.v1.views.category import TicketCategoryViewSet

app_name = "tickets_public_v1"

router = DefaultRouter()
router.register("tickets", TicketViewSet, basename="tickets")
router.register("categories", TicketCategoryViewSet, basename="ticket-category")

urlpatterns = [
    path("", include(router.urls)),
]
