from rest_framework.permissions import BasePermission


class HasFunctionPermission(BasePermission):
    """Authorize an action only when the authenticated user owns the required permission code."""

    message = 'You do not have permission to perform this action.'

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        required_function = getattr(view, 'required_function', None)
        if not required_function:
            return False

        return request.user.user_functions.filter(function__code=required_function).exists()
