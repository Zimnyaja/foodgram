from django.db.models import Count
from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import (
    Favorite, Ingredient, Recipe, RecipeIngredient, ShoppingList, Tag
)


class BaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'recipe')  # Поля для отображения в списке
    list_filter = ('user', 'recipe')  # Фильтры для навигации
    # Поиск по связанным полям
    search_fields = ('user__username', 'recipe__name')
    ordering = ('id',)  # Сортировка по ID


class IngredientResource(resources.ModelResource):
    class Meta:
        model = Ingredient


@admin.register(Ingredient)
class IngredientAdmin(ImportExportModelAdmin):
    resource_class = IngredientResource
    list_display = ('name', 'measurement_unit')
    search_fields = ('name',)


class RecipeIngredientInline(admin.TabularInline):
    model = RecipeIngredient
    extra = 1
    min_num = 1


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'author', 'get_favorites_count')
    list_filter = ('tags', 'author')
    search_fields = ('name', 'author__username', 'tags__name')
    inlines = [RecipeIngredientInline]
    readonly_fields = ('get_favorites_count',)

    def get_queryset(self, request):
        # Аннотация для подсчёта избранных
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(favorites_count=Count('favorite_set'))
        return queryset

    @admin.display(description='В избранном')
    def get_favorites_count(self, obj):
        return obj.favorites_count


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')


@admin.register(Favorite)
class FavoriteAdmin(BaseAdmin):
    pass


@admin.register(ShoppingList)
class ShoppingListAdmin(BaseAdmin):
    pass
