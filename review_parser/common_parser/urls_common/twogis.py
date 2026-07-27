from django.urls import path
from common_parser.views_common.twogis import parse_2gis

urlpatterns = [
    path('parse/', parse_2gis, name='parse-2gis'),
]