from django.contrib.auth import get_user_model
from django.db import models
from .constants import (
    MAX_LENGHT_NAME, MAX_LENGHT_SLUG, MAX_LENGHT_TAG,
    MAX_LENGHT_INGREDIENT_NAME, MAX_LENGHT_MEASUREMENT
)

User = get_user_model()


class Tag(models.Model):
    name = models.CharField(max_length=MAX_LENGHT_TAG, unique=True)
    slug = models.SlugField(max_length=MAX_LENGHT_SLUG, unique=True)

    class Meta:
        verbose_name = "Тег"
        verbose_name_plural = "Теги"
        ordering = ['name']

    def __str__(self):
        return self.name


class Ingredient(models.Model):
    name = models.CharField(max_length=MAX_LENGHT_INGREDIENT_NAME)
    measurement_unit = models.CharField(max_length=MAX_LENGHT_MEASUREMENT)

    class Meta:
        verbose_name = "Ингредиент"
        verbose_name_plural = "Ингредиенты"
        ordering = ['name']

    def __str__(self):
        return self.name


class Recipe(models.Model):
    tags = models.ManyToManyField(Tag, related_name='recipes')
    author = models.ForeignKey(User, related_name='recipes', on_delete=models.CASCADE)
    ingredients = models.ManyToManyField(Ingredient, through='RecipeIngredient')
    name = models.CharField(max_length=MAX_LENGHT_NAME)
    image = models.ImageField(
        upload_to='recipes/images/',
        null=True,
        default=None
    )
    text = models.TextField()
    cooking_time = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Рецепт"
        verbose_name_plural = "Рецепты"
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.FloatField()

    def __str__(self):
        return f"Нужен ингредиент {self.ingredient.name} в количестве {self.quantity} {self.ingredient.measurement_unit} для {self.recipe.name}"


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)


class ShoppingList(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)