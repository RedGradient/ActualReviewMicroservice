import json
from pathlib import Path

_FIXTURES_DIR = Path(__file__).resolve().parent


def _load_json(name: str) -> dict:
    return json.loads((_FIXTURES_DIR / name).read_text(encoding="utf-8"))


def vlru_thread_first_page() -> dict:
    """Первый ответ thread API (company=trinity)."""
    return _load_json("vlru_thread_first_page.json")


def vlru_comments_second_page() -> dict:
    """Вторая страница comments API для thread trinity."""
    return _load_json("vlru_comments_second_page.json")


def vlru_thread_last_page() -> dict:
    """Пустая страница — конец пагинации."""
    return _load_json("vlru_thread_last_page.json")


def vlru_avg_history() -> dict:
    """История средней оценки компании trinity (companyId=27297)."""
    return _load_json("vlru_avg_history.json")


def vlru_avg_history_low() -> dict:
    """История с низкой оценкой (< 4) для проверки clamp."""
    return _load_json("vlru_avg_history_low.json")


def vlru_comments_single_html() -> str:
    """Фрагмент HTML с одним отзывом из trinity."""
    return (_FIXTURES_DIR / "vlru_comments_single.html").read_text(encoding="utf-8")
