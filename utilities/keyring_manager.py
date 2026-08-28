"""
Keyring Manager Module

Provides secure keyring-based storage for encryption keys with fallback mechanisms
and cross-platform compatibility.

Service: blocknet_aio
Key Name: encryption_key
"""

import base64
import contextlib
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import keyring

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logger.warning("keyring library not available. Using fallback storage.")


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
    # Only handle "~" and "~/..." — leave "~user" forms untouched to avoid mis-join
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


class KeyringManager:
    """Manages encryption key storage using OS keyring with fallback mechanisms."""

    SERVICE_NAME = "blocknet_aio"
    KEY_NAME = "encryption_key"
    FALLBACK_FILE = "aio_settings.json"
    FALLBACK_KEY_NAME = "salt"  # Use "salt" for backward compatibility

    def __init__(self, config_path: str | None = None):
        """
        Initialize KeyringManager.

        Args:
            config_path: Path to configuration directory for fallback storage
        """
        self.config_path = expand_config_path(config_path)
        self.fallback_path = os.path.join(self.config_path, self.FALLBACK_FILE)
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Ensure configuration directory exists with 0o700."""
        try:
            os.makedirs(self.config_path, exist_ok=True)
            try:
                os.chmod(self.config_path, 0o700)
            except Exception as e:  # pragma: no cover - Windows
                logger.debug("Suppressed Exception: %s", e, exc_info=True)
        except Exception as e:
            logger.error(f"Failed to create config directory: {e}")

    def _get_fallback_path(self) -> str:
        """Get the full path to the fallback file."""
        return self.fallback_path

    def _load_fallback(self) -> str | None:
        """Load encryption key from fallback storage (aio_settings.json)."""
        try:
            fallback_path = self._get_fallback_path()
            if os.path.exists(fallback_path):
                with open(fallback_path) as f:
                    data = json.load(f)
                    key = data.get(self.FALLBACK_KEY_NAME)
                    if key:
                        logger.info("Encryption key loaded from fallback storage")
                        return key
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted JSON in fallback file: {e}")
        except Exception as e:
            logger.error(f"Failed to load from fallback: {e}")
        return None

    def _save_fallback(self, key: str) -> bool:
        """Save encryption key to fallback storage (aio_settings.json) atomically with 0o600."""
        try:
            fallback_path = self._get_fallback_path()

            # Load existing config if it exists
            if os.path.exists(fallback_path):
                try:
                    with open(fallback_path) as f:
                        data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(f"Corrupted JSON in fallback file {fallback_path}: {e}, backing up")
                    try:
                        from utilities.atomic_write import backup_corrupt_file

                        backup_corrupt_file(fallback_path)
                    except Exception:  # noqa: S110, SIM105
                        pass  # noqa: S110, SIM105
                    data = {}
            else:
                data = {}

            # Update with encryption key (use "salt" for backward compatibility)
            data[self.FALLBACK_KEY_NAME] = key

            # Atomic write with 0o600 via helper
            try:
                from utilities.atomic_write import atomic_write_json

                atomic_write_json(fallback_path, data, indent=2)
            except Exception:  # noqa: S110, SIM105
                # Fallback manual atomic with os.open 0o600 if helper fails
                import time as _time

                dir_path = os.path.dirname(fallback_path) or "."
                try:
                    os.makedirs(dir_path, exist_ok=True)
                    with contextlib.suppress(Exception):
                        os.chmod(dir_path, 0o700)
                except Exception:  # noqa: S110, SIM105
                    pass  # noqa: S110, SIM105
                tmp_path = fallback_path + f".tmp.{os.getpid()}.{_time.time_ns()}"
                flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                try:
                    flags |= os.O_NOFOLLOW  # type: ignore[attr-defined]
                except AttributeError:  # noqa: S110, SIM105
                    pass  # noqa: S110, SIM105
                fd = os.open(tmp_path, flags, 0o600)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                        fd = None
                    with contextlib.suppress(Exception):
                        os.chmod(tmp_path, 0o600)
                    os.replace(tmp_path, fallback_path)
                    with contextlib.suppress(Exception):
                        os.chmod(fallback_path, 0o600)
                finally:
                    if fd is not None:
                        with contextlib.suppress(Exception):
                            os.close(fd)
                    try:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                    except Exception:  # noqa: S110, SIM105
                        pass  # noqa: S110, SIM105

            logger.info("Encryption key saved to fallback storage")
            return True
        except Exception as e:
            logger.error(f"Failed to save to fallback: {e}")
            return False

    def _delete_fallback(self) -> bool:
        """Delete encryption key from fallback storage (aio_settings.json) atomically with 0o600."""
        try:
            fallback_path = self._get_fallback_path()
            if os.path.exists(fallback_path):
                try:
                    with open(fallback_path) as f:
                        data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(f"Corrupted JSON in fallback file {fallback_path}: {e}, backing up")
                    try:
                        from utilities.atomic_write import backup_corrupt_file

                        backup_corrupt_file(fallback_path)
                    except Exception:  # noqa: S110, SIM105
                        pass  # noqa: S110, SIM105
                    logger.info("Encryption key removed from fallback storage (corrupt file backed up)")
                    return True

                # Remove encryption key (use "salt" for backward compatibility)
                if self.FALLBACK_KEY_NAME in data:
                    del data[self.FALLBACK_KEY_NAME]

                # Save atomically with 0o600
                try:
                    from utilities.atomic_write import atomic_write_json

                    atomic_write_json(fallback_path, data, indent=2)
                except Exception:  # noqa: S110, SIM105
                    import time as _time

                    dir_path = os.path.dirname(fallback_path) or "."
                    try:
                        os.makedirs(dir_path, exist_ok=True)
                        with contextlib.suppress(Exception):
                            os.chmod(dir_path, 0o700)
                    except Exception:  # noqa: S110, SIM105
                        pass  # noqa: S110, SIM105
                    tmp_path = fallback_path + f".tmp.{os.getpid()}.{_time.time_ns()}"
                    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                    try:
                        flags |= os.O_NOFOLLOW  # type: ignore[attr-defined]
                    except AttributeError:  # noqa: S110, SIM105
                        pass  # noqa: S110, SIM105
                    fd = os.open(tmp_path, flags, 0o600)
                    try:
                        with os.fdopen(fd, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                            fd = None
                        with contextlib.suppress(Exception):
                            os.chmod(tmp_path, 0o600)
                        os.replace(tmp_path, fallback_path)
                        with contextlib.suppress(Exception):
                            os.chmod(fallback_path, 0o600)
                    finally:
                        if fd is not None:
                            with contextlib.suppress(Exception):
                                os.close(fd)
                        try:
                            if os.path.exists(tmp_path):
                                os.unlink(tmp_path)
                        except Exception:  # noqa: S110, SIM105
                            pass  # noqa: S110, SIM105

                logger.info("Encryption key removed from fallback storage")
            return True
        except Exception as e:
            logger.error(f"Failed to delete from fallback: {e}")  # noqa: S608 # false positive, not SQL
            return False

    def store_key(self, key: str | bytes) -> tuple[bool, str]:
        """
        Store encryption key in keyring (or fallback).

        Args:
            key: Encryption key as string or bytes

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Convert key to string if bytes
            key_str = key.decode("utf-8") if isinstance(key, bytes) else key

            # Validate key format (should be base64 encoded)
            try:
                base64.b64decode(key_str)
            except Exception:  # noqa: S110, SIM105
                logger.warning(f"Key is not valid base64: {key_str[:20]}...")

            # Try keyring first
            if KEYRING_AVAILABLE:
                try:
                    keyring.set_password(self.SERVICE_NAME, self.KEY_NAME, key_str)
                    logger.info("Encryption key stored in OS keyring")
                    return True, "Key stored in OS keyring"
                except Exception as e:
                    logger.warning(f"Keyring storage failed: {e}. Using fallback.")

            # Fallback to file-based storage
            if self._save_fallback(key_str):
                return True, "Key stored in fallback storage"
            else:
                return False, "Failed to store key in any storage"

        except Exception as e:
            logger.error(f"Error storing key: {e}")
            return False, f"Error: {str(e)}"

    def retrieve_key(self) -> tuple[str | None, str]:
        """
        Retrieve encryption key from keyring (or fallback).

        Returns:
            Tuple of (key: str | None, message: str)
        """
        try:
            # Try keyring first
            if KEYRING_AVAILABLE:
                try:
                    key = keyring.get_password(self.SERVICE_NAME, self.KEY_NAME)
                    if key:
                        logger.info("Encryption key retrieved from OS keyring")
                        return key, "Key retrieved from OS keyring"
                except Exception as e:
                    logger.warning(f"Keyring retrieval failed: {e}. Trying fallback.")

            # Fallback to file-based storage
            key = self._load_fallback()
            if key:
                return key, "Key retrieved from fallback storage"

            return None, "No encryption key found"

        except Exception as e:
            logger.error(f"Error retrieving key: {e}")
            return None, f"Error: {str(e)}"

    def delete_key(self) -> tuple[bool, str]:
        """
        Delete encryption key from keyring and fallback.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            success = False
            messages = []

            # Try to delete from keyring
            if KEYRING_AVAILABLE:
                try:
                    keyring.delete_password(self.SERVICE_NAME, self.KEY_NAME)
                    messages.append("Deleted from OS keyring")
                    success = True
                except Exception as e:
                    logger.warning(f"Keyring deletion failed: {e}")

            # Delete from fallback
            if self._delete_fallback():
                messages.append("Deleted from fallback storage")
                success = True

            message = "; ".join(messages) if messages else "No key found to delete"
            return success, message

        except Exception as e:
            logger.error(f"Error deleting key: {e}")
            return False, f"Error: {str(e)}"

    def key_exists(self) -> bool:
        """Check if encryption key exists in any storage."""
        if KEYRING_AVAILABLE:
            try:
                if keyring.get_password(self.SERVICE_NAME, self.KEY_NAME):
                    return True
            except Exception as e:  # debug logged
                logger.debug("Suppressed Exception: %s", e, exc_info=True)

        # Check if fallback file exists and contains the key (use "salt" for backward compatibility)
        if os.path.exists(self._get_fallback_path()):
            try:
                with open(self._get_fallback_path()) as f:
                    data = json.load(f)
                    return self.FALLBACK_KEY_NAME in data
            except Exception as e:  # debug logged
                logger.debug("Suppressed Exception: %s", e, exc_info=True)

        return False

    def get_storage_info(self) -> dict:
        """Get information about current storage method."""
        info = {
            "keyring_available": KEYRING_AVAILABLE,
            "keyring_service": self.SERVICE_NAME,
            "keyring_key": self.KEY_NAME,
            "fallback_path": self._get_fallback_path(),
            "fallback_exists": os.path.exists(self._get_fallback_path()),
            "key_exists": self.key_exists(),
        }

        # Check which storage is active
        if KEYRING_AVAILABLE:
            try:
                keyring_key = keyring.get_password(self.SERVICE_NAME, self.KEY_NAME)
                if keyring_key:
                    info["active_storage"] = "keyring"
                elif os.path.exists(self._get_fallback_path()):
                    info["active_storage"] = "fallback"
                else:
                    info["active_storage"] = "none"
            except Exception:  # noqa: S110, SIM105
                if os.path.exists(self._get_fallback_path()):
                    info["active_storage"] = "fallback"
                else:
                    info["active_storage"] = "none"
        else:
            info["active_storage"] = "fallback" if os.path.exists(self._get_fallback_path()) else "none"

        return info


class KeyringMigration:
    """Handles migration from old format (JSON with salt) to new format (keyring)."""

    def __init__(self, config_path: str, keyring_manager: KeyringManager):
        self.config_path = expand_config_path(config_path)
        self.keyring_manager = keyring_manager
        self.logger = logging.getLogger(__name__)

    def detect_old_format(self, config_data: dict) -> bool:
        """Detect if config data is in old format with salt key."""
        return "salt" in config_data and "xl_pass" in config_data

    def migrate_from_old_format(self, config_data: dict) -> tuple[bool, dict, str, str | None]:
        """
        Migrate from old format to new format.

        Args:
            config_data: Current configuration data

        Returns:
            Tuple of (success: bool, new_config: dict, message: str, key: str | None)
        """
        try:
            if not self.detect_old_format(config_data):
                return True, config_data, "Already in new format", None

            self.logger.info("Starting migration from old format...")

            # Extract the old encryption key
            old_key = config_data.get("salt")
            if not old_key:
                return False, config_data, "No salt key found in old format", None

            # Try to store key in keyring
            success, message = self.keyring_manager.store_key(old_key)

            if success:
                # Check if key was stored in keyring or fallback
                if "keyring" in message.lower():
                    # Keyring storage successful - remove salt from config
                    new_config = {k: v for k, v in config_data.items() if k != "salt"}
                    self.logger.info("Migration completed successfully - key stored in keyring")
                    return True, new_config, "Migration successful - key stored in keyring", old_key
                else:
                    # Fallback storage - keep salt in config
                    self.logger.info("Migration completed successfully - key stored in fallback")
                    return True, config_data, "Migration successful - key stored in fallback (salt kept)", old_key
            else:
                # Storage failed
                self.logger.error(f"Migration failed: {message}")
                return False, config_data, f"Migration failed: {message}", None

        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            return False, config_data, f"Migration error: {str(e)}", None

    def migrate_config_file(self, config_file_path: str) -> tuple[bool, str]:
        """
        Migrate a configuration file from old to new format atomically with 0o600.

        Args:
            config_file_path: Path to aio_settings.json

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Read current config
            try:
                with open(config_file_path) as f:
                    config_data = json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Corrupted JSON in {config_file_path}: {e}, backing up")
                try:
                    from utilities.atomic_write import backup_corrupt_file

                    backup_corrupt_file(config_file_path)
                except Exception:  # noqa: S110, SIM105
                    pass  # noqa: S110, SIM105
                return False, f"Error: corrupted JSON: {e}"
            except FileNotFoundError as e:
                self.logger.error(f"Config file migration failed: {e}")
                return False, f"Error: {str(e)}"

            # Check if migration is needed
            if not self.detect_old_format(config_data):
                return True, "Config already in new format"

            # Perform migration
            success, new_config, message, old_key = self.migrate_from_old_format(config_data)
            if not success:
                return False, message

            # Write new config atomically with 0o600
            try:
                from utilities.atomic_write import atomic_write_json

                atomic_write_json(config_file_path, new_config, indent=2)
            except Exception:  # noqa: S110, SIM105
                import time as _time

                dir_path = os.path.dirname(config_file_path) or "."
                try:
                    os.makedirs(dir_path, exist_ok=True)
                    with contextlib.suppress(Exception):
                        os.chmod(dir_path, 0o700)
                except Exception:  # noqa: S110, SIM105
                    pass  # noqa: S110, SIM105
                tmp_path = config_file_path + f".tmp.{os.getpid()}.{_time.time_ns()}"
                flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
                try:
                    flags |= os.O_NOFOLLOW  # type: ignore[attr-defined]
                except AttributeError:  # noqa: S110, SIM105
                    pass  # noqa: S110, SIM105
                fd = os.open(tmp_path, flags, 0o600)
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        json.dump(new_config, f, indent=2)
                        fd = None
                    with contextlib.suppress(Exception):
                        os.chmod(tmp_path, 0o600)
                    os.replace(tmp_path, config_file_path)
                    with contextlib.suppress(Exception):
                        os.chmod(config_file_path, 0o600)
                finally:
                    if fd is not None:
                        with contextlib.suppress(Exception):
                            os.close(fd)
                    try:
                        if os.path.exists(tmp_path):
                            os.unlink(tmp_path)
                    except Exception:  # noqa: S110, SIM105
                        pass  # noqa: S110, SIM105

            return True, message

        except Exception as e:
            self.logger.error(f"Config file migration failed: {e}")
            return False, f"Error: {str(e)}"
