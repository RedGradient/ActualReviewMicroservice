from django.contrib.auth.models import User
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

USER_EXISTS_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["detail"],
    properties={
        "detail": openapi.Schema(type=openapi.TYPE_STRING, example="username already exists"),
    },
)


class RegisterRequestSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True, min_length=8)


class RegisterResponseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()


def _create_user(username: str, password: str) -> User:
    return User.objects.create_user(
        username=username,
        password=password,
    )


@swagger_auto_schema(
    method="post",
    operation_summary="Регистрация пользователя",
    operation_description=(
        "Создаёт Django User. После регистрации войдите через `POST /auth/token/` с теми же username и password."
    ),
    request_body=RegisterRequestSerializer,
    responses={
        201: RegisterResponseSerializer,
        400: openapi.Response("Username уже занят или некорректные данные", USER_EXISTS_SCHEMA),
    },
    tags=["auth"],
    security=[],
)
@api_view(["POST"])
def create_user(request) -> Response:
    serializer = RegisterRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    username = serializer.validated_data["username"]
    if User.objects.filter(username=username).exists():
        return Response(
            {"detail": "username already exists"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = _create_user(username, serializer.validated_data["password"])
    return Response(
        RegisterResponseSerializer({"id": user.id, "username": user.username}).data,
        status=status.HTTP_201_CREATED,
    )
