import copy
import logging
import platform
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from utilities.config_manager import ConfigManager, SYSTEM_SPECIFIC_KEYS

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class BaseConfigTest(unittest.TestCase):
    """Base class for common testing setup"""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.test_dir.cleanup)
        self.test_dir_path = Path(self.test_dir.name)

    def set_mock_platform(self, system_value, machine_value):
        return patch.multiple(platform,
                              system=lambda: system_value,
                              machine=lambda: machine_value
                              )

    def create_config_for_platform(self, system, machine):
        with self.set_mock_platform(system, machine), patch.object(ConfigManager, '_get_aio_path',
                                                                   return_value=self.test_dir_path):
            return ConfigManager()

    def run(self, result=None):
        """Override run to log test start and end."""
        logging.info("===== Starting test: %s =====", self.id())
        test_result = super().run(result)
        logging.info("===== Completed test: %s =====", self.id())
        return test_result


class TestConfigManagerOSHandling(BaseConfigTest):
    """Test OS-specific configuration handling"""

    def test_template_initialization(self):
        """Test initial config matches template"""
        cfg = self.create_config_for_platform('Windows', 'AMD64')
        for key in cfg.config_template:
            if key in SYSTEM_SPECIFIC_KEYS:
                self.assertIsNotNone(cfg._get_system_value(key))
            else:
                self.assertEqual(cfg.config[key], cfg.config_template[key])

    def _test_os_specific_values_correctly_set(self, system, machine, tests):
        """Helper for OS-specific value validation"""
        cfg = self.create_config_for_platform(system, machine)
        cfg._save_config()

        # Check in-memory values                                                                                                                                                         
        for key, expected in tests.items():
            self.assertEqual(cfg._get_system_value(key), expected,
                             f"Failed for {key} on {system}")

            # Validate saved YAML values
        with open(self.test_dir_path / "aio_config.yaml") as f:
            config_data = yaml.safe_load(f)
            for key, expected in tests.items():
                self.assertEqual(config_data[key], expected,
                                 f"YAML mismatch for {key} on {system}")

    def test_windows_values(self):
        """Verify Windows-specific values"""
        self._test_os_specific_values_correctly_set(
            'Windows', 'AMD64',
            {
                'blocknet_bin_name': 'blocknet-qt.exe',
                'xlite_launch_options': ['--in-process-gpu'],
                'blocknet_default_paths': '%appdata%\\Blocknet'
            }
        )

    def test_linux_values(self):
        """Verify Linux-specific values"""
        self._test_os_specific_values_correctly_set(
            'Linux', 'x86_64',
            {
                'blocknet_bin_name': 'blocknet-qt',
                'xlite_launch_options': [],
                'blockdx_bin_name': 'block-dx'
            }
        )

    def test_darwin_values(self):
        """Verify macOS-specific values"""
        self._test_os_specific_values_correctly_set(
            'Darwin', 'x86_64',
            {
                'blocknet_releases_urls': 'https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-osx64.tar.gz',
                'blocknet_bin_name': 'blocknet-qt',
                'xlite_daemon_bin_name': 'xlite-daemon-osx64'
            }
        )

    def test_all_system_specific_keys_are_validated(self):
        """Verify all SYSTEM_SPECIFIC_KEYS have OS-specific values"""
        cfg = self.create_config_for_platform('Linux', 'x86_64')
        for key in SYSTEM_SPECIFIC_KEYS:
            self.assertIsNotNone(
                cfg._get_system_value(key),
                f"System key {key} failed validation"
            )


class TestConfigPersistence(BaseConfigTest):
    """Test configuration saving and loading"""

    def test_non_system_key_persistence(self):
        """Test persistence of non-system-specific keys"""
        # Save config with modifications                                                                                                                                                 
        cfg = self.create_config_for_platform('Linux', 'x86_64')
        cfg.config['blocknet_bootstrap_url'] = 'https://new.url/bootstrap.zip'
        cfg.config['extra_option_blocknet_core_conf'] = [{'new_key': 'value'}]
        cfg._save_config()

        # Reload config                                                                                                                                                                  
        new_cfg = self.create_config_for_platform('Linux', 'x86_64')
        self.assertEqual(new_cfg.config['blocknet_bootstrap_url'],
                         'https://new.url/bootstrap.zip')
        self.assertEqual(new_cfg.config['extra_option_blocknet_core_conf'],
                         [{'new_key': 'value'}])

    def test_system_key_persistence(self):
        """Test persistence of system-specific keys"""
        # Save config                                                                                                                                                                    
        cfg = self.create_config_for_platform('Darwin', 'x86_64')
        original_xlite_path = cfg._get_system_value('xlite_bin_path')
        cfg._save_config()

        # Modify and reload (should retain OS-specific template values)                                                                                                                  
        cfg.config['xlite_bin_path'] = 'new_path'
        new_cfg = self.create_config_for_platform('Darwin', 'x86_64')
        self.assertEqual(new_cfg._get_system_value('xlite_bin_path'),
                         original_xlite_path)

    def test_config_updates(self):
        """Test updating and reloading config"""
        cfg = self.create_config_for_platform('Windows', 'AMD64')
        cfg.config['nodes_to_add'] = ['127.0.0.1:41412']
        cfg._save_config()

        new_cfg = self.create_config_for_platform('Windows', 'AMD64')
        self.assertIn('127.0.0.1:41412', new_cfg.config['nodes_to_add'])

        # Verify template values retained
        self.assertEqual(
            new_cfg._get_system_value('xlite_launch_options'),
            ['--in-process-gpu']
        )

    def test_empty_config_uses_template(self):
        """Test initialization with empty config file"""
        # Create empty config file                                                                                                                                                       
        config_file = self.test_dir_path / "aio_config.yaml"
        with open(config_file, "w") as f:
            f.write("")

        cfg = self.create_config_for_platform('Linux', 'x86_64')
        self.assertIsNotNone(cfg._get_system_value('blocknet_releases_urls'))
        self.assertEqual(cfg.config['blocknet_bootstrap_url'],
                         "https://utils.blocknet.org/Blocknet.zip")


class TestConfigOperations(BaseConfigTest):
    """Test config manipulation methods"""

    def test_deep_merge(self):
        cfg = self.create_config_for_platform('Windows', 'AMD64')
        base = {'key1': 'value', 'nested': {'a': 1, 'b': 2}}
        update = {'key2': 'new', 'nested': {'b': 3, 'c': 4}}
        result = cfg._deep_merge(copy.deepcopy(base), update)

        self.assertEqual(result, {
            'key1': 'value',
            'key2': 'new',
            'nested': {'a': 1, 'b': 3, 'c': 4}
        })

    def test_set_system_value(self):
        cfg = self.create_config_for_platform('Linux', 'x86_64')
        cfg._set_system_value('blocknet_bin_name', 'new_binary_name')
        self.assertEqual(cfg._get_system_value('blocknet_bin_name'), 'new_binary_name')

        # Verify template structures preserved                                                                                                                                           
        self.assertIsInstance(cfg.config['blocknet_bin_name'], dict)

    def test_missing_keys_use_defaults(self):
        """Test keys missing from config file use template defaults"""
        with open(self.test_dir_path / "aio_config.yaml", "w") as f:
            yaml.dump({'blocknet_bootstrap_url': 'custom-value'}, f)

        cfg = self.create_config_for_platform('Darwin', 'x86_64')
        self.assertEqual(cfg.config['blocknet_bootstrap_url'], 'custom-value')
        self.assertIsNotNone(cfg._get_system_value('xlite_releases_urls'))
        self.assertEqual(
            cfg.config['base_xbridge_conf']['FullLog'],
            'true'
        )


class TestStructureValidation(BaseConfigTest):
    """Test configuration structure validation"""

    def test_saved_config_has_flat_system_keys(self):
        cfg = self.create_config_for_platform('Windows', 'AMD64')
        cfg._save_config()

        with open(self.test_dir_path / "aio_config.yaml") as f:
            config_data = yaml.safe_load(f)

            # Verify system-specific keys are flattened                                                                                                                                  
            for key in SYSTEM_SPECIFIC_KEYS:
                self.assertIn(key, config_data)
                self.assertNotIsInstance(config_data[key], dict,
                                         f"System key {key} should be flattened")

                # Verify flat value matches OS-specific value                                                                                                                            
                self.assertEqual(
                    config_data[key],
                    cfg._get_system_value(key)
                )


if __name__ == '__main__':
    unittest.main()
