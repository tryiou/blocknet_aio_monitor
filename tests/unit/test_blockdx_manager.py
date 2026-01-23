import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gui.blockdx_manager import BlockDXManager
import customtkinter as ctk


class TestBlockDXManager(unittest.TestCase):
    """Test suite for BlockDXManager class."""

    def setUp(self):
        """Set up common test fixtures."""
        # Mock global_variables
        self.mock_global_variables = MagicMock()
        self.mock_global_variables.blockdx_release_url = (
            "https://github.com/blocknetdx/block-dx/releases/download/v1.0.0/blockdx.zip"
        )

        # Mock root_gui and its managers
        self.mock_root_gui = MagicMock(spec=ctk.CTk)
        self.mock_root_gui.blocknet_manager = MagicMock()
        self.mock_root_gui.tk = MagicMock()
        self.mock_root_gui.children = {}

        # Create BlockDXManager instance with mocked dependencies
        with patch('gui.blockdx_manager.global_variables', new=self.mock_global_variables):
            with patch('gui.blockdx_manager.BlockDXHandler') as MockBlockDXHandler:
                self.mock_blockdx_handler = MockBlockDXHandler.return_value
                self.blockdx_manager = BlockDXManager(self.mock_root_gui)
                self.blockdx_manager.utility = self.mock_blockdx_handler
                self.blockdx_manager.frame_manager = MagicMock()

    def test_init(self):
        """Test BlockDXManager initialization."""
        self.assertIsNotNone(self.blockdx_manager.root_gui)
        self.assertIsNotNone(self.blockdx_manager.utility)
        self.assertEqual(self.blockdx_manager.version, ["v1.0.0"])
        self.assertFalse(self.blockdx_manager.process_running)
        self.assertIsNone(self.blockdx_manager.is_config_sync)

    def test_setup(self):
        """Test BlockDXManager setup creates frame manager and schedules status update."""
        import asyncio

        with patch('gui.blockdx_manager.BlockDxFrameManager') as MockBlockDxFrameManager:
            asyncio.run(self.blockdx_manager.setup())

            # Verify frame manager was created
            MockBlockDxFrameManager.assert_called_once_with(self.blockdx_manager)

            # Verify status update was scheduled
            self.mock_root_gui.after.assert_called_once_with(
                0, self.blockdx_manager.update_status_blockdx
            )

    def test_blockdx_check_config_blocknet_not_available(self):
        """Test blockdx_check_config returns early when Blocknet is not available."""
        # Simulate Blocknet not being available
        self.mock_root_gui.blocknet_manager.utility.data_folder = None
        self.mock_root_gui.blocknet_manager.utility.blocknet_conf_local = None

        self.blockdx_manager.blockdx_check_config()

        # Verify compare_and_update_local_conf was not called
        self.mock_blockdx_handler.compare_and_update_local_conf.assert_not_called()

    def test_blockdx_check_config_blocknet_available(self):
        """Test blockdx_check_config updates config when Blocknet is available."""
        # Simulate Blocknet being available
        self.mock_root_gui.blocknet_manager.utility.data_folder = "/mock/blocknet_data"
        self.mock_root_gui.blocknet_manager.utility.blocknet_conf_local = {
            'global': {
                'rpcuser': 'testuser',
                'rpcpassword': 'testpassword'
            }
        }

        self.blockdx_manager.blockdx_check_config()

        # Verify compare_and_update_local_conf was called with correct parameters
        expected_xbridge_conf_path = os.path.normpath(
            os.path.join("/mock/blocknet_data", "xbridge.conf")
        )
        self.mock_blockdx_handler.compare_and_update_local_conf.assert_called_once_with(
            expected_xbridge_conf_path, 'testuser', 'testpassword'
        )

    def test_update_status_blockdx(self):
        """Test update_status_blockdx updates UI and schedules next update."""
        self.blockdx_manager.update_status_blockdx()

        # Verify frame manager methods were called
        self.blockdx_manager.frame_manager.update_blockdx_process_status_checkbox.assert_called_once()
        self.blockdx_manager.frame_manager.update_blockdx_config_button_checkbox.assert_called_once()

        # Verify next status update was scheduled
        self.mock_root_gui.after.assert_called_once_with(
            2000, self.blockdx_manager.update_status_blockdx
        )
