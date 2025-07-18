from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAuthorOrReadOnly(BasePermission):
    """
    Разрешение: чтение доступно всем,
    редактирование и удаление — только автору рецепта.
    """
    def has_object_permission(self, request, view, obj):
        # Разрешаем безопасные методы (GET, HEAD, OPTIONS)
        # Для небезопасных методов проверяем, является ли пользователь автором
        return request.method in SAFE_METHODS or obj.author == request.user
