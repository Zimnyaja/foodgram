from django.urls import path

from api.views import redirect_short_link

urlpatterns = [
    path('s/<str:code>/', redirect_short_link)
]
