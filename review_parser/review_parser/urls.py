from django.contrib import admin
from django.urls import include, path

from common_parser.views import webhook

from .yasg import urlpatterns as doc_urls

urlpatterns = [  # noqa: RUF005
    path("admin/", admin.site.urls),
    path("api/yandex/", include("common_parser.urls_common.yandex")),
    path("api/twogis/", include("common_parser.urls_common.twogis")),
    path("api/vlru/", include("common_parser.urls_common.vlru")),
    path("api/v1/", include("common_parser.urls")),
    # path("api/common/", include("common_parser.urls")),
    path("api/test/webhook", webhook),
] + doc_urls
