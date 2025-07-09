# customers/permissions.py
from rest_framework import permissions


class IsCustomer(permissions.BasePermission):
    message = "فقط کاربران مشتری می‌توانند به این بخش دسترسی داشته باشند."

    def has_permission(self, request, view):
        return hasattr(request.user, "customer")
