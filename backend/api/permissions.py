from rest_framework.permissions import BasePermission, SAFE_METHODS


class AdminOnlyPermission(BasePermission):
    """Доступ только для администраторов."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class AdminOrReadOnlyPermission(BasePermission):
    """Чтение доступно всем, изменение — только администраторам."""

    def has_permission(self, request, view):
        return (
            request.method in SAFE_METHODS
            or (request.user.is_authenticated and request.user.is_staff)
            # or (request.user.is_authenticated and request.user.is_admin)
        )
