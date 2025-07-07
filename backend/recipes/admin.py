from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import Tag, Ingredient


class IngredientResource(resources.ModelResource):
    class Meta:
        model = Ingredient

@admin.register(Ingredient)
class IngredientAdmin(ImportExportModelAdmin):
    resource_class = IngredientResource

# Здесь оставляем только Tag для регистрации
models = [Tag]
admin.site.register(models)
