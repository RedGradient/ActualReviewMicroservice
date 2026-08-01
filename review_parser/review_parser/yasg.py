from django.urls import path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="Review Parser API",
        default_version="v1",
        description="""
API для парсинга и получения отзывов с платформ (Yandex, 2GIS, VL.RU).

**Эндпоинты v1 (`/api/v1/`):**
- `GET /api/v1/reviews/` — отзывы филиала по провайдеру (пагинация `limit`/`offset`)
- `POST /api/v1/sync/` — асинхронный запуск парсинга (ответ 202 + `task_id`)

**Провайдеры отзывов:** yandex, 2gis, vlru, google (google без парсера)
""",
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path(r"swagger(?P<format>\.json|\.yaml)", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
]
