import contextlib
import json
import logging
import os
from pathlib import Path
from threading import Lock, current_thread, enumerate
from typing import Any

import customtkinter as ctk
import psutil
from cryptography.fernet import Fernet, InvalidToken

from utilities.app_container import get_container
from utilities.atomic_write import atomic_write_json, backup_corrupt_file, ensure_dir_secure

logger = logging.getLogger(__name__)


def expand_config_path(path: str | None) -> str:
    """Expand user/env vars and normalize path.

    Prevents creation of literal '~' directory in CWD when a template
    path like '~/.AIO_Blocknet' is passed without expansion.
    Handles HOME unset fallback via Path.home() and normalizes with normpath.
    Idempotent — safe to call twice.
    """
    if not path or not str(path).strip():
        return os.getcwd()
    expanded = os.path.expandvars(os.path.expanduser(str(path)))
    # If expanduser failed (e.g. HOME unset), it still starts with ~ — resolve via Path.home()
    # Only handle "~" and "~/" — leave "~user" forms untouched to avoid mis-join
    if expanded == "~" or expanded.startswith("~/"):
        try:
            home = str(Path.home())
            # strip leading ~/ or ~ and join
            suffix = expanded[1:].lstrip("/\\")
            expanded = os.path.join(home, suffix) if suffix else home
        except Exception as e:  # debug logged
            logger.debug("Suppressed Exception: %s", e, exc_info=True)
        # Re-expand in case home contained vars (unlikely)
        expanded = os.path.expandvars(expanded)
    elif expanded.startswith("~"):
        # "~user" that failed to expand — avoid creating literal "~user" in CWD
        logger.warning(f"Unresolvable user path '{expanded}', falling back to HOME")
        try:
            expanded = os.path.join(str(Path.home()), expanded.lstrip("~/"))
            expanded = os.path.expandvars(expanded)
        except Exception as e:  # debug logged
            logger.debug("Suppressed Exception: %s", e, exc_info=True)
            return os.path.join(os.getcwd(), expanded.lstrip("~/").lstrip("/\\"))
    # Normalize to avoid trailing slash issues
    return os.path.normpath(expanded)


def _resolve_aio_folder(container: Any) -> str:
    """Return expanded absolute AIO folder, never a raw '~' template.

    Expands ~, env vars, HOME unset fallback, and normpath.
    Prefers container.aio_folder but falls back to conf_data template if
    aio_folder looks polluted (e.g. '/aio' from stale test singleton).
    """
    raw = None
    try:
        raw = container.aio_folder
    except Exception as e:  # debug logged
        logger.debug("Suppressed Exception: %s", e, exc_info=True)
    # Guard against MagicMock aio_folder (e.g. MagicMock(name='mock.aio_folder'))
    # which str() -> "<MagicMock name='...' id='...'>" would otherwise create real dirs.
    if raw is not None:
        try:
            raw_s = str(raw)
            if raw_s.startswith("<MagicMock") or "MagicMock" in raw_s:
                logger.debug("Skipping mocked aio_folder %s, falling back to conf_data template", raw_s)
                raw = None
            elif not isinstance(raw, (str, Path, os.PathLike)):
                # Non-path-like mock that slipped through string check
                if "MagicMock" in raw_s or "<MagicMock" in raw_s:
                    logger.debug("Skipping mocked aio_folder %s", raw_s)
                    raw = None
        except Exception as e:  # debug logged
            logger.debug("Suppressed Exception: %s", e, exc_info=True)
            raw = None
    if raw and str(raw).strip():
        expanded = expand_config_path(str(raw))
        # Guard against polluted singleton (e.g. "/aio" from test mock not cleaned).
        # Handle both POSIX ("/aio") and Windows ("\\aio") separators.
        norm_forward = expanded.replace("\\", "/")
        if norm_forward in ("/aio", "/aio/path") or norm_forward.startswith("/aio/"):
            logger.warning(
                f"Suspicious aio_folder '{raw}' expanded to '{expanded}', falling back to conf_data template"
            )
        else:
            return expanded

    try:
        raw = container.conf_data.aio_blocknet_data_path.get(container.system, "")
    except Exception as e:  # debug logged
        logger.debug("Suppressed Exception: %s", e, exc_info=True)
        raw = ""
    return expand_config_path(str(raw) if raw else None)


def configure_tooltip_text(tooltip, msg):
    if tooltip.get() != msg:
        tooltip.configure(message=msg)


def load_cfg_json():
    local_filename = "aio_settings.json"
    old_local_filename = "cfg.json"

    container = get_container()
    local_conf_path = _resolve_aio_folder(container)
    full_old_path = os.path.join(local_conf_path, old_local_filename)
    full_new_path = os.path.join(local_conf_path, local_filename)

    if os.path.exists(full_old_path):
        # migrate old config file atomically
        logger.info(f"Renaming {full_old_path} to {full_new_path}")
        try:
            # Ensure dir exists with 0o700 before rename
            ensure_dir_secure(local_conf_path, 0o700)
            os.replace(full_old_path, full_new_path)
        except Exception as e:
            # Fallback to legacy rename for mocked tests
            try:
                os.rename(full_old_path, full_new_path)  # noqa: PTH104
            except Exception as e2:
                logger.error(
                    f"Failed to migrate old config {full_old_path} -> {full_new_path}: {e} / {e2}",
                    exc_info=True,
                )

    # Check if the file exists
    if os.path.exists(full_new_path):
        try:
            with open(full_new_path) as file:
                cfg_data = json.load(file)
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted JSON in {full_new_path}: {e}, backing up and self-healing")
            backup_corrupt_file(full_new_path)
            return {}
        except FileNotFoundError:
            logger.info(f"Configuration file not found (race): [{full_new_path}]")
            return None

        logger.info(f"Configuration file loaded ok: [{full_new_path}]")
        return cfg_data
    else:
        logger.info(f"Configuration file not found: [{full_new_path}]")
        return None


def join_daemon_threads(timeout: float = 0.25) -> None:
    """Cooperatively join daemon threads; does not kill threads.

    Only joins daemon threads other than the current thread. Logs whether
    threads are still alive after timeout instead of claiming terminated.
    """
    logger.info("Joining daemon threads...")
    for thread in enumerate():
        if thread is current_thread():
            continue
        if not thread.daemon:
            logger.debug(f"Skipping non-daemon thread: {thread.name}")
            continue
        thread.join(timeout=timeout)
        if thread.is_alive():
            logger.warning(f"Thread {thread.name} still alive after {timeout}s")
        else:
            logger.info(f"Thread {thread.name} joined")


def terminate_all_threads(timeout: float = 0.25) -> None:
    """Backward-compat wrapper: does not terminate threads, only joins daemons."""
    logger.warning("terminate_all_threads is deprecated, use join_daemon_threads (does not kill)")
    join_daemon_threads(timeout=timeout)


def remove_cfg_json_key(key):
    container = get_container()
    local_filename = "aio_settings.json"
    local_conf_path = _resolve_aio_folder(container)
    filename = os.path.join(local_conf_path, local_filename)

    # Try loading the existing JSON file
    try:
        with open(filename) as file:
            cfg_data = json.load(file)
    except FileNotFoundError:
        logger.error(f"Failed to load JSON file: [{filename}]")
        return
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted JSON in {filename}: {e}, backing up")
        backup_corrupt_file(filename)
        return

    # Check if the key exists in the dictionary
    if key in cfg_data:
        # Remove the key from the dictionary
        del cfg_data[key]
        try:
            atomic_write_json(filename, cfg_data, indent=2)
        except Exception as e:
            logger.error(f"Atomic write failed for {filename}: {e}, fallback to direct write", exc_info=True)
            try:
                ensure_dir_secure(local_conf_path, 0o700)
                with open(filename, "w") as file:
                    json.dump(cfg_data, file, indent=2)
                with contextlib.suppress(Exception):
                    os.chmod(filename, 0o600)
            except Exception as e2:
                logger.error(f"Failed to remove key {key}: {e2}", exc_info=True)
                return
        logger.info(f"Key '{key}' was removed from configuration file: [{filename}]")
    else:
        logger.warning(f"Key '{key}' not found in configuration file: [{filename}]")


def save_cfg_json(key, data):
    container = get_container()
    local_filename = "aio_settings.json"
    local_conf_path = _resolve_aio_folder(container)
    filename = os.path.join(local_conf_path, local_filename)

    # Try loading the existing JSON file
    try:
        with open(filename) as file:
            cfg_data = json.load(file)
    except FileNotFoundError:
        # If file doesn't exist, create a new empty dictionary
        cfg_data = {}
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted JSON in {filename}: {e}, backing up and self-healing")
        backup_corrupt_file(filename)
        cfg_data = {}

    cfg_data.update({key: data})

    # Save atomically with 0o600
    try:
        atomic_write_json(filename, cfg_data, indent=2)
    except Exception as e:
        logger.error(f"Atomic write failed for {filename}: {e}, fallback to direct write", exc_info=True)
        try:
            ensure_dir_secure(local_conf_path, 0o700)
            with open(filename, "w") as file:
                json.dump(cfg_data, file, indent=2)
            with contextlib.suppress(Exception):
                os.chmod(filename, 0o600)
        except Exception as e2:
            logger.error(f"Failed to save {key}: {e2}", exc_info=True)
            return
    logger.info(f"Key '{key}' was saved to configuration file: [{filename}]")


# Single-route credential store.
#
# The encryption key ("salt") and the ciphertext ("xl_pass") live together
# in aio_settings.json and are committed in ONE atomic rewrite, so key and
# ciphertext can never disagree. Security boundary is OS file permissions
# (0o600 file in 0o700 dir on POSIX; per-user %APPDATA% profile on Windows).
# There is no OS keyring, no fallback store, no second path — by design.
_CREDENTIALS_LOCK = Lock()
CREDENTIALS_FILENAME = "aio_settings.json"
CREDENTIALS_KEY_NAME = "salt"
CREDENTIALS_PASS_NAME = "xl_pass"  # noqa: S105 # config key name, not a password


def store_password(password: str) -> bool:
    """Store wallet password: fresh key + ciphertext committed atomically.

    Returns True on success, False on any failure (nothing half-written:
    the atomic rewrite either lands with both values or not at all).
    """
    container = get_container()
    filename = os.path.join(_resolve_aio_folder(container), CREDENTIALS_FILENAME)
    try:
        key = Fernet.generate_key()
        ciphertext = Fernet(key).encrypt(password.encode()).decode()
    except Exception as e:
        logger.error(f"Failed to encrypt password: {e}", exc_info=True)
        return False
    with _CREDENTIALS_LOCK:
        try:
            try:
                with open(filename) as file:
                    cfg_data = json.load(file)
                if not isinstance(cfg_data, dict):
                    cfg_data = {}
            except FileNotFoundError:
                cfg_data = {}
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted JSON in {filename}: {e}, backing up and self-healing")
                backup_corrupt_file(filename)
                cfg_data = {}
            cfg_data[CREDENTIALS_KEY_NAME] = key.decode("utf-8")
            cfg_data[CREDENTIALS_PASS_NAME] = ciphertext
            atomic_write_json(filename, cfg_data, indent=2)
        except Exception as e:
            logger.error(f"Failed to store password: {e}", exc_info=True)
            return False
    logger.info("XLite password stored")
    return True


def load_stored_password() -> str | None:
    """Load and decrypt the wallet password.

    Returns the password, or None when absent/unreadable. Never deletes
    anything: an undecryptable file is kept on disk for the user to
    re-store over.
    """
    container = get_container()
    filename = os.path.join(_resolve_aio_folder(container), CREDENTIALS_FILENAME)
    try:
        with open(filename) as file:
            cfg_data = json.load(file)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted JSON in {filename}: {e}, backing up and self-healing")
        backup_corrupt_file(filename)
        return None
    except Exception as e:
        logger.error(f"Failed to load stored password: {e}", exc_info=True)
        return None
    if not isinstance(cfg_data, dict):
        return None
    key = cfg_data.get(CREDENTIALS_KEY_NAME)
    ciphertext = cfg_data.get(CREDENTIALS_PASS_NAME)
    if not key or not ciphertext:
        return None
    try:
        raw_key = key.encode("utf-8") if isinstance(key, str) else key
        return Fernet(raw_key).decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        logger.error(
            f"Stored password cannot be decrypted with stored key ({type(e).__name__}): "
            "data kept, please Store Password again",
            exc_info=True,
        )
        return None
    except Exception as e:
        logger.error(f"Failed to decrypt stored password: {e}", exc_info=True)
        return None


def wipe_stored_password() -> bool:
    """Remove key and ciphertext. True when neither remains afterwards."""
    container = get_container()
    filename = os.path.join(_resolve_aio_folder(container), CREDENTIALS_FILENAME)
    with _CREDENTIALS_LOCK:
        try:
            try:
                with open(filename) as file:
                    cfg_data = json.load(file)
            except FileNotFoundError:
                return True
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted JSON in {filename}: {e}, backing up")
                backup_corrupt_file(filename)
                return False
            if not isinstance(cfg_data, dict):
                return False
            cfg_data.pop(CREDENTIALS_KEY_NAME, None)
            cfg_data.pop(CREDENTIALS_PASS_NAME, None)
            atomic_write_json(filename, cfg_data, indent=2)
        except Exception as e:
            logger.error(f"Failed to wipe stored password: {e}", exc_info=True)
            return False
    logger.info("Stored XLite password wiped")
    return True


def enable_button(button, img=None):
    if button.cget("state") == ctk.DISABLED:
        button.configure(state=ctk.NORMAL)
    if img:
        button.configure(image=img)


def disable_button(button, img=None):
    if button.cget("state") == ctk.NORMAL:
        button.configure(state=ctk.DISABLED)
    if img:
        button.configure(image=img)


def processes_check():
    """Check for running processes related to Blocknet, BlockDX, and Xlite."""
    container = get_container()
    blocknet_bin = container.blocknet_bin
    blockdx_bin = container.blockdx_bin[-1] if container.system == "Darwin" else container.blockdx_bin
    xlite_bin = container.xlite_bin[-1] if container.system == "Darwin" else container.xlite_bin
    xlite_daemon_bin = container.xlite_daemon_bin
    # Initialize process lists
    process_lists: dict = {blocknet_bin: [], blockdx_bin: [], xlite_bin: [], xlite_daemon_bin: []}

    # Process all running processes
    for proc in psutil.process_iter(["pid", "name", "status"]):
        pid = proc.info["pid"]
        name = proc.info["name"]
        status = proc.info["status"]

        # Check against each target process type
        for target_name, process_list in process_lists.items():
            result_pid = handle_process(pid, name, status, target_name)
            if result_pid is not None:
                process_list.append(result_pid)
                break  # Process matched, no need to check other types

    return (
        process_lists[blocknet_bin],
        process_lists[blockdx_bin],
        process_lists[xlite_bin],
        process_lists[xlite_daemon_bin],
    )


def handle_process(pid, name, status, target_name):
    """Helper function to handle individual process logic."""
    # Dev builds run as `xlite-daemon` (no suffix) while the configured name
    # is `xlite-daemon-linux64` / `xlite-daemon-win64.exe` / `xlite-daemon-osx64`.
    # Accept the dev alias only — do not match cross-platform suffixed names.
    if not isinstance(name, str) or not isinstance(target_name, str):
        return None
    n = name.lower().removesuffix(".exe")
    t = target_name.lower().removesuffix(".exe")
    is_match = n == t or (n == "xlite-daemon" and t.startswith("xlite-daemon-"))
    if is_match:
        if status == "zombie":
            # the app was closed by user manually, clean zombie process
            process = psutil.Process(pid)
            process.wait()
            return None  # Don't add zombie processes to the list
        else:
            return pid
    return None
