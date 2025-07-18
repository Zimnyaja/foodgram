from django.contrib.auth import get_user_model
from django.db import transaction

from rest_framework import serializers

from api.fields import Base64ImageField
from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                            ShoppingList, Tag)
from users.models import Subscription


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Сериализатор для пользователей, включает все поля пользователя."""
    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ('email', 'id', 'username', 'first_name', 'last_name',
                  'is_subscribed', 'avatar')
        lookup_field = 'username'

    def get_is_subscribed(self, obj):
        """Проверяет, подписан ли текущий пользователь на `obj`."""
        request = self.context.get('request')
        return (
            request
            and not request.user.is_anonymous
            and Subscription.objects.filter(
                user=request.user,
                subscribed_to=obj
            ).exists()
        )


class UserAvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=True)

    class Meta:
        model = User
        fields = ('avatar',)

    def validate(self, data):
        """
        Генеральная валидация данных на уровне всего сериализатора.
        """
        if 'avatar' not in data:
            raise serializers.ValidationError({
                'avatar': "Поле 'avatar' является обязательным."
            })

        return data


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')
        read_only_fields = ('id',)


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


# все равно не могу оставить один сериалайзер для записи и чтения,
# т.к. поля для выдачи и записи разные. Кроме того, в моей модели поле для
# amount называется quantity. Поэтому приходится единый сериалайзер делать
# огромным, и перегруженным чтобы настроить его корректную работу.
# Двумя разными намного компактнее выходит. Может еще логика моего кода и
# обработок ниже вступает в конфликт. Не разобралась как его просто объединить.
class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )
    amount = serializers.FloatField(source='quantity')

    class Meta:
        model = RecipeIngredient
        fields = ['id', 'name', 'measurement_unit', 'amount']


class RecipeIngredientWriteSerializer(serializers.Serializer):
    id = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    amount = serializers.FloatField()

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                'Количество ингредиента должно быть больше нуля.'
            )
        return value


class RecipeReadSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientSerializer(
        many=True, source='recipeingredient_set'
    )
    tags = TagSerializer(many=True)
    author = UserSerializer(read_only=True)
    is_favorited = serializers.BooleanField(read_only=True)
    is_in_shopping_cart = serializers.BooleanField(read_only=True)

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients', 'is_favorited',
            'is_in_shopping_cart', 'name', 'image', 'text', 'cooking_time'
        )


class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientWriteSerializer(many=True, write_only=True)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients',
            'name', 'image', 'text', 'cooking_time'
        )
        read_only_fields = ('author',)

    def validate(self, data):
        """
        Общая валидация ингредиентов и тегов.
        """
        # Проверка наличия ингредиентов
        ingredients = data.get('ingredients')
        if not ingredients:
            raise serializers.ValidationError(
                {'ingredients': 'Необходимо указать хотя бы один ингредиент.'}
            )
        # Проверка уникальности ингредиентов
        unique_ingredients = {ingredient['id'] for ingredient in ingredients}
        if len(unique_ingredients) != len(ingredients):
            raise serializers.ValidationError(
                {
                    'ingredients': (
                        'Ингредиенты в рецепте должны быть уникальными.'
                    )
                }
            )

        # Проверка наличия тегов
        tags = data.get('tags')
        if not tags:
            raise serializers.ValidationError(
                {'tags': 'Необходимо указать хотя бы один тег.'}
            )
        # Проверка уникальности тегов
        unique_tags = set(tags)
        if len(unique_tags) != len(tags):
            raise serializers.ValidationError(
                {'tags': 'Теги в рецепте должны быть уникальными.'}
            )

        return data

    @transaction.atomic
    def create(self, validated_data):
        tags_data = validated_data.pop('tags')
        ingredients_data = validated_data.pop('ingredients')
        recipe = Recipe.objects.create(
            author=self.context['request'].user,
            **validated_data
        )
        recipe.tags.set(tags_data)
        self._process_recipe_ingredients(recipe, ingredients_data)
        user = self.context['request'].user
        recipe.is_favorited = Favorite.objects.filter(
            user=user, recipe=recipe
        ).exists()
        recipe.is_in_shopping_cart = ShoppingList.objects.filter(
            user=user, recipe=recipe
        ).exists()
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)
        ingredients_data = validated_data.pop('ingredients', None)
        instance = super().update(instance, validated_data)

        # Обновляем теги
        instance.tags.set(tags_data)
        # Удаляем старые ингредиенты
        instance.ingredients.clear()
        self._process_recipe_ingredients(instance, ingredients_data)
        return instance

    def _process_recipe_ingredients(self, recipe, ingredients_data):
        """
        Подготавливает данные для объектов RecipeIngredient.
        """
        recipe_ingredients = []
        for ingredient_data in ingredients_data:
            if 'id' not in ingredient_data or 'amount' not in ingredient_data:
                raise serializers.ValidationError(
                    'Каждый ингредиент должен содержать поля "id" и "amount".'
                )
            recipe_ingredient = RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient_data['id'],
                quantity=ingredient_data['amount']
            )
            recipe_ingredients.append(recipe_ingredient)
        # Массовое добавление объектов в базу данных
        RecipeIngredient.objects.bulk_create(recipe_ingredients)

    def to_representation(self, instance):
        # Передаём объект в сериализатор для чтения
        read_serializer = RecipeReadSerializer(
            instance, context=self.context
        )
        return read_serializer.data


class RecipeShortSerializer(serializers.ModelSerializer):
    """Короткий для избранного"""
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')


class SubscriptionSerializer(UserSerializer):
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('recipes', 'recipes_count')

    def get_recipes(self, obj):
        """
        Возвращает рецепты автора с учётом ограничения recipes_limit.
        """
        request = self.context.get('request')
        recipes_limit = request.query_params.get('recipes_limit')

        recipes = obj.recipes.all()  # Получаем все рецепты автора
        if recipes_limit:  # Применяем ограничение
            try:
                recipes = recipes[:int(recipes_limit)]
            except ValueError:
                pass  # Если параметр невалидный, игнорируем его

        return RecipeShortSerializer(
            recipes, many=True,
            context={'request': request}
        ).data

    def get_recipes_count(self, obj):
        """
        Возвращает общее количество рецептов автора.
        """
        return obj.recipes.count()
