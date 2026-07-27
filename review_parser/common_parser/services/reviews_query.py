import json
from typing import Any, Iterable

from django.db.models import Count, Q, QuerySet, Case, When, Value, IntegerField, F

from common_parser.models import Branch, Review


PROVIDER_CHOICES = ["yandex", "2gis", "vlru", "google"]


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() == "true"


def _parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def parse_filter_string(filter_str: str) -> Q:
    """
    Parse filter string to Django Q.

    Supported:
    - field=value
    - field!=value
    - field__op=value (e.g. rating__gt=4)
    - !field__op=value (negation)
    - field__in=1,2,3 (and negation)
    - field__isnull=true/false
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


def parse_providers_param(query_params) -> list[dict[str, Any]]:
    providers_raw = query_params.get("providers")
    provider_single = query_params.get("provider")

    if not providers_raw and not provider_single:
        return []

    if provider_single and not providers_raw:
        providers_raw = provider_single

    raw = (providers_raw or "").strip()
    if not raw:
        return []

    # JSON (legacy object concat, object, or array)
    if raw.startswith("{") or raw.startswith("["):
        try:
            raw_json = "[" + raw + "]" if raw.startswith("{") else raw
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                parsed = [parsed]
            if not isinstance(parsed, list):
                return []
            result: list[dict[str, Any]] = []
            for item in parsed:
                if not isinstance(item, dict) or "provider" not in item:
                    continue
                result.append(
                    {
                        "provider": item.get("provider"),
                        "count": item.get("count"),
                        "filters": item.get("filters", ""),
                    }
                )
            return result
        except Exception:
            return []

    # CSV
    providers_list = [p.strip() for p in raw.split(",") if p.strip()]
    global_count = _parse_int(query_params.get("count"))
    global_filters = query_params.get("filters") or ""
    result: list[dict[str, Any]] = []
    for prov in providers_list:
        prov_count = _parse_int(query_params.get(f"count_{prov}"))
        prov_filters = query_params.get(f"filters_{prov}") or ""
        result.append(
            {
                "provider": prov,
                "count": prov_count if prov_count is not None else global_count,
                "filters": prov_filters if prov_filters else global_filters,
            }
        )
    return result


def get_reviews_response_for_branches(*, branches: Iterable[Branch], query_params) -> dict[str, Any]:
    branches_list = list(branches)
    only_providers = _parse_bool(query_params.get("only_providers"), default=False)
    providers = parse_providers_param(query_params)
    sort_photos = _parse_bool(query_params.get("sort_photos"), default=False)

    reviews_data: list[Review] | QuerySet[Review]

    if providers:
        reviews_list: list[Review] = []
        for prov in providers:
            provider_name = prov.get("provider")
            predata = Review.objects.filter(
                branch_platform__branch__in=branches_list,
                branch_platform__provider=provider_name,
                rating__gte=4,
            )

            if sort_photos:
                predata = predata.order_by(
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
                predata = predata.order_by("-published_date")

            filters = (prov.get("filters") or "").strip()
            if filters:
                predata = predata.filter(parse_filter_string(filters))

            count = prov.get("count")
            if count:
                reviews_list += list(predata[:count])
            else:
                reviews_list += list(predata)

        if not only_providers:
            provider_to_exclude = [item["provider"] for item in providers if item.get("provider")]
            # preserve legacy behavior (no explicit ordering here)
            reviews_list += list(
                Review.objects.filter(branch_platform__branch__in=branches_list).exclude(
                    branch_platform__provider__in=provider_to_exclude
                )
            )

        reviews_data = reviews_list
    else:
        offset = _parse_int(query_params.get("offset")) or 0
        limit = _parse_int(query_params.get("limit"))
        filters = query_params.get("filters") or ""

        reviews = Review.objects.filter(branch_platform__branch__in=branches_list, rating__gte=4)

        if sort_photos:
            reviews = reviews.order_by(
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
            reviews = reviews.order_by("-published_date")

        if filters:
            reviews = reviews.filter(parse_filter_string(filters))

        if limit is not None:
            reviews = reviews[offset : offset + limit]
        elif offset:
            reviews = reviews[offset:]
        reviews_data = reviews

    provider_reviews_count = (
        Review.objects.filter(branch_platform__branch__in=branches_list)
        .values("branch_platform__provider")
        .annotate(review_count=Count("id"))
        .annotate(provider=F("branch_platform__provider"))
        .values("provider", "review_count")
    )

    return {
        "providers_requested": providers,
        "reviews": reviews_data,
        "provider_reviews_count": provider_reviews_count,
    }

