from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAuthorOrReadOnly(BasePermission):
    """
    Разрешение: чтение доступно всем,
    редактирование и удаление — только автору рецепта.
    """
    def has_object_permission(self, request, view, obj):
        # Разрешаем безопасные методы (GET, HEAD, OPTIONS)
        if request.method in SAFE_METHODS:
            return True
        # Для небезопасных методов проверяем, является ли пользователь автором
        return obj.author == request.user
