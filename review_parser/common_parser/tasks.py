from time import perf_counter

from celery import chord, shared_task
from loguru import logger

from common_parser.models import Branch, BranchPlatform, Organization
from common_parser.parsers import REVIEW_PARSERS
from common_parser.parsers.registry import get_review_parser


@shared_task(name="common_parser.tasks.weekly_parsing")
def weekly_parsing():
    t0 = perf_counter()
    branches = list(Branch.objects.all())
    providers = [parser.provider for parser in REVIEW_PARSERS]

    if not providers:
        duration_ms = int((perf_counter() - t0) * 1000)
        logger.info("weekly_parsing finished: no parsers configured duration_ms={}", duration_ms)
        return {"branches": {}, "branch_count": 0, "duration_ms": duration_ms}

    if not branches:
        duration_ms = int((perf_counter() - t0) * 1000)
        logger.info("weekly_parsing finished: no branches duration_ms={}", duration_ms)
        return {"branches": {}, "branch_count": 0, "duration_ms": duration_ms}

    header = [parse_branch_providers.s(branch.organization_id, branch.id) for branch in branches]
    merge_result = chord(header)(merge_weekly_results.s(started_at=t0))
    logger.info(
        "weekly_parsing dispatched: branch_count={} merge_task_id={}",
        len(branches),
        merge_result.id,
    )
    return {"merge_task_id": merge_result.id, "branch_count": len(branches)}


@shared_task(name="parse_branch_providers")
def parse_branch_providers(organization_id: int, branch_id: int) -> dict:
    t0 = perf_counter()

    providers = [platform.provider for platform in BranchPlatform.objects.filter(branch_id=branch_id)]
    if not providers:
        logger.info("parse_branch_providers skipped: branch_id={} has no platforms", branch_id)

    provider_results = [parse_single_provider(provider, organization_id, branch_id) for provider in providers]
    duration_ms = int((perf_counter() - t0) * 1000)
    return {"branch_id": branch_id, "results": merge_provider_results(provider_results), "duration_ms": duration_ms}


@shared_task(name="merge_weekly_results")
def merge_weekly_results(branch_payloads: list[dict], started_at: float) -> dict:
    branches = []
    for item in branch_payloads:
        branches.append(
            {"branch_id": item["branch_id"], "results": item["results"], "duration_ms": item["duration_ms"]}
        )

    duration_ms = int((perf_counter() - started_at) * 1000)
    report = {
        "branches": branches,
        "branch_count": len(branches),
        "duration_ms": duration_ms,
    }
    logger.info(
        "weekly_parsing finished: branches={} duration_ms={}",
        len(branches),
        duration_ms,
    )
    return report


@shared_task(name="parse_single_provider")
def parse_single_provider(provider: str, organization_id: int, branch_id: int):
    with logger.contextualize(provider=provider):
        try:
            organization = Organization.objects.get(pk=organization_id)
            branch = Branch.objects.get(pk=branch_id, organization=organization)
        except Organization.DoesNotExist:
            logger.error("Organization not found: id={}", organization_id)
            return {provider: {"error": "organization_not_found", "organization_id": organization_id}}
        except Branch.DoesNotExist:
            logger.error("Branch not found: id={}", branch_id)
            return {provider: {"error": "branch_not_found", "branch_id": branch_id}}

        try:
            branch_platform = BranchPlatform.objects.get(branch=branch, provider=provider)
        except BranchPlatform.DoesNotExist:
            logger.error("Branch {} has no {} provider", branch.id, provider)
            return {provider: {"error": "branch_platform_not_found", "provider": provider}}

        if not branch_platform.url:
            logger.error("Branch platform for provider {} has no url", provider)
            return {provider: {"error": "branch_platform_has_no_url", "provider": provider}}

        try:
            parser = get_review_parser(provider)
        except KeyError:
            logger.error("Unknown provider: {}", provider)
            return {provider: {"error": "unknown_provider", "provider": provider}}

        try:
            parser_result = parser.run(
                url=branch_platform.url,
                org_name=organization.name or "",
                inn=organization.inn,
                address=branch.address,
            )
            return {provider: {"parsed": parser_result.parsed, "created": parser_result.created}}
        except Exception:
            logger.exception(
                "Failed to parse {} for branch_id={}",
                provider,
                branch.pk,
            )
            return {provider: {"error": "unknown_error"}}


@shared_task(name="merge_provider_results")
def merge_provider_results(provider_results: list[dict]) -> dict:
    merged = {}
    for item in provider_results:
        merged.update(item)
    return merged


def parse_providers_async(providers: list[str], organization_id: int, branch_id: int):
    header = [parse_single_provider.s(provider, organization_id, branch_id) for provider in providers]
    return chord(header)(merge_provider_results.s())
