import os
import sys

from loguru import logger

_CONFIGURED = False

# Console: no timestamp — Docker/Celery already prefix the line.
# File: full timestamp for post-mortem grep.
_CONSOLE_FORMAT = "{level:<7} [{extra[provider]}] {message}"
_FILE_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} {level:<7} [{extra[provider]}] {message}"


def configure_logging() -> None:
    """
    Configure loguru once for the whole Django/Celery process.

    - stderr: INFO (human readable, short format)
    - debug.log: DEBUG (persistent, full format)

    Uses sys.__stderr__ so Celery's stdout/stderr proxy does not wrap
    each line as ``[timestamp: WARNING/MainProcess]``.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    file_level = os.getenv("LOG_FILE_LEVEL", "DEBUG").upper()

    logger.remove()
    logger.configure(extra={"provider": "-"})

    logger.add(
        sys.__stderr__,
        level=log_level,
        format=_CONSOLE_FORMAT,
        enqueue=True,
        colorize=False,
    )

    logger.add(
        "debug.log",
        level=file_level,
        format=_FILE_FORMAT,
        enqueue=True,
        rotation="10 MB",
        retention="10 days",
    )

    _CONFIGURED = True
