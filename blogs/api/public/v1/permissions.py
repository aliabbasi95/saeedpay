# blogs/api/public/v1/permissions.py

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrStaff(BasePermission):
    """
    Object-level permission:
    - Read-only methods are allowed to any request.
    - Write methods require the user to be the owner (e.g., obj.author) or staff.
    """

    def has_object_permission(self, request, view, obj):
        # Allow safe methods for everyone
        if request.method in SAFE_METHODS:
            return True

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False

        # Staff users can modify any object
        if user.is_staff:
            return True

        # Fallback ownership check via `author` foreign key
        owner_id = getattr(obj, "author_id", None)
        return owner_id == user.id
