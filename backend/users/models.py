from django.db import models
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

    def __str__(self):
        return (f"{self.user.username} подписан "
                f"на {self.subscribed_to.username}")
