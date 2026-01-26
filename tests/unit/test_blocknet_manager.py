import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import asyncio

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gui.blocknet_manager import BlocknetManager
from utilities.app_container import AppContainer


class TestBlocknetManager(unittest.TestCase):
    """Test suite for BlocknetManager class."""

    def setUp(self):
        """Set up common test fixtures."""
        # Create mock root GUI
        self.mock_root_gui = MagicMock()
        self.mock_root_gui.custom_path = "/mock/custom/path"
        self.mock_root_gui.xlite_manager = MagicMock()

        # Mock AppContainer
        self.mock_container = MagicMock()
        self.mock_container.blocknet_release_url = (
            "https://github.com/BlocknetDX/blocknet-core/releases/download/4.4.1/blocknet-4.4.1-linux64.tar.gz"
        )

        # Patch dependencies
        self.patches = {
            'get_container': patch('gui.blocknet_manager.get_container', return_value=self.mock_container),
            'BlocknetHandler': patch('gui.blocknet_manager.BlocknetHandler'),
        }

        # Start all patches
        for name, patcher in self.patches.items():
            setattr(self, f'mock_{name.lower()}', patcher.start())

        # Initialize BlocknetManager
        self.blocknet_manager = BlocknetManager(self.mock_root_gui)
        self.blocknet_manager.utility = self.mock_blocknethandler.return_value
        self.blocknet_manager.frame_manager = MagicMock()

    def tearDown(self):
        """Clean up patches after each test."""
        for patcher in self.patches.values():
            patcher.stop()

    def test_init(self):
        """Test BlocknetManager initialization."""
        self.assertIsNotNone(self.blocknet_manager.root_gui)
        self.assertIsNotNone(self.blocknet_manager.utility)
        self.assertEqual(self.blocknet_manager.version, ["4.4.1"])
        self.assertFalse(self.blocknet_manager.blocknet_process_running)
        self.assertIsNone(self.blocknet_manager.bootstrap_thread)
        self.mock_blocknethandler.assert_called_once_with(custom_path="/mock/custom/path")

    def test_setup(self):
        """Test setup creates frame manager and schedules status update."""
        with patch('gui.blocknet_manager.BlocknetCoreFrameManager') as MockBlocknetCoreFrameManager:
            asyncio.run(self.blocknet_manager.setup())
            MockBlocknetCoreFrameManager.assert_called_once_with(self.blocknet_manager)
            self.mock_root_gui.after.assert_called_once_with(0, self.blocknet_manager.update_status_blocknet_core)

    def test_check_config(self):
        """Test check_config with xlite daemon configurations."""
        test_cases = [
            ({"daemon_key": "daemon_value"}, {"daemon_key": "daemon_value"}),
            (None, None),
        ]

        for xlite_daemon_confs, expected_conf in test_cases:
            with self.subTest(xlite_daemon_confs=xlite_daemon_confs):
                self.mock_root_gui.xlite_manager.utility.xlite_daemon_confs_local = xlite_daemon_confs
                self.blocknet_manager.check_config()
                self.blocknet_manager.utility.compare_and_update_local_conf.assert_called_once_with(expected_conf)
                self.blocknet_manager.utility.compare_and_update_local_conf.reset_mock()

    def test_update_status_blocknet_core(self):
        """Test update_status_blocknet_core calls all frame manager update methods."""
        self.blocknet_manager.update_status_blocknet_core()

        # Verify all frame manager methods are called
        frame_manager_methods = [
            'update_blocknet_bootstrap_button',
            'update_blocknet_process_status_checkbox',
            'update_blocknet_custom_path_button',
            'update_blocknet_conf_status_checkbox',
            'update_blocknet_data_path_status_checkbox',
            'update_blocknet_rpc_connection_checkbox',
        ]

        for method in frame_manager_methods:
            with self.subTest(method=method):
                getattr(self.blocknet_manager.frame_manager, method).assert_called_once()

        # Verify status update is scheduled
        self.mock_root_gui.after.assert_called_once_with(2000, self.blocknet_manager.update_status_blocknet_core)
