from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django.utils.html import format_html

from store.models import StoreApiKey


@admin.register(StoreApiKey)
class StoreApiKeyAdmin(admin.ModelAdmin):
    list_display = ["store", "is_active", "last_regenerated_at", "regenerate_button"]
    readonly_fields = ["key_hash", "last_regenerated_at"]
    list_filter = ["is_active"]
    search_fields = ["store__name", "store__code"]

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def regenerate_button(self, obj):
        return format_html(
            f'<a class="button" href="{obj.id}/regenerate/">🔁 بازتولید کلید</a>'
        )

    regenerate_button.short_description = "عملیات"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:pk>/regenerate/",
                self.admin_site.admin_view(self.regenerate_key),
                name="storeapikey-regenerate",
            ),
        ]
        return custom_urls + urls

    def regenerate_key(self, request, pk):
        if not request.user.is_superuser:
            self.message_user(request, "فقط سوپریوزر مجاز است.", messages.ERROR)
            return redirect("..")
        try:
            obj = StoreApiKey.objects.get(pk=pk)
            new_key = obj.regenerate()
            self.message_user(
                request, f"کلید جدید تولید شد:\n{new_key}", messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request, f"خطا در بازتولید کلید: {str(e)}", messages.ERROR
            )
        return redirect("..")
