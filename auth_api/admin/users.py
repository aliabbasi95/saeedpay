# auth_api/admin/users.py
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.auth import get_user_model
from django.db import models

from customers.models import Customer
from lib.erp_base.admin import BaseAdmin
from merchants.models import Merchant
from profiles.models import Profile

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fk_name = 'user'
    extra = 0


class CustomerInline(admin.StackedInline):
    model = Customer
    can_delete = False
    fk_name = 'user'
    extra = 0


class MerchantInline(admin.StackedInline):
    model = Merchant
    can_delete = False
    fk_name = 'user'
    extra = 0


class UserRoleFilter(SimpleListFilter):
    title = 'نقش کاربر'
    parameter_name = 'role'

    def lookups(self, request, model_admin):
        return [
            ('customer', 'مشتری'),
            ('merchant', 'فروشنده'),
            ('both', 'مشتری و فروشنده'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'customer':
            return queryset.filter(
                customer__isnull=False, merchant__isnull=True
            )
        elif self.value() == 'merchant':
            return queryset.filter(
                merchant__isnull=False, customer__isnull=True
            )
        elif self.value() == 'both':
            return queryset.filter(
                customer__isnull=False, merchant__isnull=False
            )
        return queryset


class CustomUserAdmin(BaseAdmin):
    list_display = [
        'id',
        'username',
        'is_active',
        'get_phone_number',
        'get_national_id',
        'get_roles'
    ]
    search_fields = ['username', 'profile__national_id']
    inlines = [ProfileInline, CustomerInline, MerchantInline]
    list_filter = [UserRoleFilter, 'is_active']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(
            models.Q(customer__isnull=False) | models.Q(merchant__isnull=False)
        ).distinct()

    @admin.display(description="شماره تلفن")
    def get_phone_number(self, obj):
        return getattr(obj.profile, "phone_number", "-")

    @admin.display(description="کد ملی")
    def get_national_id(self, obj):
        return getattr(obj.profile, "national_id", "-")

    @admin.display(description="نقش‌ها")
    def get_roles(self, obj):
        roles = []
        if hasattr(obj, 'customer'):
            roles.append("مشتری")
        if hasattr(obj, 'merchant'):
            roles.append("فروشنده")
        return "، ".join(roles) if roles else "-"

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
