from django.urls import path
from common_parser.views_common.vlru import parse_vlru

urlpatterns = [
    path('parse/', parse_vlru, name='parse-vlru'),
]