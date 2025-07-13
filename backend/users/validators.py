import re

from django.core.exceptions import ValidationError


def username_validation(username):
    """Проверка имени пользователя."""
    # if username.lower() == 'me':
    #     raise ValidationError('Имя пользователя не может быть "me".')

    invalid_chars = re.sub(r'[\w.@+-]', '', username)
    if invalid_chars:
        raise ValidationError(
            f'Имя пользователя содержит недопустимые символы: {invalid_chars}'
        )

    return username
