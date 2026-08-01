from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from common_parser.models import Branch, BranchPlatform, Review
from common_parser.serializers import GetReviewsSerializer, ReviewSerializer, SyncReviewsSerializer
from common_parser.tasks import parse_providers_async

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
            enum=["pending", "success", "error"],
            description="Начальный статус задачи",
        ),
    },
    example={"task_id": "a3f2c1b0-4d8d-4e2a-9f1b-2c8d7e6f5a4b", "status": "pending"},
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
        200: ReviewSerializer(many=True),
        400: "Некорректные query-параметры",
        404: "Филиал или платформа не найдены",
    },
)
@api_view(["GET"])
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

    return Response(ReviewSerializer(reviews, many=True).data)


@swagger_auto_schema(
    method="POST",
    operation_summary="Запустить синхронизацию отзывов (async)",
    operation_description=(
        "Ставит в очередь Celery-задачу парсинга отзывов для указанных провайдеров филиала.\n\n"
        "Ответ **202 Accepted** содержит `task_id` — по нему можно проверить статус через Celery result backend "
        "(`django_celery_results` / `AsyncResult`).\n\n"
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
)
@api_view(["POST"])
def sync_reviews(request) -> Response:
    serializer = SyncReviewsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    task = parse_providers_async.delay(
        providers=serializer.validated_data["providers"],
        organization_id=serializer.validated_data["organization_id"],
        branch_id=serializer.validated_data["branch_id"],
    )

    return Response(
        {
            "task_id": task.id,
            "status": "pending",
        },
        status=status.HTTP_202_ACCEPTED,
    )
