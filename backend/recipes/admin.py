from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import Favorite, Ingredient, Recipe, RecipeIngredient, Tag


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


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'author', 'get_favorites_count')
    list_filter = ('tags', 'author')
    search_fields = ('name', 'author__username', 'tags__name')
    inlines = [RecipeIngredientInline]
    readonly_fields = ('get_favorites_count',)

    def get_favorites_count(self, obj):
        return Favorite.objects.filter(recipe=obj).count()
    get_favorites_count.short_description = 'В избранном'


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'color')
    search_fields = ('name', 'slug')
