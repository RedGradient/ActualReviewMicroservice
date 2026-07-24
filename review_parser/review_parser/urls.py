from django.contrib import admin
from django.urls import path, include
from .yasg import urlpatterns as doc_urls
from common_parser.views import webhook

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/yandex/', include('yandex_parser.urls')),
    path('api/twogis/', include('twogis_parser.urls')),
    path('api/vlru/', include('vl_parser.urls')),
    path('api/common/', include('common_parser.urls')),
    path('api/test/webhook', webhook),
] + doc_urls
