from django.contrib import admin
from credit.models.statement_line import StatementLine


@admin.register(StatementLine)
class StatementLineAdmin(admin.ModelAdmin):
    list_display = ("statement", "type", "amount", "created_at", "description")
    list_filter = ("type", "created_at")
    search_fields = ("description",)
