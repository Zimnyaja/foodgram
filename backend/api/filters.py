from django_filters import rest_framework as filters
from recipes.models import Recipe


class RecipeFilter(filters.FilterSet):
    """Фильтры для модели Recipe."""

    tags = filters.AllValuesMultipleFilter(field_name='tags__slug')
    author = filters.NumberFilter(field_name='author__id')
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart'
    )

    class Meta:
        model = Recipe
        fields = ['tags', 'author', 'is_favorited', 'is_in_shopping_cart']

    def filter_is_favorited(self, queryset, name, value):
        """Фильтрует рецепты, добавленные в избранное."""
        if value and self.request.user.is_authenticated:
            return queryset.filter(favorite_set__user=self.request.user)
        return queryset

    def filter_is_in_shopping_cart(self, queryset, name, value):
        """Фильтрует рецепты, находящиеся в корзине."""
        if value and self.request.user.is_authenticated:
            return queryset.filter(shoppinglist_set__user=self.request.user)
        return queryset
