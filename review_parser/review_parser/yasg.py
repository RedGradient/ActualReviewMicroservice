from django.urls import path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


schema_view = get_schema_view(
   openapi.Info(
      title="Review Parser API",
      default_version='v1',
      description="""
API для парсинга и получения отзывов с различных платформ (Яндекс, Google, 2GIS, VL.RU)
и видео из плейлистов (YouTube, VK).

**Основные эндпоинты:**
- `GET /api/common/get_reviews/` — отзывы по ID филиала
- `GET /api/common/get_reviews_by_ip` — отзывы по IP (требуется Branch IP Mapping)
- `GET /api/common/v2/reviews` — отзывы v2 (рекомендуется, удобные query-параметры)
- `GET /api/common/v2/reviews_by_ip` — отзывы v2 по IP (рекомендуется)
- `GET /api/common/get_videos_by_ip` — видео по IP (требуется Playlist IP Mapping)

**Провайдеры отзывов:** yandex, 2gis, vlru (google выключен)
**Провайдеры видео:** youtube, vk
""",
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
   path(r'swagger(?P<format>\.json|\.yaml)', schema_view.without_ui(cache_timeout=0), name='schema-json'),
   path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
   path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]