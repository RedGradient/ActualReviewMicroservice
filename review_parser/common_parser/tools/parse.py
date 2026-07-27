from __future__ import annotations

from typing import Any

from loguru import logger

from common_parser.models import Branch
from common_parser.parsers import REVIEW_PARSERS


def parse_all_providers(branch: Branch) -> dict[str, Any]:
    success_count = 0
    try_count = 0
    results: dict[str, Any] = {}

    platforms_by_provider = {
        platform.provider: platform
        for platform in branch.source.all()
    }

    for parser in REVIEW_PARSERS:
        platform = platforms_by_provider.get(parser.provider)
        if not platform or not platform.url:
            continue

        try_count += 1
        try:
            result = parser.run(
                url=platform.url,
                inn=branch.organization.inn,
                org_name=branch.organization.name or "",
                address=branch.address,
            )
            results[parser.provider] = result
            if result:
                success_count += 1
        except Exception:
            logger.exception(
                "Failed to parse {} for branch_id={}",
                parser.provider,
                branch.id,
            )

    results["tryes"] = try_count
    results["success"] = success_count
    return results
