"""
Keyring Manager Module

Provides secure keyring-based storage for encryption keys with fallback mechanisms
and cross-platform compatibility.

Service: blocknet_aio
Key Name: encryption_key
"""

import base64
import json
import logging
import os

logger = logging.getLogger(__name__)

try:
    import keyring

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logger.warning("keyring library not available. Using fallback storage.")


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
        self.config_path = config_path or os.getcwd()
        self.fallback_path = os.path.join(self.config_path, self.FALLBACK_FILE)
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """Ensure configuration directory exists."""
        try:
            os.makedirs(self.config_path, exist_ok=True)
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
        """Save encryption key to fallback storage (aio_settings.json)."""
        try:
            fallback_path = self._get_fallback_path()

            # Load existing config if it exists
            if os.path.exists(fallback_path):
                with open(fallback_path) as f:
                    data = json.load(f)
            else:
                data = {}

            # Update with encryption key (use "salt" for backward compatibility)
            data[self.FALLBACK_KEY_NAME] = key

            # Save to temporary file first (atomic operation)
            temp_path = fallback_path + ".tmp"
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)

            # Rename temporary file to actual file (atomic)
            os.replace(temp_path, fallback_path)

            logger.info("Encryption key saved to fallback storage")
            return True
        except Exception as e:
            logger.error(f"Failed to save to fallback: {e}")
            return False

    def _delete_fallback(self) -> bool:
        """Delete encryption key from fallback storage (aio_settings.json)."""
        try:
            fallback_path = self._get_fallback_path()
            if os.path.exists(fallback_path):
                # Load existing config
                with open(fallback_path) as f:
                    data = json.load(f)

                # Remove encryption key (use "salt" for backward compatibility)
                if self.FALLBACK_KEY_NAME in data:
                    del data[self.FALLBACK_KEY_NAME]

                # Save back to file
                with open(fallback_path, "w") as f:
                    json.dump(data, f, indent=2)

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
            except Exception:
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
            except Exception:
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
        self.config_path = config_path
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
        Migrate a configuration file from old to new format.

        Args:
            config_file_path: Path to aio_settings.json

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Read current config
            with open(config_file_path) as f:
                config_data = json.load(f)

            # Check if migration is needed
            if not self.detect_old_format(config_data):
                return True, "Config already in new format"

            # Perform migration
            success, new_config, message, old_key = self.migrate_from_old_format(config_data)
            if not success:
                return False, message

            # Write new config (may or may not include salt depending on keyring availability)
            with open(config_file_path, "w") as f:
                json.dump(new_config, f, indent=2)

            return True, message

        except Exception as e:
            self.logger.error(f"Config file migration failed: {e}")
            return False, f"Error: {str(e)}"
