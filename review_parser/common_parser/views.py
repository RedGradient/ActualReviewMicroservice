from django.db.models import Count, Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from common_parser.services.reviews_query import (
    get_reviews_response_for_branches,
)

from .models import Branch, BranchIPMapping, PlaylistIPMapping, Video
from .serializers import BranchSerializer, PlaylistSerializer, ReviewSerializer, VideoSerializer


class ProviderSerializer(serializers.Serializer):
    provider = serializers.CharField()
    count = serializers.IntegerField()


PROVIDER_CHOICES = ["yandex", "google", "2gis", "vlru"]


@swagger_auto_schema(
    method="GET",
    manual_parameters=[
        openapi.Parameter(
            "branch_id", openapi.IN_QUERY, description="Идентификатор филиала", type=openapi.TYPE_STRING, required=True
        ),
        openapi.Parameter(
            "only_providers",
            openapi.IN_QUERY,
            description="Только из списка провайдеров",
            type=openapi.TYPE_BOOLEAN,
            required=False,
        ),
        openapi.Parameter(
            "limit",
            openapi.IN_QUERY,
            description="Пагинация: количество отзывов",
            type=openapi.TYPE_INTEGER,
            required=False,
        ),
        openapi.Parameter(
            "offset", openapi.IN_QUERY, description="Пагинация: смещение", type=openapi.TYPE_INTEGER, required=False
        ),
        openapi.Parameter(
            "provider",
            openapi.IN_QUERY,
            description="Новый формат: один провайдер (yandex/2gis/vlru)",
            type=openapi.TYPE_STRING,
            required=False,
        ),
        openapi.Parameter(
            "count",
            openapi.IN_QUERY,
            description="Новый формат: лимит на провайдера (если providers=csv)",
            type=openapi.TYPE_INTEGER,
            required=False,
        ),
        openapi.Parameter(
            "providers",
            openapi.IN_QUERY,
            description="Список провайдеров",
            type=openapi.TYPE_ARRAY,
            items=openapi.Items(
                type=openapi.TYPE_OBJECT,
                properties={
                    "provider": openapi.Schema(
                        type=openapi.TYPE_STRING, title="Название провайдера", enum=PROVIDER_CHOICES
                    ),
                    "count": openapi.Schema(type=openapi.TYPE_INTEGER, title="Количество записей"),
                    "filters": openapi.Schema(type=openapi.TYPE_STRING, title="Фильтры"),
                },
            ),
            required=False,
        ),
    ],
    responses={
        200: """
                        "branch": {
                            "id", "address", "organization",
                            "google_map_url", "yandex_map_url", "twogis_map_url", "vlru_url", "vlru_org_id",
                            "google_review_count", "google_review_avg", "google_parse_date",
                            "yandex_review_count", "yandex_review_avg", "yandex_parse_date",
                            "twogis_review_count", "twogis_review_avg", "twogis_parse_date",
                            "vlru_review_count", "vlru_review_avg", "vlru_parse_date"
                        },
                        "provider_reviews_count": [{"provider", "review_count"}],
                        "reviews": [
                            {"id", "author", "avatar", "video", "photos", "published_date",
                             "rating", "content", "provider", "branch", "review_url"}
                        ]
                                """,
        400: "Некорректные данные",
    },
)
@api_view(["GET"])
def get_reviews(request):
    branch_id = request.query_params.get("branch_id")
    if not branch_id:
        return Response({"detail": "branch_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        branch = Branch.objects.get(id=branch_id)
    except Branch.DoesNotExist:
        return Response({"detail": "Branch not found"}, status=status.HTTP_404_NOT_FOUND)

    service_result = get_reviews_response_for_branches(branches=[branch], query_params=request.query_params)
    reviews_data = ReviewSerializer(service_result["reviews"], many=True).data

    branch_serializer = BranchSerializer(branch)

    data = {
        "branch": branch_serializer.data,
        "provider_reviews_count": service_result["provider_reviews_count"],
        "reviews": reviews_data,
    }

    return Response(data)


@swagger_auto_schema(
    method="GET",
    manual_parameters=[
        openapi.Parameter(
            "only_providers",
            openapi.IN_QUERY,
            description="Только из списка провайдеров",
            type=openapi.TYPE_BOOLEAN,
            required=False,
        ),
        openapi.Parameter(
            "providers",
            openapi.IN_QUERY,
            description="Список провайдеров",
            type=openapi.TYPE_ARRAY,
            items=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    "provider": openapi.Schema(
                        type=openapi.TYPE_STRING, title="Название провайдера", enum=PROVIDER_CHOICES
                    ),
                    "count": openapi.Schema(type=openapi.TYPE_INTEGER, title="Количество записей"),
                    "filters": openapi.Schema(type=openapi.TYPE_STRING, title="Фильтры"),
                },
            ),
            required=False,
        ),
    ],
    responses={
        200: """
                        "ip",
                        "branches": [{
                            "id", "address", "organization",
                            "google_map_url", "yandex_map_url", "twogis_map_url", "vlru_url", "vlru_org_id",
                            "google_review_count", "google_review_avg", "google_parse_date",
                            "yandex_review_count", "yandex_review_avg", "yandex_parse_date",
                            "twogis_review_count", "twogis_review_avg", "twogis_parse_date",
                            "vlru_review_count", "vlru_review_avg", "vlru_parse_date"
                        }],
                        "provider_reviews_count": [{"provider", "review_count"}],
                        "reviews": [
                            {"id", "author", "avatar", "video", "photos", "published_date",
                             "rating", "content", "provider", "branch", "review_url"}
                        ]
                                """,
        400: "Некорректные данные",
    },
)
@api_view(["GET"])
def get_reviews_by_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")

    objects_with_ip = BranchIPMapping.objects.filter(ip_address=ip)
    branches = []
    for mapping in objects_with_ip:
        branches.append(mapping.branch)

    service_result = get_reviews_response_for_branches(branches=branches, query_params=request.query_params)
    reviews_data = ReviewSerializer(service_result["reviews"], many=True).data

    branch_serializer = BranchSerializer(branches, many=True)

    data = {
        "ip": ip,
        "branches": branch_serializer.data,
        "provider_reviews_count": service_result["provider_reviews_count"],
        "reviews": reviews_data,
    }

    return Response(data)


@swagger_auto_schema(
    method="GET",
    manual_parameters=[],
    responses={
        200: """
                        "ip",
                        "playlists": [{"id", "title", "count", "url", "parse_date", "provider"}],
                        "provider_videos_count": [{"playlist__provider", "review_count"}],
                        "videos": [
                            {"id", "url", "title", "author", "date", "preview", "duration", "playlist"}
                        ]
                                """,
        400: "Некорректные данные",
    },
)
@api_view(["GET"])
def get_videos_by_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")

    objects_with_ip = PlaylistIPMapping.objects.filter(ip_address=ip)
    playlists = []
    for mapping in objects_with_ip:
        playlists.append(mapping.playlist)

    videos_data = []

    videos = Video.objects.filter(playlist__in=playlists)
    videos_serializer = VideoSerializer(videos, many=True)
    videos_data = videos_serializer.data

    playlist_serializer = PlaylistSerializer(playlists, many=True)

    data = {
        "ip": ip,
        "playlists": playlist_serializer.data,
        "provider_videos_count": Video.objects.filter(playlist__in=playlists)
        .values("playlist__provider")
        .annotate(review_count=Count("id")),
        "videos": videos_data,
    }

    return Response(data)


def parse_filter_string(filter_str):
    """
    Парсит строку фильтра в Q-объекты для Django ORM.
    Поддерживает:
    - равенство: field=value → Q(field=value)
    - не равно: field!=value → ~Q(field=value)
    - другие операторы: field__operator=value → Q(field__operator=value)
    - отрицание операторов: !field__operator=value → ~Q(field__operator=value)
    """
    conditions = Q()

    if not filter_str:
        return conditions

    for part in filter_str.split("&"):
        if not part:
            continue

        if "!=" in part:
            key, value = part.split("!=", 1)
            q_object = ~Q(**{key: value})
        elif "=" in part:
            key, value = part.split("=", 1)
            negate = False

            if key.startswith("!"):
                negate = True
                key = key[1:]

            if key.endswith("__in"):
                value_list = [v.strip() for v in value.split(",") if v.strip()]
                q_object = Q(**{key: value_list})

            elif key.endswith("__isnull"):
                q_object = Q(**{key: value.lower() == "true"})
            else:
                q_object = Q(**{key: value})
            if negate:
                q_object = ~q_object
        else:
            continue

        conditions &= q_object

    return conditions


from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def webhook(request):
    from loguru import logger

    logger.info(f"webhook received: body={request.body.decode('utf-8')}")
    return HttpResponse(status=200)
