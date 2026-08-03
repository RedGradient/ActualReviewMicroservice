import re


def normalize_content(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u00a0", " ")  # неразрывный пробел
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)  # все пробелы → один
    text = re.sub(r"[^\w\s]+", "", text, flags=re.UNICODE)  # убрать пунктуацию
    return text
