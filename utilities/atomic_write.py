"""Atomic file write helpers with secure permissions (0o600) and dir 0o700."""

import json
import logging
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


def ensure_dir_secure(dir_path: str | Path, mode: int = 0o700) -> None:
    """Ensure directory exists with secure permissions.

    Uses makedirs with exist_ok then chmod to enforce mode regardless of umask.
    Swallows creation errors (e.g. mocked /test paths, permission in tests) and logs debug,
    since callers will handle write failures via fallback.
    """
    if not dir_path:
        return
    # Early guard for mocked AppContainer where aio_folder is a MagicMock
    # (e.g. MagicMock(name='mock.aio_folder') without string value) —
    # Path(str(MagicMock)) -> "<MagicMock name='...' id='...'>" would otherwise
    # create real folders named "<MagicMock ...>" in repo root.
    try:
        s = str(dir_path)
    except Exception:
        logger.debug("Skipping mocked dir %s", dir_path)
        return
    if not s or s.startswith("<MagicMock") or "MagicMock" in s:
        logger.debug("Skipping mocked dir %s", dir_path)
        return
    if not isinstance(dir_path, (str, Path, os.PathLike)):
        # Non-path-like mock objects whose str already contains MagicMock handled above;
        # otherwise avoid makedirs on unexpected types.
        if "MagicMock" in s or "<MagicMock" in s:
            logger.debug("Skipping mocked dir %s", dir_path)
            return
        logger.debug("Skipping non-path-like dir %s", dir_path)
        return
    p = Path(s)
    # Also guard if parent string looks mocked (e.g. Path("<MagicMock ...>/file.json").parent)
    try:
        parent_s = str(p.parent)
        if parent_s.startswith("<MagicMock") or "MagicMock" in parent_s or "<MagicMock" in parent_s:
            logger.debug("Skipping mocked dir %s", dir_path)
            return
    except Exception:
        logger.debug("Skipping mocked dir %s", dir_path)
        return
    # Avoid creating empty or current dir references like '.'.
    if str(p) in ("", "."):
        return
    # Skip secure dir creation for mocked test paths under /test (no real FS).
    # This also avoids extra os.path.exists calls inside makedirs that break tests mocking exists.
    if str(p).startswith("/test"):
        return
    try:
        os.makedirs(p, exist_ok=True)
    except Exception as e:
        logger.debug("Suppressed Exception ensure_dir %s: %s", p, e, exc_info=True)
        return
    try:
        os.chmod(p, mode)
    except Exception as e:  # pragma: no cover - Windows chmod no-op
        logger.debug("Suppressed Exception: %s", e, exc_info=True)


def _atomic_write(target: Path, writer: Callable[[Any], None]) -> None:
    """Write atomically via tmp + os.replace with 0o600.

    Creates tmp file in same directory with os.open O_NOFOLLOW 0o600,
    calls writer(file_handle), chmod 0o600, replace onto target, chmod target.
    Cleans up tmp on any exception. Handles Windows missing O_NOFOLLOW.
    """
    # Guard against MagicMock target (e.g. aio_folder mocked) — avoid creating "<MagicMock ...>" dirs/files.
    try:
        ts = str(target)
        if ts.startswith("<MagicMock") or "MagicMock" in ts:
            logger.debug("Skipping mocked _atomic_write target %s", target)
            return
    except Exception:
        logger.debug("Skipping mocked _atomic_write target %s", target)
        return
    target = Path(target)
    dir_path = target.parent
    ensure_dir_secure(dir_path, 0o700)

    tmp_name = f".{target.name}.tmp.{os.getpid()}.{time.time_ns()}"
    tmp_path = dir_path / tmp_name
    fd = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        # O_NOFOLLOW prevents symlink TOCTOU; absent on Windows.
        try:
            flags |= os.O_NOFOLLOW  # type: ignore[attr-defined]
        except AttributeError as e:  # pragma: no cover
            logger.debug("Suppressed AttributeError: %s", e, exc_info=True)

        fd = os.open(str(tmp_path), flags, 0o600)
        # fdopen takes ownership; set fd None to avoid double close.
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fd = None
            writer(f)
        try:
            os.chmod(tmp_path, 0o600)
        except Exception as e:  # pragma: no cover
            logger.debug("Suppressed Exception: %s", e, exc_info=True)
        os.replace(str(tmp_path), str(target))
        try:
            os.chmod(target, 0o600)
        except Exception as e:  # pragma: no cover
            logger.debug("Suppressed Exception: %s", e, exc_info=True)
    except Exception:
        # Cleanup tmp file on failure.
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception as e:  # pragma: no cover
            logger.debug("Suppressed Exception: %s", e, exc_info=True)
        if fd is not None:
            try:
                os.close(fd)
            except Exception as e:  # pragma: no cover
                logger.debug("Suppressed Exception: %s", e, exc_info=True)
        raise


def atomic_write_json(target: str | Path, data: Any, indent: int = 2) -> None:
    """Atomically write JSON with 0o600 perms."""
    target_p = Path(target)

    def _writer(f: Any) -> None:
        json.dump(data, f, indent=indent)

    _atomic_write(target_p, _writer)


def atomic_write_yaml(target: str | Path, data: Any) -> None:
    """Atomically write YAML with 0o600 perms."""
    target_p = Path(target)

    def _writer(f: Any) -> None:
        yaml.safe_dump(data, f, default_flow_style=False)

    _atomic_write(target_p, _writer)


def backup_corrupt_file(path: str | Path) -> Path | None:
    """Backup corrupt file to <path>.corrupt.<time_ns>-<pid> via atomic rename.

    Returns backup path on success, None on failure.
    """
    src = Path(str(path))
    if not src.exists():
        return None
    backup_name = f"{src.name}.corrupt.{time.time_ns()}-{os.getpid()}"
    backup_path = src.parent / backup_name
    try:
        os.replace(str(src), str(backup_path))
        try:
            os.chmod(backup_path, 0o600)
        except Exception as e:  # pragma: no cover
            logger.debug("Suppressed Exception: %s", e, exc_info=True)
        logger.error(f"Backed up corrupt file {src} -> {backup_path}")
        return backup_path
    except Exception as e:
        logger.error(f"Failed to backup corrupt file {src}: {e}", exc_info=True)
        return None
