# profiles/admin/profile.py

from django.contrib import admin

from profiles.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "phone_number",
        "national_id",
        "full_name",
        "auth_stage",
        "kyc_status",
        "phone_national_id_match_status",
        "video_task_id",
        "kyc_last_checked_at",
    ]
    list_filter = ["auth_stage", "kyc_status", "phone_national_id_match_status"]
    search_fields = ["user__username", "national_id", "phone_number"]
    readonly_fields = [
        "user",
        "auth_stage",
        "kyc_status",
        "video_task_id",
        "kyc_last_checked_at",
        "phone_national_id_match_status",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        ("اطلاعات کاربر", {
            "fields": (
                "user",
                "phone_number",
                "email",
            )
        }),
        ("اطلاعات هویتی", {
            "fields": (
                "national_id",
                "first_name",
                "last_name",
                "birth_date",
            )
        }),
        ("احراز هویت", {
            "fields": (
                "auth_stage",
                "kyc_status",
                "phone_national_id_match_status",
                "video_task_id",
                "kyc_last_checked_at",
            )
        }),
        ("تاریخچه", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    @admin.display(description="نام کامل")
    def full_name(self, obj):
        return obj.full_name

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False
