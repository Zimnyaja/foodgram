from django_filters import rest_framework as filters

from recipes.models import Ingredient, Recipe, Tag


class RecipeFilter(filters.FilterSet):
    """Фильтры для модели Recipe."""

    tags = filters.ModelMultipleChoiceFilter(
        field_name='tags__slug',  # Фильтрация по slug тегов
        to_field_name='slug',  # Сравнение по slug
        queryset=Tag.objects.all(),  # Проверяем только существующие теги
    )
    is_favorited = filters.BooleanFilter(field_name='is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(
        field_name='is_in_shopping_cart'
    )

    class Meta:
        model = Recipe
        fields = ['tags', 'author', ]


class IngredientFilter(filters.FilterSet):
    """Фильтр для модели Ingredient."""
    name = filters.CharFilter(field_name='name', lookup_expr='istartswith')

    class Meta:
        model = Ingredient
        fields = ['name']
