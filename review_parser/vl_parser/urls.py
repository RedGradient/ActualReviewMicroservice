from django.urls import path
from .views import parse_vlru

urlpatterns = [
    path('parse/', parse_vlru, name='parse-vlru'),
]