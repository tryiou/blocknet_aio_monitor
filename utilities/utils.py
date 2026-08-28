import contextlib
import json
import logging
import os
from pathlib import Path
from threading import current_thread, enumerate
from typing import Any

import customtkinter as ctk
import psutil
from cryptography.fernet import Fernet

from utilities.app_container import get_container
from utilities.atomic_write import atomic_write_json, backup_corrupt_file, ensure_dir_secure
from utilities.keyring_manager import KeyringManager, KeyringMigration, expand_config_path

logger = logging.getLogger(__name__)


def _resolve_aio_folder(container: Any) -> str:
    """Return expanded absolute AIO folder, never a raw '~' template.

    Delegates to keyring_manager.expand_config_path for consistent
    handling of ~, env vars, HOME unset fallback, and normpath.
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

        # Check if migration from old format (with salt) is needed
        if cfg_data and "salt" in cfg_data:
            logger.info("Detected old format with salt key. Starting migration to keyring...")
            keyring_manager = KeyringManager(local_conf_path)
            migration = KeyringMigration(local_conf_path, keyring_manager)

            success, new_cfg_data, message, old_key = migration.migrate_from_old_format(cfg_data)
            if success:
                # Save the migrated config atomically with 0o600
                try:
                    atomic_write_json(full_new_path, new_cfg_data, indent=2)
                except Exception as e:
                    logger.error(f"Failed to save migrated config: {e}", exc_info=True)
                    try:
                        with open(full_new_path, "w") as file:
                            json.dump(new_cfg_data, file, indent=2)
                    except Exception:  # noqa: S110, SIM105
                        pass  # noqa: S110, SIM105
                logger.info(f"Migration successful: {message}")
                cfg_data = new_cfg_data
            else:
                logger.error(f"Migration failed: {message}")

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

        # If removing password-related keys, also delete encryption key from keyring
        if key in ["salt", "xl_pass"]:
            delete_encryption_key()
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
    logger.info(f"{key} {data} was saved to configuration file: [{filename}]")


def save_encryption_key(key):
    """Save encryption key to keyring (or fallback storage)."""
    container = get_container()
    local_conf_path = _resolve_aio_folder(container)
    keyring_manager = KeyringManager(local_conf_path)
    success, message = keyring_manager.store_key(key)
    if success:
        logger.info(f"Encryption key saved: {message}")
    else:
        logger.error(f"Failed to save encryption key: {message}")
    return success


def load_encryption_key():
    """Load encryption key from keyring (or fallback storage)."""
    container = get_container()
    local_conf_path = _resolve_aio_folder(container)
    keyring_manager = KeyringManager(local_conf_path)
    key, message = keyring_manager.retrieve_key()
    if key:
        logger.info(f"Encryption key loaded: {message}")
        return key.encode("utf-8") if isinstance(key, str) else key
    else:
        logger.error(f"Failed to load encryption key: {message}")
        return None


def delete_encryption_key():
    """Delete encryption key from keyring and fallback storage."""
    container = get_container()
    local_conf_path = _resolve_aio_folder(container)
    keyring_manager = KeyringManager(local_conf_path)
    success, message = keyring_manager.delete_key()
    if success:
        logger.info(f"Encryption key deleted: {message}")
    else:
        logger.error(f"Failed to delete encryption key: {message}")
    return success


def generate_key():
    """Generate a new encryption key and store it in keyring."""
    key = Fernet.generate_key()
    # Store the key in keyring
    if save_encryption_key(key.decode("utf-8")):
        return key
    else:
        logger.error("Failed to store encryption key in keyring")
        return None


def encrypt_password(password, key=None):
    """Encrypt the password using the provided key or from keyring."""
    if key is None:
        key = load_encryption_key()
        if key is None:
            logger.error("No encryption key available for password encryption")
            return None

    cipher_suite = Fernet(key)
    encrypted_password = cipher_suite.encrypt(password.encode())
    return encrypted_password.decode()


def decrypt_password(encrypted_password, key=None):
    """Decrypt the encrypted password using the provided key or from keyring."""
    if key is None:
        key = load_encryption_key()
        if key is None:
            logger.error("No encryption key available for password decryption")
            return None

    cipher_suite = Fernet(key)
    decrypted_password = cipher_suite.decrypt(encrypted_password.encode())
    return decrypted_password.decode()


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
    if name == target_name:
        if status == "zombie":
            # the app was closed by user manually, clean zombie process
            process = psutil.Process(pid)
            process.wait()
            return None  # Don't add zombie processes to the list
        else:
            return pid
    return None
