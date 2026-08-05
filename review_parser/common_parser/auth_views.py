from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

TOKEN_PAIR_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["access", "refresh"],
    properties={
        "access": openapi.Schema(type=openapi.TYPE_STRING, description="JWT access token"),
        "refresh": openapi.Schema(type=openapi.TYPE_STRING, description="JWT refresh token"),
    },
)

TOKEN_REFRESH_RESPONSE_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["access"],
    properties={
        "access": openapi.Schema(type=openapi.TYPE_STRING, description="Новый JWT access token"),
    },
)

LOGIN_BODY = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["username", "password"],
    properties={
        "username": openapi.Schema(type=openapi.TYPE_STRING, example="admin"),
        "password": openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_PASSWORD, example="admin"),
    },
)

REFRESH_BODY = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["refresh"],
    properties={
        "refresh": openapi.Schema(type=openapi.TYPE_STRING, description="Refresh token из POST /auth/token/"),
    },
)


class TokenObtainPairSwaggerView(TokenObtainPairView):
    @swagger_auto_schema(
        operation_summary="Получить JWT access/refresh",
        operation_description=(
            "Логин по username/password Django User.\n\n"
            "Скопируйте `access` и нажмите **Authorize** в Swagger — "
            "введите `Bearer <access>` (со словом Bearer и пробелом)."
        ),
        request_body=LOGIN_BODY,
        responses={
            200: openapi.Response("Пара токенов", TOKEN_PAIR_SCHEMA),
            401: "Неверный username или password",
        },
        tags=["auth"],
        security=[],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class TokenRefreshSwaggerView(TokenRefreshView):
    @swagger_auto_schema(
        operation_summary="Обновить JWT access",
        request_body=REFRESH_BODY,
        responses={
            200: openapi.Response("Новый access token", TOKEN_REFRESH_RESPONSE_SCHEMA),
            401: "Refresh token недействителен или просрочен",
        },
        tags=["auth"],
        security=[],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
