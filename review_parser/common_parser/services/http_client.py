from __future__ import annotations

import os
from functools import lru_cache

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_TIMEOUT_S = float(os.getenv("HTTP_TIMEOUT_S", "15"))


@lru_cache(maxsize=1)
def get_session() -> requests.Session:
    """
    Shared requests Session with sane retries.

    Retries help with transient 429/5xx from providers.
    """
    retries = Retry(
        total=int(os.getenv("HTTP_RETRY_TOTAL", "3")),
        connect=int(os.getenv("HTTP_RETRY_CONNECT", "3")),
        read=int(os.getenv("HTTP_RETRY_READ", "3")),
        status=int(os.getenv("HTTP_RETRY_STATUS", "3")),
        backoff_factor=float(os.getenv("HTTP_RETRY_BACKOFF", "0.5")),
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
        raise_on_status=False,
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=50)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def get(url: str, *, timeout: float | None = None, **kwargs) -> requests.Response:
    if timeout is None:
        timeout = DEFAULT_TIMEOUT_S
    return get_session().get(url, timeout=timeout, **kwargs)

