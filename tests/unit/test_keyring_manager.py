"""
Unit tests for keyring_manager module.

Tests keyring-based encryption key storage with fallback mechanisms.
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest

from utilities.keyring_manager import KeyringManager, KeyringMigration

# Constants for test data
TEST_KEY = "test_encryption_key_123"
TEST_SALT = "test_salt_key_base64"
TEST_THEME = "Dark"
TEST_PATH = "/path/to/blocknet"
TEST_PASSWORD = "encrypted_password_base64"


# Fixtures for common test setups
@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def manager(temp_dir):
    """Create a KeyringManager instance with a temporary directory."""
    return KeyringManager(temp_dir)


@pytest.fixture
def manager_with_fallback_key(manager):
    """Create a KeyringManager with a key stored in fallback."""
    with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
        manager.store_key(TEST_KEY)
    return manager


@pytest.fixture
def mock_keyring():
    """Mock the keyring module with KEYRING_AVAILABLE=True."""
    with (
        patch("utilities.keyring_manager.KEYRING_AVAILABLE", True),
        patch("utilities.keyring_manager.keyring") as mock_keyring,
    ):
        yield mock_keyring


@pytest.fixture
def old_config():
    """Return a sample old-format configuration."""
    return {"theme": TEST_THEME, "custom_path": TEST_PATH, "salt": TEST_SALT, "xl_pass": TEST_PASSWORD}


@pytest.fixture
def new_config():
    """Return a sample new-format configuration."""
    return {"theme": TEST_THEME, "xl_pass": TEST_PASSWORD}


# Helper methods for test setup
def setup_fallback_key(manager):
    """Helper to store a key in fallback storage."""
    with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
        manager.store_key(TEST_KEY)


def setup_keyring_mock(mock_keyring, key=TEST_KEY, should_fail=False):
    """Helper to configure the mock keyring."""
    if should_fail:
        mock_keyring.get_password.side_effect = Exception("Keyring error")
        mock_keyring.set_password.side_effect = Exception("Keyring error")
        mock_keyring.delete_password.side_effect = Exception("Keyring error")
    else:
        mock_keyring.get_password.return_value = key
        mock_keyring.set_password.return_value = None
        mock_keyring.delete_password.return_value = None


# Test KeyringManager
class TestKeyringManager:
    """Test cases for KeyringManager class."""

    class TestHappyPath:
        """Tests for normal, expected behavior."""

        def test_init_with_config_path(self, temp_dir):
            """Test initialization with custom config path."""
            manager = KeyringManager(temp_dir)
            assert manager.config_path == temp_dir
            assert manager.fallback_path == os.path.join(temp_dir, "aio_settings.json")

        def test_init_without_config_path(self):
            """Test initialization without config path (uses current directory)."""
            manager = KeyringManager()
            assert manager.config_path == os.getcwd()

        def test_store_key_fallback_success(self, manager):
            """Test storing key using fallback storage."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                success, message = manager.store_key(TEST_KEY)

                assert success is True
                assert "fallback" in message.lower()

                # Verify key was saved to aio_settings.json
                fallback_path = manager.fallback_path
                assert os.path.exists(fallback_path)

                with open(fallback_path) as f:
                    data = json.load(f)
                    assert data["salt"] == TEST_KEY

        def test_retrieve_key_fallback_success(self, manager_with_fallback_key):
            """Test retrieving key from fallback storage."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                key, message = manager_with_fallback_key.retrieve_key()

            # Fallback storage encrypts the key, so we get the encrypted value back
            assert key is not None and len(key) > 0
            assert "fallback" in message.lower()

        def test_retrieve_key_not_found(self, manager):
            """Test retrieving key when none exists."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                key, message = manager.retrieve_key()

                assert key is None
                assert "no encryption key found" in message.lower()

        def test_delete_key_fallback_success(self, manager_with_fallback_key):
            """Test deleting key from fallback storage."""
            fallback_path = manager_with_fallback_key.fallback_path
            assert os.path.exists(fallback_path)

            success, message = manager_with_fallback_key.delete_key()

            assert success is True
            # File should still exist but without salt
            assert os.path.exists(fallback_path)
            with open(fallback_path) as f:
                data = json.load(f)
                assert "salt" not in data

        def test_key_exists_true(self, manager_with_fallback_key):
            """Test key_exists returns True when key exists."""
            assert manager_with_fallback_key.key_exists() is True

        def test_key_exists_false(self, manager):
            """Test key_exists returns False when key doesn't exist."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                assert manager.key_exists() is False

        def test_key_exists_with_keyring(self, manager, mock_keyring):
            """Test key_exists returns True when key exists in keyring."""
            setup_keyring_mock(mock_keyring)
            assert manager.key_exists() is True

        def test_get_storage_info_fallback(self, manager_with_fallback_key):
            """Test getting storage information for fallback."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                info = manager_with_fallback_key.get_storage_info()

                assert info["keyring_available"] is False
                assert info["keyring_service"] == "blocknet_aio"
                assert info["keyring_key"] == "encryption_key"
                assert info["fallback_exists"] is True
                assert info["key_exists"] is True
                assert info["active_storage"] == "fallback"

        def test_get_storage_info_keyring_key_exists(self, manager, mock_keyring):
            """Test getting storage information when key exists in keyring."""
            setup_keyring_mock(mock_keyring)

            info = manager.get_storage_info()

            assert info["keyring_available"] is True
            assert info["keyring_service"] == "blocknet_aio"
            assert info["keyring_key"] == "encryption_key"
            assert info["fallback_exists"] is False
            assert info["key_exists"] is True
            assert info["active_storage"] == "keyring"

        def test_get_storage_info_keyring_key_missing(self, manager, mock_keyring):
            """Test getting storage information when keyring returns None."""
            setup_keyring_mock(mock_keyring, key=None)

            info = manager.get_storage_info()

            assert info["keyring_available"] is True
            assert info["fallback_exists"] is False
            assert info["key_exists"] is False
            assert info["active_storage"] == "none"

        def test_store_key_with_keyring_success(self, manager, mock_keyring):
            """Test storing key using keyring when available."""
            success, message = manager.store_key(TEST_KEY)

            assert success is True
            assert "keyring" in message.lower()
            mock_keyring.set_password.assert_called_once_with("blocknet_aio", "encryption_key", TEST_KEY)

        def test_retrieve_key_with_keyring_success(self, manager, mock_keyring):
            """Test retrieving key from keyring when available."""
            setup_keyring_mock(mock_keyring)

            key, message = manager.retrieve_key()

            assert key == TEST_KEY
            assert "keyring" in message.lower()
            mock_keyring.get_password.assert_called_once_with("blocknet_aio", "encryption_key")

        def test_delete_key_with_keyring_success(self, manager, mock_keyring):
            """Test deleting key from keyring when available."""
            success, message = manager.delete_key()

            assert success is True
            assert "keyring" in message.lower()
            mock_keyring.delete_password.assert_called_once_with("blocknet_aio", "encryption_key")

    class TestEdgeCases:
        """Tests for edge cases and unusual inputs."""

        def test_store_key_with_bytes(self, manager):
            """Test storing key when key is bytes instead of string."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                test_key_bytes = b"test_encryption_key_123"

                success, message = manager.store_key(test_key_bytes)

                assert success is True
                assert "fallback" in message.lower()

                # Verify key was saved as string
                fallback_path = manager.fallback_path
                with open(fallback_path) as f:
                    data = json.load(f)
                    assert data["salt"] == test_key_bytes.decode("utf-8")

        def test_store_key_invalid_base64(self, manager):
            """Test storing key that is not valid base64 (should still work with warning)."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                test_key = "not-valid-base64!@#"

                success, message = manager.store_key(test_key)

                assert success is True
                assert "fallback" in message.lower()

        def test_delete_key_nonexistent(self, manager):
            """Test deleting key when no key exists."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                success, message = manager.delete_key()

                assert success is True
                # File doesn't exist, so _delete_fallback returns True (nothing to delete)
                assert "deleted from fallback storage" in message.lower()

        def test_delete_key_corrupted_json(self, manager):
            """Test deleting key when fallback file has corrupted JSON."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                # Create corrupted JSON file
                fallback_path = manager.fallback_path
                with open(fallback_path, "w") as f:
                    f.write("{invalid json")

                success, message = manager.delete_key()

                assert success is False
                assert "no key found" in message.lower()

        def test_retrieve_key_fallback_corrupted_json(self, manager):
            """Test retrieving key when fallback file has corrupted JSON."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                # Create corrupted JSON file
                fallback_path = manager.fallback_path
                with open(fallback_path, "w") as f:
                    f.write("{invalid json")

                key, message = manager.retrieve_key()

                assert key is None
                assert "no encryption key found" in message.lower()

        def test_get_storage_info_fallback_corrupted_json(self, manager):
            """Test get_storage_info when fallback file has corrupted JSON."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                # Create corrupted JSON file
                fallback_path = manager.fallback_path
                with open(fallback_path, "w") as f:
                    f.write("{invalid json")

                info = manager.get_storage_info()

                assert info["fallback_exists"] is True
                assert info["key_exists"] is False
                # File exists but is corrupted, so active_storage is "fallback" (file exists)
                assert info["active_storage"] == "fallback"

        def test_get_storage_info_fallback_no_file(self, manager):
            """Test get_storage_info when fallback file doesn't exist."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                info = manager.get_storage_info()

                assert info["fallback_exists"] is False
                assert info["key_exists"] is False
                assert info["active_storage"] == "none"

    class TestErrorHandling:
        """Tests for error handling and exception paths."""

        @pytest.mark.parametrize(
            "test_name, setup_func, method_to_patch, expect_key_none",
            [
                ("store_key", lambda m, k: m.store_key(k), "_save_fallback", False),
                ("retrieve_key", lambda m, k: m.retrieve_key(), "_load_fallback", True),
                ("delete_key", lambda m, k: m.delete_key(), "_delete_fallback", False),
            ],
        )
        def test_outer_exception(self, manager, mock_keyring, test_name, setup_func, method_to_patch, expect_key_none):
            """Test when outer try block raises exception."""
            # Mock keyring to fail so fallback is called
            mock_keyring.get_password.side_effect = Exception("Keyring error")
            mock_keyring.set_password.side_effect = Exception("Keyring error")
            mock_keyring.delete_password.side_effect = Exception("Keyring error")

            # Mock _save_fallback, _load_fallback, or _delete_fallback to raise exception
            with patch.object(manager, method_to_patch, side_effect=Exception("Outer error")):
                result, message = setup_func(manager, TEST_KEY)

                if expect_key_none:
                    # For retrieve_key, result is the key (should be None)
                    assert result is None
                else:
                    # For store_key and delete_key, result is success (should be False)
                    assert result is False
                assert "error" in message.lower()

        def test_store_key_fallback_failure(self, manager):
            """Test storing key when fallback save fails."""
            # Mock _save_fallback to fail
            with (
                patch("utilities.keyring_manager.KEYRING_AVAILABLE", False),
                patch.object(manager, "_save_fallback", return_value=False),
            ):
                success, message = manager.store_key(TEST_KEY)

                assert success is False
                assert "failed" in message.lower()

        def test_store_key_keyring_failure_fallback_success(self, manager, mock_keyring):
            """Test storing key when keyring fails but fallback succeeds."""
            setup_keyring_mock(mock_keyring, should_fail=True)

            success, message = manager.store_key(TEST_KEY)

            assert success is True
            assert "fallback" in message.lower()

        def test_retrieve_key_keyring_failure_fallback_success(self, manager, mock_keyring):
            """Test retrieving key when keyring fails but fallback succeeds."""
            # Store key in fallback first
            setup_fallback_key(manager)

            # Mock keyring to fail
            setup_keyring_mock(mock_keyring, should_fail=True)

            key, message = manager.retrieve_key()

            assert key == TEST_KEY
            assert "fallback" in message.lower()

        def test_delete_key_keyring_failure_fallback_success(self, manager, mock_keyring):
            """Test deleting key when keyring fails but fallback succeeds."""
            # Store key in fallback first
            setup_fallback_key(manager)

            # Mock keyring to fail
            setup_keyring_mock(mock_keyring, should_fail=True)

            success, message = manager.delete_key()

            assert success is True
            assert "fallback" in message.lower()

        def test_delete_key_both_fail(self, manager, mock_keyring):
            """Test deleting key when both keyring and fallback fail."""
            # Store key in fallback first
            setup_fallback_key(manager)

            # Mock keyring to fail
            setup_keyring_mock(mock_keyring, should_fail=True)

            # Mock fallback to fail
            with patch.object(manager, "_delete_fallback", return_value=False):
                success, message = manager.delete_key()

                assert success is False
                assert "no key found" in message.lower()

        def test_key_exists_keyring_exception(self, manager, mock_keyring):
            """Test key_exists when keyring raises exception."""
            setup_keyring_mock(mock_keyring, should_fail=True)

            # Should fall back to checking file
            assert manager.key_exists() is False

        def test_key_exists_keyring_exception_with_fallback_key(self, manager, mock_keyring):
            """Test key_exists when keyring raises exception but fallback has key."""
            # Store key in fallback
            setup_fallback_key(manager)

            # Mock keyring to raise exception
            setup_keyring_mock(mock_keyring, should_fail=True)

            # Should fall back to checking file
            assert manager.key_exists() is True

        def test_get_storage_info_keyring_exception(self, manager, mock_keyring):
            """Test get_storage_info when keyring raises exception."""
            setup_keyring_mock(mock_keyring, should_fail=True)

            info = manager.get_storage_info()

            assert info["active_storage"] == "none"

        def test_get_storage_info_keyring_exception_with_fallback(self, manager, mock_keyring):
            """Test get_storage_info when keyring raises exception but fallback exists."""
            # Store key in fallback
            setup_fallback_key(manager)

            # Mock keyring to raise exception
            setup_keyring_mock(mock_keyring, should_fail=True)

            info = manager.get_storage_info()

            assert info["active_storage"] == "fallback"

        def test_save_fallback_exception(self, manager):
            """Test _save_fallback when exception occurs."""
            # Mock os.replace to raise exception
            with (
                patch("utilities.keyring_manager.KEYRING_AVAILABLE", False),
                patch("utilities.keyring_manager.os.replace", side_effect=Exception("OS error")),
            ):
                success = manager._save_fallback("test_key")

                assert success is False

        def test_delete_fallback_exception(self, manager):
            """Test _delete_fallback when exception occurs."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                # Create fallback file
                fallback_path = manager.fallback_path
                with open(fallback_path, "w") as f:
                    json.dump({"salt": "test_key"}, f)

                # Mock json.load to raise exception
                with patch("utilities.keyring_manager.json.load", side_effect=Exception("JSON error")):
                    success = manager._delete_fallback()

                    assert success is False

        def test_ensure_config_dir_exception(self):
            """Test _ensure_config_dir when exception occurs."""
            with patch("utilities.keyring_manager.os.makedirs", side_effect=Exception("OS error")):
                manager = KeyringManager("/invalid/path")
                # Should not raise exception, just log error
                assert manager.config_path == os.path.normpath("/invalid/path")

        def test_load_fallback_generic_exception(self, manager):
            """Test _load_fallback when generic exception occurs."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                # Create fallback file
                fallback_path = manager.fallback_path
                with open(fallback_path, "w") as f:
                    json.dump({"salt": TEST_KEY}, f)

                # Mock json.load to raise generic exception
                with patch("utilities.keyring_manager.json.load", side_effect=Exception("Generic error")):
                    key = manager._load_fallback()

                    assert key is None

        def test_load_fallback_json_decode_error(self, manager):
            """Test _load_fallback when JSON decode error occurs."""
            with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
                # Create corrupted JSON file
                fallback_path = manager.fallback_path
                with open(fallback_path, "w") as f:
                    f.write("{invalid json")

                key = manager._load_fallback()

                assert key is None

        def test_retrieve_key_keyring_exception(self, manager, mock_keyring):
            """Test retrieve_key when keyring raises exception."""
            setup_keyring_mock(mock_keyring, should_fail=True)

            key, message = manager.retrieve_key()

            assert key is None
            assert "no encryption key found" in message.lower()

        def test_delete_key_keyring_exception(self, manager, mock_keyring):
            """Test delete_key when keyring raises exception."""
            setup_keyring_mock(mock_keyring, should_fail=True)

            success, message = manager.delete_key()

            # When keyring fails but fallback succeeds (even if no key exists), success is True
            assert success is True
            # When fallback file doesn't exist, _delete_fallback returns True
            assert "deleted from fallback storage" in message.lower()

        def test_get_storage_info_keyring_exception_no_fallback(self, manager, mock_keyring):
            """Test get_storage_info when keyring raises exception and no fallback."""
            setup_keyring_mock(mock_keyring, should_fail=True)

            info = manager.get_storage_info()

            assert info["active_storage"] == "none"


# Test KeyringMigration
class TestKeyringMigration:
    """Test cases for KeyringMigration class."""

    def test_detect_old_format_true(self, temp_dir, manager, old_config):
        """Test detecting old format with salt key."""
        migration = KeyringMigration(temp_dir, manager)
        assert migration.detect_old_format(old_config) is True

    def test_detect_old_format_false(self, temp_dir, manager, new_config):
        """Test detecting new format without salt key."""
        migration = KeyringMigration(temp_dir, manager)
        assert migration.detect_old_format(new_config) is False

    def test_migrate_from_old_format_success(self, temp_dir, manager, old_config):
        """Test successful migration from old format to new format (fallback - salt kept)."""
        with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
            migration = KeyringMigration(temp_dir, manager)

            success, new_config, message, key = migration.migrate_from_old_format(old_config)

            assert success is True
            assert "salt" in new_config  # Salt kept in fallback
            assert "xl_pass" in new_config
            assert new_config["theme"] == TEST_THEME
            assert new_config["custom_path"] == TEST_PATH
            assert "migration" in message.lower()
            assert key == TEST_SALT

    def test_migrate_from_old_format_success_with_keyring(self, temp_dir, manager, old_config, mock_keyring):
        """Test successful migration from old format to new format (keyring - salt removed)."""
        migration = KeyringMigration(temp_dir, manager)

        success, new_config, message, key = migration.migrate_from_old_format(old_config)

        assert success is True
        assert "salt" not in new_config  # Salt removed when keyring works
        assert "xl_pass" in new_config
        assert new_config["theme"] == TEST_THEME
        assert new_config["custom_path"] == TEST_PATH
        assert "migration" in message.lower()
        assert "keyring" in message.lower()
        assert key == TEST_SALT
        mock_keyring.set_password.assert_called_once_with("blocknet_aio", "encryption_key", TEST_SALT)

    def test_migrate_from_old_format_no_salt(self, temp_dir, manager, new_config):
        """Test migration when config already in new format."""
        migration = KeyringMigration(temp_dir, manager)

        success, result_config, message, key = migration.migrate_from_old_format(new_config)

        assert success is True
        assert result_config == new_config
        assert "already" in message.lower()
        assert key is None

    def test_migrate_config_file_success(self, temp_dir, manager):
        """Test successful migration of config file (fallback - salt kept)."""
        with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
            migration = KeyringMigration(temp_dir, manager)

            # Create old format config file
            config_file = os.path.join(temp_dir, "aio_settings.json")
            old_config = {"theme": TEST_THEME, "salt": TEST_SALT, "xl_pass": TEST_PASSWORD}

            with open(config_file, "w") as f:
                json.dump(old_config, f)

            # Migrate
            success, message = migration.migrate_config_file(config_file)

            assert success is True
            assert "success" in message.lower()

            # Verify config file was updated (salt kept in fallback)
            with open(config_file) as f:
                new_config = json.load(f)
                assert "salt" in new_config  # Salt kept in fallback
                assert "xl_pass" in new_config
                assert new_config["theme"] == TEST_THEME

    def test_migrate_config_file_already_migrated(self, temp_dir, manager, new_config):
        """Test migration when config file is already in new format."""
        migration = KeyringMigration(temp_dir, manager)

        # Create new format config file
        config_file = os.path.join(temp_dir, "aio_settings.json")
        with open(config_file, "w") as f:
            json.dump(new_config, f)

        # Migrate
        success, message = migration.migrate_config_file(config_file)

        assert success is True
        assert "already" in message.lower()

    def test_migrate_config_file_not_found(self, temp_dir, manager):
        """Test migration when config file doesn't exist."""
        migration = KeyringMigration(temp_dir, manager)

        config_file = os.path.join(temp_dir, "nonexistent.json")

        success, message = migration.migrate_config_file(config_file)

        assert success is False
        assert "error" in message.lower()

    def test_migrate_from_old_format_exception(self, temp_dir, manager, old_config):
        """Test migrate_from_old_format when exception occurs."""
        with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
            migration = KeyringMigration(temp_dir, manager)

            # Mock store_key to raise exception
            with patch.object(manager, "store_key", side_effect=Exception("Store error")):
                success, new_config, message, key = migration.migrate_from_old_format(old_config)

                assert success is False
                assert "error" in message.lower()

    def test_migrate_config_file_exception(self, temp_dir, manager):
        """Test migrate_config_file when exception occurs."""
        with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
            migration = KeyringMigration(temp_dir, manager)

            config_file = os.path.join(temp_dir, "aio_settings.json")

            # Create config file
            with open(config_file, "w") as f:
                json.dump({"theme": TEST_THEME}, f)

            # Mock json.load to raise exception
            with patch("utilities.keyring_manager.json.load", side_effect=Exception("JSON error")):
                success, message = migration.migrate_config_file(config_file)

                assert success is False
                assert "error" in message.lower()

    def test_migrate_config_file_write_exception(self, temp_dir, manager):
        """Test migrate_config_file when write fails."""
        with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
            migration = KeyringMigration(temp_dir, manager)

            config_file = os.path.join(temp_dir, "aio_settings.json")

            # Create old format config file
            old_config = {"theme": TEST_THEME, "salt": TEST_SALT, "xl_pass": TEST_PASSWORD}

            with open(config_file, "w") as f:
                json.dump(old_config, f)

            # Mock open to raise exception on write (robust to UP015 open without mode)
            original_open = open

            def mock_open_side_effect(*args, **kwargs):
                mode = args[1] if len(args) > 1 else kwargs.get("mode", "r")
                if "w" in mode:
                    raise Exception("Write error")
                return original_open(*args, **kwargs)

            with patch("builtins.open", side_effect=mock_open_side_effect):
                success, message = migration.migrate_config_file(config_file)

                assert success is False
                assert "migration failed" in message.lower()

    def test_migrate_from_old_format_outer_exception(self, temp_dir, manager, old_config):
        """Test migrate_from_old_format when outer try block raises exception."""
        with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
            migration = KeyringMigration(temp_dir, manager)

            # Mock detect_old_format to raise exception
            with patch.object(migration, "detect_old_format", side_effect=Exception("Detect error")):
                success, new_config, message, key = migration.migrate_from_old_format(old_config)

                assert success is False
                assert "error" in message.lower()

    def test_migrate_config_file_outer_exception(self, temp_dir, manager):
        """Test migrate_config_file when outer try block raises exception."""
        with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
            migration = KeyringMigration(temp_dir, manager)

            config_file = os.path.join(temp_dir, "aio_settings.json")

            # Mock json.load to raise exception
            with patch("utilities.keyring_manager.json.load", side_effect=Exception("JSON error")):
                success, message = migration.migrate_config_file(config_file)

                assert success is False
                assert "error" in message.lower()


# Integration Tests
class TestKeyringIntegration:
    """Integration tests for keyring functionality."""

    def test_full_workflow_fallback(self, temp_dir):
        """Test complete workflow using fallback storage."""
        manager = KeyringManager(temp_dir)

        # Store key
        with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
            success, message = manager.store_key(TEST_KEY)
            assert success is True

            # Verify key exists
            assert manager.key_exists() is True

            # Retrieve key
            key, message = manager.retrieve_key()
            # The key should be returned as the original plaintext
            assert key == TEST_KEY

            # Get storage info
            info = manager.get_storage_info()
            assert info["active_storage"] == "fallback"

            # Delete key
            success, message = manager.delete_key()
            assert success is True

            # Verify key no longer exists
            assert manager.key_exists() is False

    def test_migration_workflow(self, temp_dir):
        """Test complete migration workflow (fallback - salt kept)."""
        keyring_manager = KeyringManager(temp_dir)
        migration = KeyringMigration(temp_dir, keyring_manager)

        # Create old format config
        config_file = os.path.join(temp_dir, "aio_settings.json")
        old_config = {
            "theme": TEST_THEME,
            "custom_path": TEST_PATH,
            "salt": "old_encryption_key",
            "xl_pass": TEST_PASSWORD,
        }

        with open(config_file, "w") as f:
            json.dump(old_config, f)

        # Migrate
        with patch("utilities.keyring_manager.KEYRING_AVAILABLE", False):
            success, message = migration.migrate_config_file(config_file)
            assert success is True

            # Verify migration results (salt kept in fallback)
            with open(config_file) as f:
                new_config = json.load(f)
                assert "salt" in new_config  # Salt kept in fallback
                assert "xl_pass" in new_config
                assert new_config["theme"] == TEST_THEME
                assert new_config["custom_path"] == TEST_PATH

            # Verify key is in keyring/fallback
            key, _ = keyring_manager.retrieve_key()
            assert key == "old_encryption_key"
