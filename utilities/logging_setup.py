"""Application file logging with size-capped rotation.

Writes DEBUG app logs to ``aio_monitor.log`` inside the AIO data folder so
logs can be checked cold (after the app exited). Rotation keeps 3 files
total (live log + 2 backups) at 5 MB each.

Resilience properties:
- Idempotent: safe to call multiple times, attaches at most one handler
  per log file path.
- Never raises: any failure (missing dir, read-only FS, mocked paths in
  tests) is reported on the console logger and returns None.
- No GUI imports: safe to use from the entry point before Tk loads.
"""

import contextlib
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_FILENAME = "aio_monitor.log"
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 2  # live log + 2 backups = 3 files total
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Opt-out (tests, debugging): when set, file logging is disabled entirely.
# tests/conftest.py sets this so importing the entry point never attaches a
# real RotatingFileHandler to the root logger during the test session (its
# per-record os.path.exists checks would otherwise consume globally-patched
# os.path.exists side_effects in unrelated tests).
NO_FILE_LOG_ENV_VAR = "AIO_NO_FILE_LOG"


def _is_mocked_path(path: object) -> bool:
    """True for missing/blank/MagicMock-derived paths (never log there)."""
    if path is None:
        return True
    try:
        text = str(path)
        return not text.strip() or "MagicMock" in text
    except Exception:
        return True


def _handler_for_path(root_logger: logging.Logger, log_path: str) -> bool:
    """Return True if root_logger already rotates to log_path (idempotency)."""
    try:
        wanted = os.path.abspath(log_path)
    except Exception:
        return False
    for handler in root_logger.handlers:
        try:
            if isinstance(handler, RotatingFileHandler) and os.path.abspath(handler.baseFilename) == wanted:
                return True
        except Exception:  # debug logged
            logger.debug("Suppressed Exception while inspecting handler", exc_info=True)
    return False


def setup_file_logging(
    aio_folder: str | Path | None,
    root_logger: logging.Logger | None = None,
    max_bytes: int = LOG_MAX_BYTES,
    backup_count: int = LOG_BACKUP_COUNT,
) -> str | None:
    """Attach a rotating file handler to the root logger.

    Args:
        aio_folder: AIO data folder holding the log file.
        root_logger: Logger to attach to (defaults to the root logger).
        max_bytes: Rotation threshold per file.
        backup_count: Number of backups (live + backups = total files).

    Returns:
        Absolute log file path on success, None when file logging is
        unavailable. Never raises.
    """
    log = root_logger if root_logger is not None else logging.getLogger()
    try:
        if os.environ.get(NO_FILE_LOG_ENV_VAR):
            logger.debug("File logging disabled via %s", NO_FILE_LOG_ENV_VAR)
            return None
        if _is_mocked_path(aio_folder):
            logger.debug("Skipping file logging for mocked path %s", aio_folder)
            return None
        folder = os.path.abspath(os.path.expandvars(os.path.expanduser(str(aio_folder))))
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            logger.warning(f"Cannot create log folder {folder}: {e}. Continuing without file logging.")
            return None
        log_path = os.path.join(folder, LOG_FILENAME)
        if _handler_for_path(log, log_path):
            return log_path
        try:
            handler = RotatingFileHandler(
                log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8", delay=True
            )
        except Exception as e:
            logger.warning(f"Cannot open log file {log_path}: {e}. Continuing without file logging.")
            return None
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        log.addHandler(handler)
        with contextlib.suppress(Exception):
            if os.path.exists(log_path):
                os.chmod(log_path, 0o600)
        log.debug(f"File logging enabled: {log_path} (max {max_bytes}B x {backup_count + 1} files)")
        return log_path
    except Exception as e:
        logger.warning(f"File logging setup failed: {e}. Continuing without file logging.")
        return None
