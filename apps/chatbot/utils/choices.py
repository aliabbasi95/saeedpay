# chatbot/utils/choices.py

from django.db import models
from django.utils.translation import gettext_lazy as _


class Sender(models.TextChoices):
    USER = "user", _("کاربر")
    AI = "ai", _("هوش مصنوعی")
