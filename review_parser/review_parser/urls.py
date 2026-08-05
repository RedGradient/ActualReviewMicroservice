from django.contrib import admin
from django.urls import include, path

from common_parser.auth_views import TokenObtainPairSwaggerView, TokenRefreshSwaggerView

from . import admin_index  # noqa: F401
from .yasg import urlpatterns as doc_urls

urlpatterns = [  # noqa: RUF005
    path("admin/", admin.site.urls),
    path("api/v1/", include("common_parser.urls")),
    path("auth/token/", TokenObtainPairSwaggerView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshSwaggerView.as_view(), name="token_refresh"),
] + doc_urls
