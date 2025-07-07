from django.urls import include, path
from rest_framework import routers

from api.views import IngredientViewSet, RecipeViewSet, TagViewSet, FavoriteToggle, ShoppingListToggle, UserViewSet


router = routers.DefaultRouter()
router.register('tags', TagViewSet, basename='tags')
router.register('recipes', RecipeViewSet, basename='recipes')
router.register('ingredients', IngredientViewSet, basename='ingredients')
router.register('users', UserViewSet, basename='users')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('djoser.urls.authtoken'), name='auth'),
    path('recipes/<int:recipe_id>/favorite/', FavoriteToggle.as_view(), name='favorite-toggle'),
    path('recipes/<int:recipe_id>/shopping_cart/', ShoppingListToggle.as_view(), name='shopping_list_toggle'),
]
