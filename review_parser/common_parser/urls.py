from django.urls import path

from common_parser.views import get_reviews, sync_reviews

urlpatterns = [
    path("reviews/", get_reviews),
    path("sync/", sync_reviews),
]
