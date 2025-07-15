import unittest
import os
import tempfile
import platform
import yaml
from unittest.mock import patch
from pathlib import Path
from utilities.config_manager import ConfigManager, SYSTEM_SPECIFIC_KEYS
import copy

class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.test_dir.cleanup)
        self.test_dir_path = Path(self.test_dir.name)
        
    def set_mock_platform(self, system_value, machine_value):
        return patch.multiple(platform,
            system=lambda: system_value,
            machine=lambda: machine_value
        )

    def test_basic_save_and_load(self):
        """Test basic save and load functionality"""
        with patch.object(ConfigManager, '_get_aio_path', return_value=self.test_dir_path):
            # Save initial config
            cfg_save = ConfigManager()
            cfg_save._save_config()
            
            # Load config
            cfg_load = ConfigManager()
            
            # Verify non-system-specific keys match
            for key in cfg_save.config_template:
                if key not in SYSTEM_SPECIFIC_KEYS:
                    self.assertEqual(cfg_save.config[key], cfg_load.config[key])
            
            # Verify system-specific keys
            for key in SYSTEM_SPECIFIC_KEYS:
                # Both should have same structure: either dict or base type
                self.assertEqual(type(cfg_save.config[key]), type(cfg_load.config[key]))
                
                # Verify the value for current system matches
                self.assertEqual(
                    cfg_save._get_system_value(key),
                    cfg_load._get_system_value(key)
                )

    def test_system_specific_values_windows(self):
        """Test Windows-specific values"""
        with self.set_mock_platform('Windows', 'AMD64'), \
             patch.object(ConfigManager, '_get_aio_path', return_value=self.test_dir_path):
            # Save config
            cfg = ConfigManager()
            cfg._save_config()
            
            # Get specific values to verify
            bin_name = cfg._get_system_value('blocknet_bin_name')
            launch_opts = cfg._get_system_value('xlite_launch_options')
            paths = cfg._get_system_value('blocknet_default_paths')
            releases = cfg._get_system_value('blocknet_releases_urls')
            bin_path = cfg._get_system_value('blocknet_bin_path')
            
            self.assertEqual(bin_name, 'blocknet-qt.exe')
            self.assertEqual(launch_opts, ['--in-process-gpu'])
            self.assertEqual(paths, '%appdata%\\Blocknet')
            self.assertTrue('win64.zip' in releases)
            self.assertEqual(bin_path, ['blocknet-4.4.1', 'bin'])
            
            # Check file content
            config_file = self.test_dir_path / "aio_config.yaml"
            with open(config_file) as f:
                config_data = yaml.safe_load(f)
                
            self.assertEqual(config_data['blocknet_bin_name'], 'blocknet-qt.exe')
            self.assertEqual(config_data['xlite_launch_options'], ['--in-process-gpu'])
            self.assertEqual(config_data['blocknet_default_paths'], '%appdata%\\Blocknet')
            self.assertTrue('win64.zip' in config_data['blocknet_releases_urls'])
            self.assertEqual(config_data['blocknet_bin_path'], ['blocknet-4.4.1', 'bin'])

    def test_system_specific_values_linux(self):
        """Test Linux-specific values"""
        with self.set_mock_platform('Linux', 'x86_64'), \
             patch.object(ConfigManager, '_get_aio_path', return_value=self.test_dir_path):
            # Save config
            cfg = ConfigManager()
            cfg._save_config()
            
            # Get specific values to verify
            bin_name = cfg._get_system_value('blocknet_bin_name')
            launch_opts = cfg._get_system_value('xlite_launch_options')
            bin_name_xlite = cfg._get_system_value('xlite_bin_name')
            bin_name_blockdx = cfg._get_system_value('blockdx_bin_name')
            
            self.assertEqual(bin_name, 'blocknet-qt')
            self.assertEqual(launch_opts, [])
            self.assertEqual(bin_name_xlite, 'xlite')
            self.assertEqual(bin_name_blockdx, 'block-dx')
            
            # Check file content
            config_file = self.test_dir_path / "aio_config.yaml"
            with open(config_file) as f:
                config_data = yaml.safe_load(f)
                
            self.assertEqual(config_data['blocknet_bin_name'], 'blocknet-qt')
            self.assertEqual(config_data['xlite_launch_options'], [])

    def test_system_specific_values_darwin(self):
        """Test MacOS-specific values"""
        with self.set_mock_platform('Darwin', 'x86_64'), \
             patch.object(ConfigManager, '_get_aio_path', return_value=self.test_dir_path):
            # Save config
            cfg = ConfigManager()
            cfg._save_config()
            
            # Get specific values to verify
            release_urls = cfg._get_system_value('blocknet_releases_urls')
            bin_name = cfg._get_system_value('blocknet_bin_name')
            bin_path_xlite = cfg._get_system_value('xlite_bin_path')
            bin_path_blockdx = cfg._get_system_value('blockdx_bin_path')
            daemon_bin = cfg._get_system_value('xlite_daemon_bin_name')
            
            # For MacOS, blocknet_bin_name is 'blocknet-qt'
            self.assertEqual(bin_name, 'blocknet-qt')
            self.assertEqual(bin_path_xlite, 'XLite-1.0.7-mac')
            self.assertEqual(bin_path_blockdx, 'BLOCK-DX-1.9.5-mac')
            self.assertEqual(daemon_bin, 'xlite-daemon-osx64')
            
            expected_url = "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-osx64.tar.gz"
            self.assertEqual(release_urls, expected_url)

    def test_non_system_specific_values(self):
        """Test non-system-specific values persist correctly"""
        with patch.object(ConfigManager, '_get_aio_path', return_value=self.test_dir_path):
            # Save config
            cfg_save = ConfigManager()
            
            # Modify a non-system-specific value
            new_nodes = ['192.168.1.1:41412']
            new_xconf = {'ExchangeWallets': 'XMR', 'FullLog': 'false'}
            cfg_save.config['nodes_to_add'] = new_nodes
            cfg_save.config['base_xbridge_conf'] = new_xconf
            cfg_save._save_config()
            
            # Load config
            cfg_load = ConfigManager()
            
            self.assertEqual(cfg_load.config['nodes_to_add'], new_nodes)
            self.assertEqual(cfg_load.config['base_xbridge_conf'], new_xconf)
            self.assertTrue('ExchangeWallets' in cfg_load.config['base_xbridge_conf'])

    def test_config_updates(self):
        """Test that config updates work correctly"""
        with patch.object(ConfigManager, '_get_aio_path', return_value=self.test_dir_path):
            # First config
            cfg1 = ConfigManager()
            cfg1._save_config()
            
            # Second config with updates
            cfg2 = ConfigManager()
            cfg2.config['nodes_to_add'].append('127.0.0.1:41412')
            cfg2.config['remote_blockchain_configuration_repo'] = "https://new.repo.url"
            cfg2._save_config()
            
            # Third config should have updated values
            cfg3 = ConfigManager()
            self.assertIn('127.0.0.1:41412', cfg3.config['nodes_to_add'])
            self.assertEqual(cfg3.config['remote_blockchain_configuration_repo'], "https://new.repo.url")

    def test_new_aio_folder_creation(self):
        """Test that AIO folder is created when it doesn't exist"""
        # Create a temp folder that doesn't exist yet
        new_test_dir_path = self.test_dir_path / "aio_blocknet"
        # Make sure the folder does not exist
        if new_test_dir_path.exists():
            import shutil
            shutil.rmtree(new_test_dir_path)
            
        with patch.object(ConfigManager, '_get_aio_path') as mock_method:
            # Set up the mock to create the directory and return the path
            def mock_get_aio_path():
                os.makedirs(new_test_dir_path, exist_ok=True)
                return new_test_dir_path
            
            mock_method.side_effect = mock_get_aio_path
            
            cfg = ConfigManager()
            config_file = new_test_dir_path / "aio_config.yaml"
            
            self.assertTrue(new_test_dir_path.exists())
            self.assertTrue(config_file.exists())

    def test_deep_merge(self):
        """Test _deep_merge functionality"""
        cfg = ConfigManager()
        base = {'a': 1, 'b': {'x': 2, 'y': 3}}
        update = {'b': {'y': 4, 'z': 5}, 'c': 6}
        
        result = cfg._deep_merge(copy.deepcopy(base), update)
        self.assertEqual(result['a'], 1)
        self.assertEqual(result['b']['x'], 2)
        self.assertEqual(result['b']['y'], 4)
        self.assertEqual(result['b']['z'], 5)
        self.assertEqual(result['c'], 6)

    def test_set_system_value(self):
        """Test _set_system_value method"""
        with patch.object(ConfigManager, '_get_aio_path', return_value=self.test_dir_path):
            cfg = ConfigManager()
            
            # Update a system-specific value
            cfg._set_system_value('blocknet_bin_name', 'new_blocknet')
            cfg._set_system_value('xlite_launch_options', ['--new-option'])
            
            self.assertEqual(cfg._get_system_value('blocknet_bin_name'), 'new_blocknet')
            self.assertEqual(cfg._get_system_value('xlite_launch_options'), ['--new-option'])

    def test_missing_key_in_load(self):
        """Test loading when keys are missing from YAML"""
        with patch.object(ConfigManager, '_get_aio_path', return_value=self.test_dir_path):
            # Create minimal config
            with open(self.test_dir_path / "aio_config.yaml", "w") as f:
                yaml.dump({'nodes_to_add': ['111.111.111.111:41412']}, f)
            
            cfg = ConfigManager()
            self.assertEqual(cfg.config['nodes_to_add'], ['111.111.111.111:41412'])
            # Default values should be present too
            self.assertIn('blocknet_bootstrap_url', cfg.config)

if __name__ == '__main__':
    unittest.main()
