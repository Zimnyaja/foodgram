from collections import defaultdict
from django.conf import settings
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404

from rest_framework import decorators, permissions, response, status, viewsets
from rest_framework.response import Response

from .utils.shortener import decode_code, encode_id
from api.serializers import (IngredientSerializer, RecipeSerializer,
                             SubscriptionSerializer, TagSerializer,
                             UserCreateSerializer, UserSerializer,
                             UserAvatarSerializer)
from api.paginators import RecipePagination
from api.permissions import AdminOrReadOnlyPermission
from recipes.models import (Favorite, Ingredient, Recipe, RecipeIngredient,
                            Tag, ShoppingList)
from users.models import Subscription

User = get_user_model()


def redirect_short_link(request, code):
    recipe_id = decode_code(code)
    if recipe_id is None:
        raise Http404("Invalid short link")
    try:
        Recipe.objects.get(id=recipe_id)
    except Recipe.DoesNotExist:
        raise Http404("Recipe not found")
    return HttpResponseRedirect(f'/recipes/{recipe_id}')


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    pagination_class = RecipePagination
    lookup_field = 'id'

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ['retrieve', 'me', 'subscriptions']:
            return SubscriptionSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        if self.action in ['list', 'retrieve', 'me']:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @decorators.action(
        detail=False,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def me(self, request):
        """Возвращает данные текущего авторизованного пользователя."""
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

            subscription = Subscription.objects.filter(
                user=user, subscribed_to=author
            )

            if subscription.exists():
                return response.Response(
                    {'errors': 'Вы уже подписаны на этого пользователя.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            Subscription.objects.create(user=user, subscribed_to=author)
            serializer = self.get_serializer(
                author, context={'request': request}
            )
            return response.Response(
                serializer.data, status=status.HTTP_201_CREATED
            )

        if request.method == 'DELETE':
            subscription = Subscription.objects.filter(
                user=user, subscribed_to=author
            )
            if not subscription.exists():
                return response.Response(
                    {'errors': 'Вы не подписаны на этого пользователя.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            subscription.delete()
            return response.Response(status=status.HTTP_204_NO_CONTENT)

    @decorators.action(
        detail=False,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def subscriptions(self, request):
        user = request.user
        subscribed_authors = User.objects.filter(subscribers__user=user)
        page = self.paginate_queryset(subscribed_authors)
        serializer = SubscriptionSerializer(
            page, many=True,
            context={'request': request}
        )
        return self.get_paginated_response(serializer.data)

    @decorators.action(
        detail=False,
        methods=['put', 'patch', 'delete'],
        permission_classes=[permissions.IsAuthenticated],
        url_path='me/avatar'
    )
    def avatar(self, request):
        """Обновление или удаление аватара текущего пользователя."""
        user = request.user

        if request.method in ['PUT', 'PATCH']:
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

        if request.method == 'DELETE':
            user.avatar.delete(save=True)  # Удаляем файл и сохраняем модель
            return response.Response(status=status.HTTP_204_NO_CONTENT)

    @decorators.action(
        detail=False,
        methods=['post', 'put', 'patch'],
        permission_classes=[permissions.IsAuthenticated],
        url_path='set_password'
    )
    def set_password(self, request):
        user = request.user
        current_password = request.data.get('current_password')
        new_password = request.data.get('new_password')

        if not current_password or not new_password:
            return Response({'detail': 'Текущий и новый пароли обязательны.'},
                            status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(current_password):
            return Response({'current_password': 'Неверный пароль.'},
                            status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)
        return Response(
            {'detail': 'Пароль успешно изменён.'},
            status=status.HTTP_204_NO_CONTENT
        )


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    # lookup_field = "slug"
    # filter_backends = (filters.SearchFilter,)
    # search_fields = ('name',)
    permission_classes = (AdminOrReadOnlyPermission,)


class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    # filter_backends = (filters.SearchFilter,)
    # search_fields = ('^name',)
    # search_param = 'name'

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        return queryset


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = RecipePagination

    def get_queryset(self):
        queryset = super().get_queryset()
        tags = self.request.query_params.getlist('tags')
        author_id = self.request.query_params.get('author')

        if tags:
            queryset = queryset.filter(tags__slug__in=tags).distinct()
        if author_id:
            queryset = queryset.filter(author_id=author_id)
        if self.request.user.is_authenticated:
            is_favorited = bool(
                int(self.request.query_params.get('is_favorited', 0))
            )
            is_in_shopping_cart = bool(
                int(self.request.query_params.get('is_in_shopping_cart', 0))
            )
            if is_favorited:
                queryset = queryset.filter(
                    favorite__user=self.request.user
                ).distinct()
            if is_in_shopping_cart:
                queryset = queryset.filter(
                    shoppinglist__user=self.request.user
                ).distinct()

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(author=user,)

    @decorators.action(detail=True, methods=['get'], url_path='get-link')
    def get_short_link(self, request, pk=None):
        try:
            recipe = self.get_object()
        except Recipe.DoesNotExist:
            return Response({'error': 'Recipe not found'}, status=404)

        short_code = encode_id(recipe.id)
        full_link = f'{settings.DOMAIN_NAME}/s/{short_code}'
        return Response({'short-link': full_link})

    @decorators.action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        """Добавление/удаление рецепта в избранное."""
        recipe = get_object_or_404(Recipe, id=pk)
        user = request.user

        if request.method == 'POST':
            if Favorite.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'detail': 'Рецепт уже в избранном.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            Favorite.objects.create(user=user, recipe=recipe)
            return Response(
                {'detail': 'Добавлено в избранное.'},
                status=status.HTTP_201_CREATED
            )

        if request.method == 'DELETE':
            favorite = Favorite.objects.filter(user=user, recipe=recipe)
            if not favorite.exists():
                return Response(
                    {'detail': 'Рецепт не в избранном.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            favorite.delete()
            return Response(
                {'detail': 'Удалено из избранного.'},
                status=status.HTTP_204_NO_CONTENT
            )

    @decorators.action(
        detail=True, methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        """Добавление и удаление рецепта из списка покупок."""
        recipe = get_object_or_404(Recipe, id=pk)
        user = request.user

        if request.method == 'POST':
            if ShoppingList.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'detail': 'Рецепт уже в списке покупок.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            ShoppingList.objects.create(user=user, recipe=recipe)
            return Response(
                {'detail': 'Добавлено в список покупок.'},
                status=status.HTTP_201_CREATED
            )

        if request.method == 'DELETE':
            item = ShoppingList.objects.filter(user=user, recipe=recipe)
            if not item.exists():
                return Response(
                    {'detail': 'Рецепта нет в списке покупок.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            item.delete()
            return Response(
                {'detail': 'Удалено из списка покупок.'},
                status=status.HTTP_204_NO_CONTENT
            )

    @decorators.action(
        detail=False, methods=['get'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        """Скачать список покупок в виде TXT файла."""
        user = request.user

        # Находим все рецепты пользователя в списке покупок
        recipes = Recipe.objects.filter(shoppinglist__user=user)

        # Словарь: имя ингредиента -> [общее количество, единица измерения]
        ingredients = defaultdict(lambda: [0, ''])

        # Собираем ингредиенты по всем рецептам
        recipe_ingredients = RecipeIngredient.objects.filter(
            recipe__in=recipes
        )

        for item in recipe_ingredients:
            name = item.ingredient.name
            unit = item.ingredient.measurement_unit
            ingredients[name][0] += item.quantity
            ingredients[name][1] = unit

        if not ingredients:
            return Response({'detail': 'Список покупок пуст.'}, status=400)

        # Сформировать текстовое содержимое
        content = 'Список покупок:\n\n'
        for name, (quantity, unit) in ingredients.items():
            content += f'{name} — {quantity} {unit}\n'

        # Вернуть как TXT-файл
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response
