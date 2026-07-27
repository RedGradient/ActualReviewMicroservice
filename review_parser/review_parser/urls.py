from django.contrib import admin
from django.urls import path, include
from .yasg import urlpatterns as doc_urls
from common_parser.views import webhook

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/yandex/', include('common_parser.urls.yandex')),
    path('api/twogis/', include('common_parser.urls.twogis')),
    path('api/vlru/', include('common_parser.urls.vlru')),
    path('api/common/', include('common_parser.urls')),
    path('api/test/webhook', webhook),
] + doc_urls
