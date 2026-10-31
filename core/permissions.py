from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Signed-in users with the `admin` role. Staff users get 403."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == "admin")
