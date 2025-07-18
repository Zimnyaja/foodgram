from django.urls import path

from .views import redirect_short_link

urlpatterns = [
    path('s/<str:code>/', redirect_short_link)
]
