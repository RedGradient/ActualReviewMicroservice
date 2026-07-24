from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from django.db.models import Count, Case, When, Q, Value, IntegerField

from common_parser.models import Branch, BranchIPMapping, Review
from common_parser.serializers import BranchSerializer, ReviewSerializer
from common_parser.services.reviews_query import _parse_int, _parse_bool


@api_view(["GET"])
def reviews_v2(request):
    branch_id = request.query_params.get("branch_id")
    if not branch_id:
        return Response(
            {"detail": "branch_id is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        branch = Branch.objects.get(id=branch_id)
    except Branch.DoesNotExist:
        return Response({"detail": "Branch not found"}, status=status.HTTP_404_NOT_FOUND)

    offset = _parse_int(request.query_params.get("offset")) or 0
    limit = _parse_int(request.query_params.get("limit"))
    min_rating = _parse_int(request.query_params.get("min_rating")) or 4
    providers_param = request.query_params.get("providers", "")
    sort_photos = _parse_bool(request.query_params.get("sort_photos"), default=False)

    provider_reviews_count = (
        Review.objects.filter(branch=branch)
        .values("provider")
        .annotate(review_count=Count("id"))
    )

    reviews_by_provider = {}

    if providers_param:
        providers_list = [p.strip() for p in providers_param.split(",") if p.strip()]
    else:
        providers_list = [item["provider"] for item in provider_reviews_count]

    for provider in providers_list:
        provider_reviews = Review.objects.filter(
            branch=branch,
            provider=provider,
            rating__gte=min_rating
        )

        if sort_photos:
            provider_reviews = provider_reviews.order_by(
                Case(
                    When(
                        ~Q(photos__isnull=True) & ~Q(photos=""),
                        then=Value(1)
                    ),
                    default=Value(0),
                    output_field=IntegerField(),
                ).desc(),
                "-published_date"
            )
        else:
            provider_reviews = provider_reviews.order_by(
                "-published_date"
            )

        if limit is not None:
            paginated = provider_reviews[offset:offset + limit]
        elif offset:
            paginated = provider_reviews[offset:]
        else:
            paginated = provider_reviews

        reviews_by_provider[provider] = ReviewSerializer(paginated, many=True).data

    return Response({
        "branch": BranchSerializer(branch).data,
        "provider_reviews_count": provider_reviews_count,
        "reviews": reviews_by_provider,
    })


@api_view(["GET"])
def reviews_by_ip_v2(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")

    branches = [m.branch for m in BranchIPMapping.objects.filter(ip_address=ip)]

    if not branches:
        return Response({
            "ip": ip,
            "branches": [],
            "provider_reviews_count": [],
            "reviews": {}
        })

    offset = _parse_int(request.query_params.get("offset")) or 0
    limit = _parse_int(request.query_params.get("limit"))
    min_rating = _parse_int(request.query_params.get("min_rating")) or 4
    providers_param = request.query_params.get("providers", "")
    sort_photos = _parse_bool(request.query_params.get("sort_photos"), default=False)

    provider_reviews_count = (
        Review.objects.filter(branch__in=branches)
        .values("provider")
        .annotate(review_count=Count("id"))
    )

    reviews_by_provider = {}

    if providers_param:
        providers_list = [p.strip() for p in providers_param.split(",") if p.strip()]
    else:
        providers_list = [item["provider"] for item in provider_reviews_count]

    for provider in providers_list:
        provider_reviews = Review.objects.filter(
            branch__in=branches,
            provider=provider,
            rating__gte=min_rating
        )

        if sort_photos:
            provider_reviews = provider_reviews.order_by(
                Case(
                    When(
                        ~Q(photos__isnull=True) & ~Q(photos=""),
                        then=Value(1)
                    ),
                    default=Value(0),
                    output_field=IntegerField(),
                ).desc(),
                "-published_date"
            )
        else:
            provider_reviews = provider_reviews.order_by(
                "-published_date"
            )

        if limit is not None:
            paginated = provider_reviews[offset:offset + limit]
        elif offset:
            paginated = provider_reviews[offset:]
        else:
            paginated = provider_reviews

        reviews_by_provider[provider] = ReviewSerializer(paginated, many=True).data

    return Response({
        "ip": ip,
        "branches": BranchSerializer(branches, many=True).data,
        "provider_reviews_count": provider_reviews_count,
        "reviews": reviews_by_provider,
    })
