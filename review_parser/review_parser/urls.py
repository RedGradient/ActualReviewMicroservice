from django.contrib import admin
from django.urls import include, path

from .yasg import urlpatterns as doc_urls

urlpatterns = [  # noqa: RUF005
    path("admin/", admin.site.urls),
    path("api/v1/", include("common_parser.urls")),
] + doc_urls
