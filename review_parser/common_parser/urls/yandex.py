from django.urls import path
from review_parser.common_parser.views.yandex import parse_yandex

urlpatterns = [
    path('parse/', parse_yandex, name='parse-yandex'),
]