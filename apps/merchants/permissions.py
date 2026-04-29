# merchants/permissions.py
from rest_framework import permissions


class IsMerchant(permissions.BasePermission):
    message = "فقط کاربران فروشنده می‌توانند به این بخش دسترسی داشته باشند."

    def has_permission(self, request, view):
        return hasattr(request.user, "merchant")
