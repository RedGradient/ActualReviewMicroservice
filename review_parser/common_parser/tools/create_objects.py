from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from common_parser.models import Branch, BranchPlatform, Organization, Playlist, Review, Video
from common_parser.serializers import (
    BranchPlatformSerializer,
    OrganizationSerializer,
    ReviewSerializer,
    VideoSerializer,
)
from common_parser.tools.hash import get_content_hash
from common_parser.tools.normalize_content import normalize_content


def create_review(data: dict) -> bool:
    """Создает отзыв, если уже есть такой отзыв возвращает False"""
    branch_platform = data["branch_platform"]
    existing_review = Review.objects.filter(
        branch_platform=branch_platform, author=data["author"], content=data["content"]
    ).exists()

    if existing_review:
        return False

    normalized_content = normalize_content(data["content"])
    data_rewiew = {
        "branch_platform": branch_platform.id,
        "author": data["author"],
        "avatar": data["avatar"],
        "rating": data["rating"],
        "content": data["content"],
        "content_hash": get_content_hash(normalized_content),
        "published_date": data["published_date"],
    }

    if "photos" in data:
        data_rewiew["photos"] = data["photos"]

    if "video" in data:
        data_rewiew["video"] = data["video"]

    if "review_url" in data:
        data_rewiew["review_url"] = data["review_url"]

    serializer_review = ReviewSerializer(data=data_rewiew)

    if serializer_review.is_valid():
        serializer_review.save()
        return True
    else:
        print("Ошибки сериализатора:", serializer_review.errors)
        return False


def get_or_create_Organization(inn: str, name: str) -> Organization:
    try:
        organization = Organization.objects.get(inn=inn)
        if name and organization.name != name:
            organization.name = name
            organization.save()
    except Organization.DoesNotExist:
        serializer_org = OrganizationSerializer(data={"inn": inn, "name": name or ""})
        if serializer_org.is_valid():
            organization = serializer_org.save()
        else:
            return None

    return organization


def get_or_create_Branch(
    organization: str,
    address: str,
    url_name: str,
    url: str,
    review_count_name: str,
    review_count: str,
    review_avg_name: str,
    review_avg: str,
) -> Branch:
    try:
        branch = Branch.objects.get(address=address, organization=organization)
        if url and getattr(branch, url_name) != url:
            setattr(branch, url_name, url)
        if review_count and getattr(branch, review_count_name) != review_count:
            setattr(branch, review_count_name, review_count)
        if review_avg and getattr(branch, review_avg_name) != review_avg:
            setattr(branch, review_avg_name, review_avg)
        branch.save()
    except Branch.DoesNotExist:
        serializer_branch = BranchPlatformSerializer(
            data={"organization": organization.id, "address": address or "", url_name: url}
        )
        if serializer_branch.is_valid():
            branch = serializer_branch.save()
        else:
            return None

    return branch


def get_or_create_playlist(data: dict) -> Playlist:
    playlist_url = data.get("url")

    try:
        playlist = Playlist.objects.get(url=playlist_url)

        for key, value in data.items():
            setattr(playlist, key, value)

        playlist.save()
        return playlist

    except Playlist.DoesNotExist:
        new_playlist = Playlist(**data)
        new_playlist.save()

        return new_playlist


def create_video(data: dict) -> bool:
    """Создает видео, если уже есть такое возвращает False"""
    existing_review = Video.objects.filter(url=data["url"]).exists()

    if existing_review:
        return False

    serializer_video = VideoSerializer(data=data)

    if serializer_video.is_valid():
        serializer_video.save()
        return True
    else:
        print("Ошибки сериализатора:", serializer_video.errors)
        return False


def get_or_create_branch(organization: Organization, address: str | None) -> Branch:
    branch, _ = Branch.objects.get_or_create(
        organization=organization,
        address=address or "",
    )
    return branch


def get_or_create_branch_platform(
    organization: Organization,
    address: str,
    provider: str,
    url: str | None = None,
    org_id: str | None = None,
    review_count: int | None = None,
    review_avg: float | int | str | None = None,
    parsed_at: datetime | None = None,
) -> BranchPlatform:
    branch = get_or_create_branch(organization, address)
    platform, created = BranchPlatform.objects.get_or_create(
        branch=branch,
        provider=provider,
        defaults=_platform_defaults(
            url=url,
            org_id=org_id,
            review_count=review_count,
            review_avg=review_avg,
            parsed_at=parsed_at,
        ),
    )
    if not created:
        _update_platform_fields(
            platform,
            url=url,
            org_id=org_id,
            review_count=review_count,
            review_avg=review_avg,
            parsed_at=parsed_at,
        )
    return platform


def _platform_defaults(**kwargs: Any) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if value is not None}


def _update_platform_fields(platform: BranchPlatform, **kwargs: Any) -> None:
    updated: list[str] = []
    for field, value in kwargs.items():
        if value is None:
            continue
        if field == "review_avg":
            value = _coerce_review_avg(value)
        if getattr(platform, field) != value:
            setattr(platform, field, value)
            updated.append(field)
    if updated:
        platform.save(update_fields=updated)


def _coerce_review_avg(value: float | int | str) -> Decimal | None:
    try:
        avg = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if avg < 0:
        return None
    return avg
