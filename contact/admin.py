from django.contrib import admin
from contact.models.contact import Contact

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "created_at")
    search_fields = ("name", "email", "phone")
    list_filter = ("created_at",)
    readonly_fields = ("name", "email", "phone", "message", "created_at")
    fieldsets = (
        (None, {
            'fields': ("name", "email", "phone", "message", "created_at")
        }),
    )
    def has_add_permission(self, request):
        return False
