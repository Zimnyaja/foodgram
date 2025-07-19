from django_filters import rest_framework as filters

from recipes.models import Ingredient, Recipe


class RecipeFilter(filters.FilterSet):
    """Фильтры для модели Recipe."""

    tags = filters.AllValuesMultipleFilter(field_name='tags__slug')
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
