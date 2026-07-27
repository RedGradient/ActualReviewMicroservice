from pathlib import Path

_FIXTURES_DIR = Path(__file__).resolve().parent


def twogis_api_response() -> str:
    """Текст JSON-ответа 2GIS Reviews API (одна страница, один отзыв)."""
    return (_FIXTURES_DIR / "twogis_api_response.json").read_text(encoding="utf-8")
