# apps/auth_api/api/public/v1/serializers/mixins.py

class UserPublicPayloadMixin:
    @staticmethod
    def build_user_public_payload(user):
        roles = []
        if hasattr(user, "customer"):
            roles.append("customer")
        if hasattr(user, "merchant"):
            roles.append("merchant")
        profile = getattr(user, "profile", None)
        return {
            "user_id": user.id,
            "phone_number": getattr(profile, "phone_number", ""),
            "roles": roles,
            "first_name": getattr(profile, "first_name", ""),
            "last_name": getattr(profile, "last_name", ""),
        }


