from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models

from .constants import (
    MAX_LENGHT_NAME, MAX_LENGHT_SLUG, MAX_LENGHT_TAG,
    MAX_LENGHT_INGREDIENT_NAME, MAX_LENGHT_MEASUREMENT,
    MIN_COOKING_TIME
)

User = get_user_model()


class BaseUserRecipe(models.Model):
    """Базовый класс для моделей, связывающих пользователя и рецепт."""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, verbose_name="Пользователь", related_name="%(class)s_set",
    )
    recipe = models.ForeignKey(
        'Recipe', on_delete=models.CASCADE, verbose_name="Рецепт", related_name="%(class)s_set",
    )

    class Meta:
        abstract = True
        constraints = [
            models.UniqueConstraint(
                # Пользователь не может добавлять один и тот же рецепт дважды
                fields=['user', 'recipe'],
                name="unique_%(class)s"
            )
        ]


class Tag(models.Model):
    name = models.CharField(
        max_length=MAX_LENGHT_TAG, unique=True, verbose_name="Название"
    )
    slug = models.SlugField(max_length=MAX_LENGHT_SLUG, unique=True)

    class Meta:
        verbose_name = "Тег"
        verbose_name_plural = "Теги"
        ordering = ['name']

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    name = models.CharField(
        max_length=MAX_LENGHT_INGREDIENT_NAME, verbose_name="Название"
    )
    measurement_unit = models.CharField(
        max_length=MAX_LENGHT_MEASUREMENT, verbose_name="Мера измерения"
    )

    class Meta:
        verbose_name = "Ингредиент"
        verbose_name_plural = "Ингредиенты"
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                # Поля, которые должны быть уникальными в комбинации
                fields=['name', 'measurement_unit'],
                name='unique_ingredient_name_unit'
            )
        ]

    def __str__(self):
        return self.name


class Recipe(models.Model):
    tags = models.ManyToManyField(
        Tag, related_name='recipes', verbose_name="Теги"
    )
    author = models.ForeignKey(
        User, related_name='recipes',
        on_delete=models.CASCADE,
        verbose_name="Автор"
    )
    ingredients = models.ManyToManyField(
        Ingredient, through='RecipeIngredient'
    )
    name = models.CharField(
        max_length=MAX_LENGHT_NAME, verbose_name="Название рецепта"
    )
    image = models.ImageField(
        upload_to='recipes/images/',
        null=True,
        default=None,
        verbose_name="Картинка"
    )
    text = models.TextField(verbose_name="Описание")
    cooking_time = models.PositiveIntegerField(
        validators=[MinValueValidator(MIN_COOKING_TIME)],
        verbose_name="Время приготовления"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепты"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.CASCADE, verbose_name="Ингредиент"
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(MIN_COOKING_TIME)],
        verbose_name="Количество"
    )

    class Meta:
        verbose_name = "Ингредиент в рецепте"
        verbose_name_plural = "Ингредиенты в рецепте"

    def __str__(self):
        return (
            f"Нужен ингредиент {self.ingredient.name} "
            f"в количестве {self.quantity} {self.ingredient.measurement_unit} "
            f"для {self.recipe.name}"
        )


class Favorite(BaseUserRecipe):
    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранные"


class ShoppingList(BaseUserRecipe):
    class Meta:
        verbose_name = "Список покупок"
        verbose_name_plural = "Списки покупок"
