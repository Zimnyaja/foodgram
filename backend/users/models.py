from django.db import models
from django.db.models import Q, F
from django.contrib.auth.models import AbstractUser

from users.constants import (EMAIL_LENGTH, NAME_LENGTH)
from users.validators import username_validation


class User(AbstractUser):
    """Кастомная модель пользователя."""
    email = models.EmailField(
        verbose_name='Почта',
        max_length=EMAIL_LENGTH,
        unique=True,
    )
    username = models.CharField(
        verbose_name='Имя пользователя',
        max_length=NAME_LENGTH,
        validators=[username_validation],
        unique=True,
    )
    first_name = models.CharField(
        verbose_name='Имя',
        max_length=NAME_LENGTH,
    )
    last_name = models.CharField(
        verbose_name='Фамилия',
        max_length=NAME_LENGTH,
    )
    avatar = models.ImageField(
        verbose_name='Аватар',
        upload_to='avatars/',
        blank=True,
        default='',
    )
    USERNAME_FIELD = 'email'  # Используем email вместо username для входа
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']  # Обязательное

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('username',)

    def __str__(self):
        return self.username


class Subscription(models.Model):
    user = models.ForeignKey(
        User, related_name='subscriptions', on_delete=models.CASCADE
    )
    subscribed_to = models.ForeignKey(
        User, related_name='subscribers', on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # 1️⃣ Ограничение: Запрет на повторную подписку
            models.UniqueConstraint(
                fields=['user', 'subscribed_to'],
                # Поля, которые должны быть уникальными в комбинации
                name='unique_subscription'  # Название ограничения
            ),
            # 2️⃣ Ограничение: Запрет подписки на самого себя
            models.CheckConstraint(
                check=~Q(user=F('subscribed_to')),
                # Проверка, что пользователь не подписан сам на себя
                name='prevent_self_subscription'  # Название ограничения
            ),
        ]
        verbose_name = 'Подписка'  # Корректное имя модели в админ-панели
        verbose_name_plural = 'Подписки'  # Корректное множественное число
        ordering = ['-created_at']
        # Сортировка по дате создания (например, последние подписки сверху)

    def __str__(self):
        return (f"{self.user.username} подписан "
                f"на {self.subscribed_to.username}")
