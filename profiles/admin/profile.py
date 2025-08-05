# profiles/admin/profile.py

from django.contrib import admin

from profiles.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'phone_number', 'national_id', 'full_name']
    search_fields = ['user__username', 'national_id', 'phone_number']

    @admin.display(description="نام کامل")
    def full_name(self, obj):
        return obj.full_name

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False
