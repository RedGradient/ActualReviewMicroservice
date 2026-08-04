import hashlib

from common_parser.tools.normalize_content import normalize_content


def normalize_and_hash(content: str) -> str:
    normalized = normalize_content(content)
    return get_content_hash(normalized)


def get_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
