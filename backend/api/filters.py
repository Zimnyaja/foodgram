from django_filters import rest_framework as filters

from recipes.models import Recipe


class RecipeFilter(filters.FilterSet):
    """Фильтры для модели Recipe."""

    tags = filters.AllValuesMultipleFilter(field_name='tags__slug')
    # is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    # is_in_shopping_cart = filters.BooleanFilter(
    #     method='filter_is_in_shopping_cart'
    # )
    is_favorited = filters.BooleanFilter(field_name='is_favorited')  # Убрали `method=`
    is_in_shopping_cart = filters.BooleanFilter(field_name='is_in_shopping_cart')  # Убрали `method=`

    class Meta:
        model = Recipe
        fields = ['tags', 'author',]

    # def filter_is_favorited(self, queryset, name, value):
    #     """Фильтрует рецепты, добавленные в избранное."""
    #     if value and self.request.user.is_authenticated:
    #         return queryset.filter(favorite_set__user=self.request.user)
    #     return queryset

    # def filter_is_in_shopping_cart(self, queryset, name, value):
    #     """Фильтрует рецепты, находящиеся в корзине."""
    #     if value and self.request.user.is_authenticated:
    #         return queryset.filter(shoppinglist_set__user=self.request.user)
    #     return queryset
