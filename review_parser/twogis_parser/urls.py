from django.urls import path
from .views import parse_2gis

urlpatterns = [
    path('parse/', parse_2gis, name='parse-2gis'),
]