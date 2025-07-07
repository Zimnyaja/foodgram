from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import get_object_or_404

from rest_framework import serializers

from api.fields import Base64ImageField
from recipes.models import Ingredient, Recipe, Tag, Favorite, ShoppingList, RecipeIngredient
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
        fields = ['email', 'id', 'username', 'first_name', 'last_name', 'password']
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
    ingredient = IngredientSerializer(read_only=True)

    class Meta:
        model = RecipeIngredient
        fields = ['ingredient', 'quantity']


class RecipeIngredientWriteSerializer(serializers.ModelSerializer):
    ingredient = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())

    class Meta:
        model = RecipeIngredient
        fields = ['ingredient', 'quantity']


class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientWriteSerializer(many=True, write_only=True)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    tags = serializers.PrimaryKeyRelatedField(queryset=Tag.objects.all(), many=True)

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
            return Favorite.objects.filter(user=request.user, recipe=obj).exists()
        return False

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return ShoppingList.objects.filter(user=request.user, recipe=obj).exists()
        return False

    def create(self, validated_data):
        tags_data = validated_data.pop('tags', [])
        print(tags_data)
        ingredients_data = validated_data.pop('ingredients')
        print("Ingredients Data:", ingredients_data)
        recipe = Recipe.objects.create(**validated_data)
        recipe.tags.set(tags_data)

        for ingredient_data in ingredients_data:
            ingredient = ingredient_data['ingredient']  # получение объекта
            quantity = ingredient_data['quantity']
            RecipeIngredient.objects.create(recipe=recipe, ingredient=ingredient, quantity=quantity)

        return recipe
    
    def to_representation(self, instance):
        # Сначала вызываем стандартный `to_representation`
        representation = super().to_representation(instance)

        # Теперь заменяем поле `ingredients` на сериализатор для чтения
        ingredients_data = RecipeIngredientReadSerializer(instance.recipeingredient_set, many=True).data
        representation['ingredients'] = ingredients_data  # Обновляем поле `ingredients`

        return representation


class RecipeShortSerializer(serializers.ModelSerializer):
    """Короткий для избранного"""
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')
        read_only_fields = ('id', 'name', 'image', 'cooking_time')


class SubscriptionSerializer(UserSerializer):
    recipes = RecipeShortSerializer(many=True, read_only=True)
    recipes_count = serializers.IntegerField(source='recipes.count', read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('recipes', 'recipes_count')
