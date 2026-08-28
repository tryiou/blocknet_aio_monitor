import copy
import logging
import os
import platform
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import yaml

from utilities.config_manager import SYSTEM_SPECIFIC_KEYS, ConfigManager

logger = logging.getLogger(__name__)


class ConfigManagerTestCase(unittest.TestCase):
    """Base test case with common configuration setup utilities"""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.test_dir.cleanup)
        self.test_dir_path = Path(self.test_dir.name)

    def _create_config_for_platform(self, system: str, machine: str) -> ConfigManager:
        """Create a ConfigManager instance for a specific platform"""
        with (
            patch.multiple(platform, system=lambda: system, machine=lambda: machine),
            patch.object(ConfigManager, "_get_aio_path", return_value=self.test_dir_path),
        ):
            return ConfigManager()

    def _assert_system_value(self, config: ConfigManager, key: str, expected, system: str):
        """Assert that a system-specific key has the expected value"""
        actual = config._get_system_value(key)
        self.assertEqual(actual, expected, f"Failed for {key} on {system}")

    def _assert_yaml_value(self, key: str, expected, system: str):
        """Assert that a key in the saved YAML file has the expected value"""
        with open(self.test_dir_path / "aio_config.yaml") as f:
            config_data = yaml.safe_load(f)
            self.assertEqual(config_data[key], expected, f"YAML mismatch for {key} on {system}")

    def run(self, result=None):
        """Override run to log test start and end."""
        logger.info("===== Starting test: %s =====", self.id())
        test_result = super().run(result)
        logger.info("===== Completed test: %s =====", self.id())
        return test_result


class TestOSHandling(ConfigManagerTestCase):
    """Test OS-specific configuration handling"""

    def test_template_initialization(self):
        """Test initial config matches template"""
        cfg = self._create_config_for_platform("Windows", "AMD64")
        for key in cfg.config_template:
            if key in SYSTEM_SPECIFIC_KEYS:
                self.assertIsNotNone(cfg._get_system_value(key))
            else:
                self.assertEqual(cfg.config[key], cfg.config_template[key])

    def test_windows_values(self):
        """Verify Windows-specific values"""
        cfg = self._create_config_for_platform("Windows", "AMD64")
        cfg._save_config()

        expected = {
            "blocknet_bin_name": "blocknet-qt.exe",
            "xlite_launch_options": ["--in-process-gpu"],
            "blocknet_default_paths": "%appdata%\\Blocknet",
        }

        for key, value in expected.items():
            self._assert_system_value(cfg, key, value, "Windows")
            self._assert_yaml_value(key, value, "Windows")

    def test_linux_values(self):
        """Verify Linux-specific values"""
        cfg = self._create_config_for_platform("Linux", "x86_64")
        cfg._save_config()

        expected = {"blocknet_bin_name": "blocknet-qt", "xlite_launch_options": [], "blockdx_bin_name": "block-dx"}

        for key, value in expected.items():
            self._assert_system_value(cfg, key, value, "Linux")
            self._assert_yaml_value(key, value, "Linux")

    def test_darwin_values(self):
        """Verify macOS-specific values"""
        cfg = self._create_config_for_platform("Darwin", "x86_64")
        cfg._save_config()

        expected = {
            "blocknet_releases_urls": "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-osx64.tar.gz",
            "blocknet_bin_name": "blocknet-qt",
            "xlite_daemon_bin_name": "xlite-daemon-osx64",
        }

        for key, value in expected.items():
            self._assert_system_value(cfg, key, value, "Darwin")
            self._assert_yaml_value(key, value, "Darwin")

    def test_all_system_specific_keys_are_validated(self):
        """Verify all SYSTEM_SPECIFIC_KEYS have OS-specific values"""
        cfg = self._create_config_for_platform("Linux", "x86_64")
        for key in SYSTEM_SPECIFIC_KEYS:
            self.assertIsNotNone(cfg._get_system_value(key), f"System key {key} failed validation")


class TestPersistence(ConfigManagerTestCase):
    """Test configuration saving and loading"""

    def test_non_system_key_persistence(self):
        """Test persistence of non-system-specific keys"""
        cfg = self._create_config_for_platform("Linux", "x86_64")
        cfg.config["blocknet_bootstrap_url"] = "https://new.url/bootstrap.zip"
        cfg.config["extra_option_blocknet_core_conf"] = [{"new_key": "value"}]
        cfg._save_config()

        new_cfg = self._create_config_for_platform("Linux", "x86_64")
        self.assertEqual(new_cfg.config["blocknet_bootstrap_url"], "https://new.url/bootstrap.zip")
        self.assertEqual(new_cfg.config["extra_option_blocknet_core_conf"], [{"new_key": "value"}])

    def test_system_key_persistence(self):
        """Test persistence of system-specific keys"""
        cfg = self._create_config_for_platform("Darwin", "x86_64")
        original_xlite_path = cfg._get_system_value("xlite_bin_path")
        cfg._save_config()

        # Modify and reload (should retain OS-specific template values)
        cfg.config["xlite_bin_path"] = "new_path"
        new_cfg = self._create_config_for_platform("Darwin", "x86_64")
        self.assertEqual(new_cfg._get_system_value("xlite_bin_path"), original_xlite_path)

    def test_config_updates(self):
        """Test updating and reloading config"""
        cfg = self._create_config_for_platform("Windows", "AMD64")
        cfg.config["nodes_to_add"] = ["127.0.0.1:41412"]
        cfg._save_config()

        new_cfg = self._create_config_for_platform("Windows", "AMD64")
        self.assertIn("127.0.0.1:41412", new_cfg.config["nodes_to_add"])
        self.assertEqual(new_cfg._get_system_value("xlite_launch_options"), ["--in-process-gpu"])

    def test_empty_config_uses_template(self):
        """Test initialization with empty config file"""
        config_file = self.test_dir_path / "aio_config.yaml"
        with open(config_file, "w") as f:
            f.write("")

        cfg = self._create_config_for_platform("Linux", "x86_64")
        self.assertIsNotNone(cfg._get_system_value("blocknet_releases_urls"))
        self.assertEqual(cfg.config["blocknet_bootstrap_url"], "https://utils.blocknet.org/Blocknet.zip")


class TestOperations(ConfigManagerTestCase):
    """Test config manipulation methods"""

    def test_deep_merge(self):
        cfg = self._create_config_for_platform("Windows", "AMD64")
        base = {"key1": "value", "nested": {"a": 1, "b": 2}}
        update = {"key2": "new", "nested": {"b": 3, "c": 4}}
        result = cfg._deep_merge(copy.deepcopy(base), update)

        self.assertEqual(result, {"key1": "value", "key2": "new", "nested": {"a": 1, "b": 3, "c": 4}})

    def test_set_system_value(self):
        cfg = self._create_config_for_platform("Linux", "x86_64")
        cfg._set_system_value("blocknet_bin_name", "new_binary_name")
        self.assertEqual(cfg._get_system_value("blocknet_bin_name"), "new_binary_name")
        self.assertIsInstance(cfg.config["blocknet_bin_name"], dict)

    def test_missing_keys_use_defaults(self):
        """Test keys missing from config file use template defaults"""
        with open(self.test_dir_path / "aio_config.yaml", "w") as f:
            yaml.dump({"blocknet_bootstrap_url": "custom-value"}, f)

        cfg = self._create_config_for_platform("Darwin", "x86_64")
        self.assertEqual(cfg.config["blocknet_bootstrap_url"], "custom-value")
        self.assertIsNotNone(cfg._get_system_value("xlite_releases_urls"))
        self.assertEqual(cfg.config["base_xbridge_conf"]["FullLog"], "true")


class TestStructureValidation(ConfigManagerTestCase):
    """Test configuration structure validation"""

    def test_saved_config_has_flat_system_keys(self):
        cfg = self._create_config_for_platform("Windows", "AMD64")
        cfg._save_config()

        with open(self.test_dir_path / "aio_config.yaml") as f:
            config_data = yaml.safe_load(f)

            for key in SYSTEM_SPECIFIC_KEYS:
                self.assertIn(key, config_data)
                self.assertNotIsInstance(config_data[key], dict, f"System key {key} should be flattened")
                self.assertEqual(config_data[key], cfg._get_system_value(key))


class TestEdgeCases(ConfigManagerTestCase):
    """Test edge cases and error conditions"""

    def test_get_system_value_returns_none_for_missing_key(self):
        """Test _get_system_value returns None when key not found in dict"""
        cfg = self._create_config_for_platform("Linux", "x86_64")
        # Create a dict with a key that doesn't exist for current system
        cfg.config["test_key"] = {("Windows", "AMD64"): "windows_value"}
        result = cfg._get_system_value("test_key")
        self.assertIsNone(result)

    def test_get_aio_path_creates_directory(self):
        """Test _get_aio_path creates directory if it doesn't exist"""
        # Create a fresh ConfigManager without mocking _get_aio_path
        with patch.multiple(platform, system=lambda: "Linux", machine=lambda: "x86_64"):
            cfg = ConfigManager()
            # _get_aio_path is called during initialization
            # Verify the directory was created
            self.assertTrue(cfg.aio_folder.exists())
            self.assertTrue(cfg.aio_folder.is_dir())

    def test_set_system_value_for_non_system_key(self):
        """Test _set_system_value works for non-system-specific keys"""
        cfg = self._create_config_for_platform("Linux", "x86_64")
        cfg._set_system_value("blocknet_bootstrap_url", "custom_url")
        self.assertEqual(cfg.config["blocknet_bootstrap_url"], "custom_url")

    def test_set_system_value_with_non_dict_config(self):
        """Test _set_system_value when config key is not a dict"""
        cfg = self._create_config_for_platform("Linux", "x86_64")
        # blocknet_bin_path is a list in template
        cfg._set_system_value("blocknet_bin_path", ["custom", "path"])
        self.assertEqual(cfg.config["blocknet_bin_path"], ["custom", "path"])

    def test_set_system_value_with_new_system_key(self):
        """Test _set_system_value when system key doesn't exist in dict"""
        cfg = self._create_config_for_platform("Linux", "x86_64")
        # Create a SYSTEM_SPECIFIC_KEY dict without current system key
        cfg.config["xlite_daemon_bin_name"] = {("Windows", "AMD64"): "xlite-daemon-win64.exe"}
        # Set value for current system (should add new key)
        cfg._set_system_value("xlite_daemon_bin_name", "xlite-daemon-linux64")
        self.assertEqual(
            cfg.config["xlite_daemon_bin_name"],
            {("Windows", "AMD64"): "xlite-daemon-win64.exe", ("Linux", "x86_64"): "xlite-daemon-linux64"},
        )

    def test_atomic_yaml_0600_and_0700(self):
        """Test _save_config atomic write uses 0o600 and dir 0o700."""
        cfg = self._create_config_for_platform("Linux", "x86_64")
        cfg._save_config()
        config_file = self.test_dir_path / "aio_config.yaml"
        self.assertTrue(config_file.exists())
        if os.name != "nt":
            self.assertEqual(oct(config_file.stat().st_mode & 0o777), oct(0o600))
            self.assertEqual(oct(self.test_dir_path.stat().st_mode & 0o777), oct(0o700))
        # No tmp file left behind
        self.assertEqual(list(self.test_dir_path.glob("*.tmp.*")), [])

    def test_corrupted_yaml_self_heal(self):
        """Corrupted aio_config.yaml is backed up and self-heals."""
        config_file = self.test_dir_path / "aio_config.yaml"
        config_file.write_text("{invalid: yaml: : [", encoding="utf-8")
        cfg = self._create_config_for_platform("Linux", "x86_64")
        # Should self-heal to template, not crash
        self.assertIsNotNone(cfg._get_system_value("blocknet_releases_urls"))
        backups = list(self.test_dir_path.glob("aio_config.yaml.corrupt.*"))
        self.assertEqual(len(backups), 1)


if __name__ == "__main__":
    unittest.main()
