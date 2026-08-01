from time import perf_counter

from celery import shared_task
from django.shortcuts import get_object_or_404
from loguru import logger

from common_parser.models import Branch, BranchPlatform, Organization, Playlist
from common_parser.parsers.registry import get_review_parser
from common_parser.parsers.yandex.parser import create_yandex_reviews
from common_parser.tools.parse import parse_all_providers


@shared_task(name="common_parser.tasks.weekly_parsing")
def weekly_parsing():
    t0 = perf_counter()
    branches = Branch.objects.all()

    dict_results = {}
    for branch in branches:
        dict_results[f"{branch.id}"] = parse_all_providers(branch)

    logger.info(
        f"weekly_parsing finished: branches={len(dict_results)} duration_ms={int((perf_counter() - t0) * 1000)}"
    )
    return dict_results


@shared_task(name="parse_all_providers_async_on_create")
def parse_all_providers_async_on_create(branch_org_id, branch_address):
    t0 = perf_counter()
    try:
        branch = Branch.objects.get(organization_id=branch_org_id, address=branch_address)
        result = parse_all_providers(branch)
        logger.info(
            "parse_all_providers_async_on_create finished: branch_id={} duration_ms={}",
            branch.id,
            int((perf_counter() - t0) * 1000),
        )
        return result
    except Branch.DoesNotExist:
        logger.error(f"Branch not found (org_id={branch_org_id}, address={branch_address})")
    except Exception as e:
        logger.exception(f"Error in parse_all_providers_async_on_create: {e}")


@shared_task(name="parse_all_providers_async")
def parse_all_providers_async(branch_id):
    t0 = perf_counter()
    branch = get_object_or_404(Branch, id=branch_id)
    results = parse_all_providers(branch)
    logger.info(
        f"parse_all_providers_async finished: branch_id={branch_id} duration_ms={int((perf_counter() - t0) * 1000)}"
    )
    return {"branch_id": branch_id, "results": results}


@shared_task(name="parse_yandex_async")
def parse_yandex_async(branch_platform_id):
    t0 = perf_counter()
    branch_platform = get_object_or_404(BranchPlatform, id=branch_platform_id)
    results = create_yandex_reviews(
        url=branch_platform.url,
        inn=branch_platform.branch.organization.inn,
        address=branch_platform.branch.address,
    )
    logger.info(
        f"parse_yandex_async finished: branch_platform_id={branch_platform_id} "
        f"duration_ms={int((perf_counter() - t0) * 1000)}"
    )
    return {"branch_platform_id": branch_platform_id, "results": results}


@shared_task(name="parse_providers_async")
def parse_providers_async(providers: list[str], organization_id: int, branch_id: int):
    try:
        organization = Organization.objects.get(pk=organization_id)
        branch = Branch.objects.get(pk=branch_id, organization=organization)
    except Organization.DoesNotExist:
        logger.error("Organization not found: id={}", organization_id)
        return {"error": "organization_not_found", "organization_id": organization_id}
    except Branch.DoesNotExist:
        logger.error("Branch not found: id={}", branch_id)
        return {"error": "branch_not_found", "branch_id": branch_id}

    result = {}
    for provider in providers:
        try:
            branch_platform = BranchPlatform.objects.get(branch_id=branch_id, provider=provider)
        except BranchPlatform.DoesNotExist:
            logger.error(f"Branch {branch} has no {provider} provider")
            result[provider] = {"error": "branch_platform_not_found", "provider": provider}
            continue

        if not branch_platform.url:
            logger.error(f"Branch platform for provider {provider} has no url")
            result[provider] = {"error": "branch_platform_has_no_url", "provider": provider}
            continue

        try:
            parser = get_review_parser(provider)
        except KeyError:
            logger.error("Unknown provider: {}", provider)
            result[provider] = {"error": "unknown_provider", "provider": provider}
            continue

        try:
            parser_result = parser.run(
                url=branch_platform.url, org_name=organization.name or "", inn=organization.inn, address=branch.address
            )

            result[provider] = {
                "parsed": parser_result.parsed,
                "created": parser_result.created,
            }
        except Exception:
            logger.exception(
                "Failed to parse {} for branch_id={}",
                parser.provider,
                branch.pk,
            )
            result[provider] = {"error": "unknown_error"}

    return result


@shared_task(name="parse_vlru_async")
def parse_vlru_async(branch_id):
    t0 = perf_counter()
    branch = get_object_or_404(Branch, id=branch_id)
    parser = get_review_parser("vlru")
    results = parser.run(
        url=branch.vlru_url,
        inn=branch.organization.inn,
        address=branch.address,
    )
    logger.info(f"parse_vlru_async finished: branch_id={branch_id} duration_ms={int((perf_counter() - t0) * 1000)}")
    return {"branch_id": branch_id, "results": results}


@shared_task(name="parse_2gis_async")
def parse_2gis_async(branch_id):
    t0 = perf_counter()
    branch = get_object_or_404(Branch, id=branch_id)
    parser = get_review_parser("2gis")
    results = parser.run(
        url=branch.twogis_map_url,
        inn=branch.organization.inn,
        address=branch.address,
    )
    logger.info(f"parse_2gis_async finished: branch_id={branch_id} duration_ms={int((perf_counter() - t0) * 1000)}")
    return {"branch_id": branch_id, "results": results}


@shared_task(name="parse_youtube_videos_async")
def parse_youtube_videos_async(playlist_id):
    from common_parser.tools.parse_videos import parse_youtube_videos

    t0 = perf_counter()
    playlist = get_object_or_404(Playlist, id=playlist_id)
    results = parse_youtube_videos(playlist.url)
    logger.info(
        "parse_youtube_videos_async finished: playlist_id={} duration_ms={}",
        playlist_id,
        int((perf_counter() - t0) * 1000),
    )
    return {"playlist_id": playlist_id, "results": results}


@shared_task(name="parse_vk_videos_async")
def parse_vk_videos_async(playlist_id):
    from common_parser.tools.parse_videos import parse_vk_videos

    t0 = perf_counter()
    playlist = get_object_or_404(Playlist, id=playlist_id)
    results = parse_vk_videos(playlist.url)
    logger.info(
        f"parse_vk_videos_async finished: playlist_id={playlist_id} duration_ms={int((perf_counter() - t0) * 1000)}"
    )
    return {"playlist_id": playlist_id, "results": results}
