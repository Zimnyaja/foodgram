from rest_framework import filters, decorators, viewsets, permissions, response, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.shortcuts import get_object_or_404, render

from api.serializers import (IngredientSerializer, RecipeSerializer,
                             SubscriptionSerializer, TagSerializer,
                             UserCreateSerializer, UserSerializer,
                             UserAvatarSerializer)
from api.paginators import RecipePagination
from api.permissions import AdminOrReadOnlyPermission
from recipes.models import Favorite, Ingredient, Recipe, Tag, ShoppingList
from users.models import Subscription

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    pagination_class = RecipePagination

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
        methods=['post'],
        permission_classes=[permissions.IsAuthenticated]
    )
    def subscribe(self, request, id=None):
        """Подписка на пользователя."""
        user = request.user
        author = get_object_or_404(User, id=id)

        if user == author:
            return response.Response(
                {'errors': 'Нельзя подписаться на самого себя.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        subscription = Subscription.objects.filter(user=user, author=author)

        if subscription.exists():
            return response.Response(
                {'errors': 'Вы уже подписаны на этого пользователя.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        Subscription.objects.create(user=user, subscribed_to=author)
        serializer = self.get_serializer(author, context={'request': request})
        return response.Response(serializer.data, status=status.HTTP_201_CREATED)

    @decorators.action(
        detail=True,
        methods=['delete'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def unsubscribe(self, request, id=None):
        """Отписка от пользователя."""
        user = request.user
        author = get_object_or_404(User, id=id)

        subscription = Subscription.objects.filter(user=user, subscribed_to=author)
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
        serializer = SubscriptionSerializer(page, many=True, context={'request': request})
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
            serializer = UserAvatarSerializer(user, data=request.data, partial=True, context={'request': request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return response.Response(serializer.data, status=status.HTTP_200_OK)

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
            return Response({"detail": "Текущий и новый пароли обязательны."},
                            status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(current_password):
            return Response({"current_password": "Неверный пароль."},
                            status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        update_session_auth_hash(request, user)
        return Response({"detail": "Пароль успешно изменён."}, status=status.HTTP_204_NO_CONTENT)


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
    filter_backends = (filters.SearchFilter,)
    search_fields = ('^name',)


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
            is_favorited = bool(int(self.request.query_params.get('is_favorited', 0)))
            is_in_shopping_cart = bool(int(self.request.query_params.get('is_in_shopping_cart', 0)))
            if is_favorited:
                queryset = queryset.filter(favorite__user=self.request.user).distinct()
            if is_in_shopping_cart:
                queryset = queryset.filter(shoppinglist__user=self.request.user).distinct()

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        serializer.save(author=user,)

    # pagination_class = PageNumberPagination

    # def perform_create(self, serializer):
    #     serializer.save(owner=self.request.user)


class FavoriteToggle(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, recipe_id):
        recipe = get_object_or_404(Recipe, id=recipe_id)
        favorite, created = Favorite.objects.get_or_create(user=request.user, recipe=recipe)
        if not created:
            favorite.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShoppingListToggle(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, recipe_id):
        recipe = get_object_or_404(Recipe, id=recipe_id)
        shopping_item, created = ShoppingList.objects.get_or_create(user=request.user, recipe=recipe)
        if not created:
            shopping_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)