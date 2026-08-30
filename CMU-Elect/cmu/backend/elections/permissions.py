from rest_framework.permissions import BasePermission


class IsAuthenticatedAndPasswordChanged(BasePermission):
    """Allow normal voter endpoints only after the first-login password is changed."""

    message = "You must change your password before accessing this resource."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        profile = getattr(request.user, "profile", None)
        return bool(
            profile
            and profile.account_status == "active"
            and request.user.is_active
            and not profile.must_change_password
        )


class IsAdministrator(BasePermission):
    """Allow access only to authenticated, active Django staff users."""

    message = "Administrator access is required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.is_staff
        )
