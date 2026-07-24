from django.urls import path
from .views import parse_yandex

urlpatterns = [
    path('parse/', parse_yandex, name='parse-yandex'),
]