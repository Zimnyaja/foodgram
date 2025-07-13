from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password

from rest_framework import serializers

from api.fields import Base64ImageField
from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                            ShoppingList, Tag)
from users.models import Subscription
from users.validators import username_validation

User = get_user_model()


class UsernameEmailValidationSerializer:
    """Сериализатор валидации имени пользователя и e-mail."""

    def validate_username(self, username):
        """Проверка на соответствие имени пользователя требованиям."""
        return username_validation(username)


class UserCreateSerializer(UsernameEmailValidationSerializer,
                           serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'email', 'id', 'username', 'first_name', 'last_name', 'password'
        ]
        extra_kwargs = {'password': {'write_only': True}}

    def validate_password(self, value):
        # Проверяем пароль на валидность
        validate_password(value)
        return value

    def create(self, validated_data):
        """Создание пользователя с хэшированным паролем."""
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)


class UserSerializer(UsernameEmailValidationSerializer,
                     serializers.ModelSerializer):
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
        if request is None or request.user.is_anonymous:
            return False
        return Subscription.objects.filter(
            user=request.user,
            subscribed_to=obj
        ).exists()


class UserAvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField(required=True)

    class Meta:
        model = User
        fields = ('avatar',)


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')
        read_only_fields = ('id',)


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='ingredient.id')
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


class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientWriteSerializer(many=True, write_only=True)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True
    )
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'tags', 'author', 'ingredients', 'is_favorited',
            'is_in_shopping_cart', 'name', 'image', 'text', 'cooking_time'
        )
        read_only_fields = ('author',)

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Favorite.objects.filter(
                user=request.user,
                recipe=obj
            ).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ShoppingList.objects.filter(
                user=request.user,
                recipe=obj
            ).exists()
        return False

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
                {'ingredients': 'Ингредиенты в рецепте должны быть уникальными.'}
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

    def create(self, validated_data):
        tags_data = validated_data.pop('tags', [])
        ingredients_data = validated_data.pop('ingredients')
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags_data)

        for ingredient_data in ingredients_data:
            RecipeIngredient.objects.create(recipe=recipe,
                                            ingredient=ingredient_data['id'],
                                            quantity=ingredient_data['amount'])

        return recipe

    def update(self, instance, validated_data):
        # Обновляем поля основного объекта
        tags_data = validated_data.pop('tags', None)
        ingredients_data = validated_data.pop('ingredients', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Обновляем теги
        if tags_data is not None:
            instance.tags.set(tags_data)

        # Обновляем ингредиенты
        if ingredients_data is not None:
            # Удаляем старые ингредиенты
            instance.recipeingredient_set.all().delete()
            for ingredient_data in ingredients_data:
                RecipeIngredient.objects.create(
                    recipe=instance,
                    ingredient=ingredient_data['id'],
                    quantity=ingredient_data['amount']
                )
        return instance

    def to_representation(self, instance):
        # Сначала вызываем стандартный `to_representation`
        representation = super().to_representation(instance)

        # Теперь заменяем поле `ingredients` на сериализатор для чтения
        ingredients_data = RecipeIngredientReadSerializer(
            instance.recipeingredient_set.all(),
            many=True
        ).data
        representation['ingredients'] = ingredients_data  # Обновляем поле
        representation['tags'] = TagSerializer(
            instance.tags.all(),
            many=True
        ).data
        representation['author'] = UserSerializer(
            instance.author,
            context=self.context
        ).data

        return representation


class RecipeShortSerializer(serializers.ModelSerializer):
    """Короткий для избранного"""
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')


class SubscriptionSerializer(UserSerializer):
    recipes = serializers.SerializerMethodField()  # Изменяем на SerializerMethodField
    recipes_count = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('recipes', 'recipes_count')

    def get_recipes(self, obj):
        """
        Возвращает рецепты автора с учётом ограничения recipes_limit.
        """
        request = self.context.get('request')
        recipes_limit = self.context.get('recipes_limit')  # Берём recipes_limit из контекста

        recipes = obj.recipes.all()  # Получаем все рецепты автора
        if recipes_limit:  # Применяем ограничение
            try:
                recipes = recipes[:int(recipes_limit)]
            except ValueError:
                pass  # Если параметр невалидный, игнорируем его

        return RecipeShortSerializer(recipes, many=True, context={'request': request}).data

    def get_recipes_count(self, obj):
        """
        Возвращает общее количество рецептов автора.
        """
        return obj.recipes.count()
