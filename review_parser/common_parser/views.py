from celery.result import AsyncResult
from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from common_parser.models import Branch, BranchPlatform, Organization, Review
from common_parser.serializers import (
    BranchPlatformSerializer,
    BranchSerializer,
    GetReviewsSerializer,
    OrganizationSerializer,
    ReviewPublicSerializer,
    SyncReviewsSerializer,
    TaskQuerySerializer,
)
from common_parser.tasks import parse_providers_async

BEARER_AUTH = [{"Bearer": []}]

SYNC_ACCEPTED_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["task_id", "status"],
    properties={
        "task_id": openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_UUID,
            description="ID Celery-задачи для отслеживания статуса",
        ),
        "status": openapi.Schema(
            type=openapi.TYPE_STRING,
            enum=["PENDING", "STARTED", "SUCCESS", "FAILURE", "RETRY", "REVOKED"],
            description="Начальный статус задачи",
        ),
    },
    example={"task_id": "a3f2c1b0-4d8d-4e2a-9f1b-2c8d7e6f5a4b", "status": "pending"},
)

TASK_STATUS_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    required=["task_id", "status"],
    properties={
        "task_id": openapi.Schema(
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_UUID,
            description="ID Celery-задачи",
        ),
        "status": openapi.Schema(
            type=openapi.TYPE_STRING,
            enum=["PENDING", "STARTED", "SUCCESS", "FAILURE", "RETRY", "REVOKED"],
            description="Текущий статус задачи в Celery",
        ),
    },
    example={"task_id": "a3f2c1b0-4d8d-4e2a-9f1b-2c8d7e6f5a4b", "status": "SUCCESS"},
)


@swagger_auto_schema(
    method="GET",
    operation_summary="Получить отзывы филиала",
    operation_description=(
        "Возвращает список отзывов для указанного филиала и провайдера. "
        "Поддерживается пагинация через параметры `limit` и `offset`."
    ),
    query_serializer=GetReviewsSerializer,
    responses={
        200: ReviewPublicSerializer(many=True),
        400: "Некорректные query-параметры",
        404: "Филиал или платформа не найдены",
    },
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_reviews(request) -> Response:
    serializer = GetReviewsSerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)

    branch = get_object_or_404(Branch, pk=serializer.validated_data["branch_id"])
    branch_platform = get_object_or_404(
        BranchPlatform,
        branch=branch,
        provider=serializer.validated_data["provider"],
    )

    limit = serializer.validated_data["limit"]
    offset = serializer.validated_data["offset"]

    reviews = Review.objects.filter(branch_platform=branch_platform).order_by("-published_date")[
        offset : offset + limit
    ]

    return Response(ReviewPublicSerializer(reviews, many=True).data)


@swagger_auto_schema(
    method="POST",
    operation_summary="Запустить синхронизацию отзывов (async)",
    operation_description=(
        "Ставит в очередь Celery-задачу парсинга отзывов для указанных провайдеров филиала.\n\n"
        "Ответ **202 Accepted** содержит `task_id` — статус можно проверить через `GET /api/v1/tasks/?task_id=...` "
        "или Celery result backend (`django_celery_results` / `AsyncResult`).\n\n"
        "Ошибки по отдельным провайдерам не отменяют задачу целиком. "
        "Пример смешанного результата:\n"
        "```json\n"
        "{\n"
        '  "2gis": {"parsed": 10, "created": 3},\n'
        '  "vlru": {"parsed": 5, "created": 1},\n'
        '  "yandex": {"error": "branch_platform_not_found", "provider": "yandex"}\n'
        "}\n"
        "```\n\n"
        "Если организация или филиал не найдены, задача завершится с объектом "
        '`{"error": "organization_not_found", ...}` или `{"error": "branch_not_found", ...}`.'
    ),
    request_body=SyncReviewsSerializer,
    responses={
        202: openapi.Response(
            description="Задача принята в обработку",
            schema=SYNC_ACCEPTED_SCHEMA,
        ),
        400: "Некорректное тело запроса",
    },
    tags=["sync"],
    security=BEARER_AUTH,
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sync_reviews(request) -> Response:
    serializer = SyncReviewsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    task: AsyncResult = parse_providers_async(
        providers=serializer.validated_data["providers"],
        organization_id=serializer.validated_data["organization_id"],
        branch_id=serializer.validated_data["branch_id"],
    )

    return Response(
        {
            "task_id": task.id,
            "status": task.status,
        },
        status=status.HTTP_202_ACCEPTED,
    )


@swagger_auto_schema(
    method="GET",
    operation_summary="Получить статус Celery-задачи",
    operation_description=(
        "Возвращает текущий статус фоновой задачи по query-параметру `task_id`, "
        "полученному из `POST /api/v1/sync/`.\n\n"
        "**Статусы Celery:**\n"
        "- `PENDING` — в очереди или worker ещё не отметил старт\n"
        "- `STARTED` — выполняется\n"
        "- `SUCCESS` — завершена успешно\n"
        "- `FAILURE` — завершена с ошибкой\n"
        "- `RETRY` — повторная попытка\n"
        "- `REVOKED` — отменена\n\n"
        "Результат выполненной задачи (`parse_providers_async`) доступен через Celery result backend "
        "(`AsyncResult(task_id).result` / таблица `django_celery_results_taskresult`)."
    ),
    manual_parameters=[
        openapi.Parameter(
            "task_id",
            openapi.IN_QUERY,
            description="ID Celery-задачи (UUID)",
            type=openapi.TYPE_STRING,
            format=openapi.FORMAT_UUID,
            required=True,
        ),
    ],
    responses={
        200: openapi.Response(
            description="Статус задачи",
            schema=TASK_STATUS_SCHEMA,
        ),
        400: "Некорректные query-параметры",
    },
    tags=["sync"],
    security=BEARER_AUTH,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tasks(request) -> Response:
    serializer = TaskQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    task_id = serializer.validated_data["task_id"]
    task = AsyncResult(task_id)
    if task.result:
        return Response({"task_id": task_id, "status": task.status, "result": task.result})
    return Response({"task_id": task_id, "status": task.status})


class CreateReadDeleteModelViewSet(ModelViewSet):
    http_method_names = ["get", "post", "delete"]  # noqa: RUF012


class OrganizationView(CreateReadDeleteModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer


class BranchView(CreateReadDeleteModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer


class BranchPlatformView(CreateReadDeleteModelViewSet):
    queryset = BranchPlatform.objects.all()
    serializer_class = BranchPlatformSerializer
