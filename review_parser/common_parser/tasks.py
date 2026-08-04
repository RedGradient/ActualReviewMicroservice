from time import perf_counter

from celery import chord, shared_task
from loguru import logger

from common_parser.models import Branch, BranchPlatform, Organization
from common_parser.parsers.registry import get_review_parser
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


@shared_task(name="parse_single_provider")
def parse_single_provider(provider: str, organization_id: int, branch_id: int):
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
        logger.error(f"Branch {branch} has no {provider} provider")
        return {provider: {"error": "branch_platform_not_found", "provider": provider}}

    if not branch_platform.url:
        logger.error(f"Branch platform for provider {provider} has no url")
        return {provider: {"error": "branch_platform_has_no_url", "provider": provider}}

    try:
        parser = get_review_parser(provider)
    except KeyError:
        logger.error("Unknown provider: {}", provider)
        return {provider: {"error": "unknown_provider", "provider": provider}}

    try:
        parser_result = parser.run(
            url=branch_platform.url, org_name=organization.name or "", inn=organization.inn, address=branch.address
        )

        return {provider: {"parsed": parser_result.parsed, "created": parser_result.created}}
    except Exception:
        logger.exception(
            "Failed to parse {} for branch_id={}",
            parser.provider,
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
