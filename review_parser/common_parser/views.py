from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from common_parser.models import Branch, BranchPlatform, Organization, Review
from common_parser.parsers.registry import get_review_parser
from common_parser.serializers import GetReviewsSerializer, ReviewSerializer, SyncReviewsSerializer

VALID_PROVIDERS = [choice[0] for choice in BranchPlatform.PROVIDER_CHOICES]

SYNC_RESULT_SCHEMA = openapi.Schema(
    type=openapi.TYPE_OBJECT,
    properties={
        "parsed": openapi.Schema(type=openapi.TYPE_INTEGER, description="Количество обработанных отзывов"),
        "created": openapi.Schema(type=openapi.TYPE_INTEGER, description="Количество новых отзывов"),
    },
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
    operation_summary="Синхронизировать отзывы",
    operation_description=(
        "Запускает парсинг отзывов для указанных провайдеров филиала. "
        "Для каждого провайдера должна быть настроена ссылка на платформу (`BranchPlatform.url`)."
    ),
    request_body=SyncReviewsSerializer,
    responses={
        200: openapi.Response(
            description="Результат синхронизации по каждому провайдеру",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                additional_properties=SYNC_RESULT_SCHEMA,
                example={"2gis": {"parsed": 10, "created": 3}, "vlru": {"parsed": 5, "created": 1}},
            ),
        ),
        404: "Организация, филиал или платформа не найдены",
    },
)
@api_view(["POST"])
def sync_reviews(request) -> Response:
    serializer = SyncReviewsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    organization = get_object_or_404(Organization, pk=serializer.validated_data["organization_id"])
    branch = get_object_or_404(Branch, pk=serializer.validated_data["branch_id"])

    results = {}
    for provider in serializer.validated_data["providers"]:
        branch_platform = get_object_or_404(BranchPlatform, branch=branch, provider=provider)
        if not branch_platform.url:
            results[provider] = None
            continue

        parser = get_review_parser(provider)
        result = parser.run(
            url=branch_platform.url, org_name=organization.name, inn=organization.inn, address=branch.address
        )

        results[provider] = result

    return Response(results)
