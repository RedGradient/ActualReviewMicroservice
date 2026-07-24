from django.urls import path
from .views import get_reviews, get_reviews_by_ip, get_videos_by_ip
from .views_v2 import reviews_v2, reviews_by_ip_v2

urlpatterns = [
    path('get_reviews/', get_reviews, name='get-reviews'),
    path('get_reviews_by_ip', get_reviews_by_ip, name='get-reviews-by-ip'),
    path('get_videos_by_ip', get_videos_by_ip, name='get-videos-by-ip'),
    path('v2/reviews', reviews_v2, name='reviews-v2'),
    path('v2/reviews_by_ip', reviews_by_ip_v2, name='reviews-by-ip-v2'),
]