from django.contrib.auth import get_user_model
from django.db.models import BooleanField, Exists, OuterRef, Sum, Value
from django_filters.rest_framework import DjangoFilterBackend
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from djoser.views import UserViewSet as DjoserUserViewSet

from rest_framework import decorators, permissions, response, status, viewsets
from rest_framework.response import Response

from recipes.utils.shortener import encode_id
from api.filters import RecipeFilter
from api.serializers import (
    IngredientSerializer, RecipeReadSerializer, RecipeSerializer,
    RecipeShortSerializer, SubscriptionSerializer, TagSerializer,
    UserSerializer, UserAvatarSerializer
)
from api.paginators import RecipePagination
from api.permissions import IsAuthorOrReadOnly
from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                            Tag, ShoppingList)
from users.models import Subscription

User = get_user_model()


class UserViewSet(DjoserUserViewSet):
    queryset = User.objects.all()
    pagination_class = RecipePagination
    lookup_field = 'id'
    serializer_class = UserSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @decorators.action(
        detail=False,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return response.Response(serializer.data)

    @decorators.action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def subscribe(self, request, id=None):
        """Подписка на пользователя."""
        user = request.user
        author = get_object_or_404(User, id=id)

        if request.method == 'POST':
            if user == author:
                return response.Response(
                    {'errors': 'Нельзя подписаться на самого себя.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            subscription, created = Subscription.objects.get_or_create(
                user=user,
                subscribed_to=author
            )

            if not created:
                # Если объект уже существует
                return response.Response(
                    {'errors': 'Вы уже подписаны на этого пользователя.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer = SubscriptionSerializer(
                author,
                context={'request': request}
            )
            return response.Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        # Delete. Мне не понравилось выносить на 2 разных метода, код местами
        # начинает дублироваться. Кажется, что вся подписка в одном методе
        # компактнее выглядит
        subscription = Subscription.objects.filter(
            user=user, subscribed_to=author
        )
        deleted_count, _ = subscription.delete()
        if deleted_count == 0:
            # Если удаление ничего не удалило, значит подписки не существовало
            return response.Response(
                {'errors': 'Вы не подписаны на этого пользователя.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return response.Response(status=status.HTTP_204_NO_CONTENT)

    @decorators.action(
        detail=False,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def subscriptions(self, request):
        """
        Список подписок текущего пользователя без пагинации.
        """
        # Получаем всех авторов, на которых подписан пользователь
        user = request.user
        subscribed_authors = User.objects.filter(subscribers__user=user)

        paginator = RecipePagination()
        page = paginator.paginate_queryset(subscribed_authors, request)

        recipes_limit = request.query_params.get('recipes_limit')

        if page is not None:
            # Если есть пагинация, сериализуем только текущую страницу
            serializer = SubscriptionSerializer(
                page, many=True,
                context={'request': request, 'recipes_limit': recipes_limit}
            )
            return paginator.get_paginated_response(serializer.data)

        # Если параметры пагинации отсутствуют, возвращаем полный список
        serializer = SubscriptionSerializer(
            subscribed_authors, many=True,
            context={'request': request, 'recipes_limit': recipes_limit}
        )
        return Response(serializer.data)

    @decorators.action(
        detail=False,
        methods=['put', 'delete'],
        permission_classes=[permissions.IsAuthenticated],
        url_path='me/avatar'
    )
    def avatar(self, request):
        """Обновление или удаление аватара текущего пользователя."""
        user = request.user

        if request.method == 'PUT':
            serializer = UserAvatarSerializer(
                user, data=request.data,
                partial=True,
                context={'request': request}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return response.Response(
                serializer.data, status=status.HTTP_200_OK
            )

        user.avatar.delete(save=True)  # Удаляем файл и сохраняем модель
        return response.Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        return queryset


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly
    ]
    pagination_class = RecipePagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = RecipeFilter

    def get_serializer_class(self):
        """
        Возвращает сериализатор в зависимости от типа действия (action).
        """
        if self.action in ('list', 'retrieve'):  # Чтение рецептов
            return RecipeReadSerializer
        return RecipeSerializer  # Запись/обновление рецептов

    def get_queryset(self):
        """
        Оптимизация запросов через аннотации для избранного и корзины.
        """
        queryset = super().get_queryset()
        if self.request.user.is_authenticated:
            queryset = queryset.annotate(
                is_favorited=Exists(
                    Favorite.objects.filter(
                        user=self.request.user, recipe=OuterRef('pk')
                    )
                ),
                is_in_shopping_cart=Exists(
                    ShoppingList.objects.filter(
                        user=self.request.user, recipe=OuterRef('pk')
                    )
                )
            )
        else:
            queryset = queryset.annotate(
                is_favorited=Value(False, output_field=BooleanField()),
                is_in_shopping_cart=Value(False, output_field=BooleanField())
            )
        return queryset

    @decorators.action(detail=True, methods=['get'], url_path='get-link')
    def get_short_link(self, request, pk=None):
        try:
            recipe = self.get_object()
        except Recipe.DoesNotExist:
            return Response({'error': 'Recipe not found'}, status=404)

        short_code = encode_id(recipe.id)
        full_link = request.build_absolute_uri(f'/s/{short_code}')
        return Response({'short-link': full_link})

    def manage_object(self, model, pk, request, add_message, remove_message):
        """
        Общий метод для добавления и удаления объектов (Favorite, ShoppingList)
        """
        recipe = get_object_or_404(Recipe, id=pk)
        user = request.user
        if request.method == 'POST':
            obj, created = model.objects.get_or_create(
                user=user, recipe=recipe
            )
            if not created:
                return Response(
                    {'detail': add_message},
                    status=status.HTTP_400_BAD_REQUEST
                )
            serializer = RecipeShortSerializer(
                recipe, context={'request': request}
            )
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        # Удаление объекта
        deleted_count, _ = model.objects.filter(
            user=user, recipe=recipe
        ).delete()
        if deleted_count == 0:
            return Response(
                {'detail': remove_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            {'detail': remove_message},
            status=status.HTTP_204_NO_CONTENT
        )

    @decorators.action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        """Добавление/удаление рецепта в избранное."""
        return self.manage_object(
            model=Favorite,
            pk=pk,
            request=request,
            add_message='Рецепт уже в избранном.',
            remove_message='Рецепт удалён из избранного.'
        )

    @decorators.action(
        detail=True, methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        """Добавление и удаление рецепта из списка покупок."""
        return self.manage_object(
            model=ShoppingList,
            pk=pk,
            request=request,
            add_message='Рецепт уже в списке покупок.',
            remove_message='Рецепт удалён из списка покупок.'
        )

    @decorators.action(
        detail=False, methods=['get'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        """Скачать список покупок в виде TXT файла."""
        user = request.user

        # Получаем все ингредиенты через связь: рецепты -> корзина -> юзер
        ingredients = (
            RecipeIngredient.objects
            .filter(recipe__shoppinglist_set__user=user)
            .values('ingredient__name', 'ingredient__measurement_unit')
            .annotate(total_quantity=Sum('quantity'))
            .order_by('ingredient__name')  # Упорядочиваем по названию
        )

        if not ingredients.exists():
            return Response({'detail': 'Список покупок пуст.'}, status=400)

        # Формируем текстовое содержимое для файла
        content = 'Список покупок:\n\n'
        for item in ingredients:
            content += (
                f"{item['ingredient__name']} — "
                f"{item['total_quantity']} "
                f"{item['ingredient__measurement_unit']}\n")

        # Генерируем HTTP-ответ с содержимым файла
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response
