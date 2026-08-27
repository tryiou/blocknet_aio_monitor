"""Tests for BlockDxFrameManager following DRY/SOC/KISS principles."""
import os
import sys
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import widgets_strings
from gui.blockdx_frame_manager import BlockDxFrameManager
from utilities.app_container import AppContainer


class TestBlockDxFrameManager(unittest.TestCase):
    """Test suite for BlockDxFrameManager with improved structure."""

    def setUp(self):
        """Set up test fixtures for BlockDxFrameManager tests."""
        # Create mock AppContainer
        self.mock_container = MagicMock()
        self.mock_container.conf_data.blockdx_selectedWallets_blocknet = "BLOCK"

        # Create mock parent with all required attributes
        self.mock_parent = MagicMock()
        self.mock_parent.process_running = False
        self.mock_parent.is_config_sync = False
        self.mock_parent.utility = MagicMock()
        self.mock_parent.utility.blockdx_conf_local = None

        # Create mock root_gui with blocknet_manager
        self.mock_root_gui = MagicMock()
        self.mock_parent.root_gui = self.mock_root_gui

        # Create mock blocknet_manager
        self.mock_blocknet_manager = MagicMock()
        self.mock_root_gui.blocknet_manager = self.mock_blocknet_manager

        # Create mock utility for blocknet_manager
        self.mock_blocknet_manager.utility = MagicMock()
        self.mock_blocknet_manager.utility.data_folder = None
        self.mock_blocknet_manager.utility.blocknet_conf_local = None
        self.mock_blocknet_manager.utility.valid_rpc = False

        # Create mock patches to avoid tkinter issues
        self.mock_ctk = MagicMock()
        self.mock_ctk_frame = MagicMock()
        self.mock_ctk_label = MagicMock()
        self.mock_ctk_boolean_var = MagicMock()
        self.mock_ctk_string_var = MagicMock()
        self.mock_ctk_checkbox = MagicMock()

        # Patch tkinter components and get_container
        self.patches = [
            patch('gui.blockdx_frame_manager.ctk', self.mock_ctk),
            patch('gui.blockdx_frame_manager.ctk.CTkFrame', self.mock_ctk_frame),
            patch('gui.blockdx_frame_manager.ctk.CTkLabel', self.mock_ctk_label),
            patch('gui.blockdx_frame_manager.ctk.BooleanVar', self.mock_ctk_boolean_var),
            patch('gui.blockdx_frame_manager.ctk.StringVar', self.mock_ctk_string_var),
            patch('gui.blockdx_frame_manager.ctkCheckBoxMod.CTkCheckBox', self.mock_ctk_checkbox),
            patch('gui.blockdx_frame_manager.get_container', return_value=self.mock_container),
        ]

        for p in self.patches:
            p.start()

        # Mock StringVar and BooleanVar to return mock objects
        self.mock_ctk_string_var.return_value = MagicMock()
        self.mock_ctk_boolean_var.return_value = MagicMock()

        # Create the manager
        self.manager = BlockDxFrameManager(self.mock_parent)

    def tearDown(self):
        """Clean up patches after each test."""
        for p in self.patches:
            p.stop()

    def test_init(self):
        """Test BlockDxFrameManager initialization."""
        self.assertIsNotNone(self.manager)
        self.assertEqual(self.manager.parent, self.mock_parent)
        self.assertEqual(self.manager.root_gui, self.mock_root_gui)
        self.assertIsNotNone(self.manager.master_frame)
        self.assertIsNotNone(self.manager.title_frame)

    def test_grid_widgets(self):
        """Test grid_widgets method."""
        self.manager.grid_widgets(0, 0)

        # Verify that all widgets were gridded
        self.assertEqual(self.mock_ctk_checkbox.call_count, 2)  # 2 checkboxes
        self.manager.label.grid.assert_called_once()

    def test_update_blockdx_process_status_checkbox_running(self):
        """Test update_blockdx_process_status_checkbox when running."""
        self.mock_parent.process_running = True

        self.manager.update_blockdx_process_status_checkbox()

        self.manager.process_status_checkbox_state.set.assert_called_once_with(True)
        self.manager.process_status_checkbox_string_var.set.assert_called_once_with(
            widgets_strings.blockdx_running_string
        )

    def test_update_blockdx_process_status_checkbox_not_running(self):
        """Test update_blockdx_process_status_checkbox when not running."""
        self.mock_parent.process_running = False

        self.manager.update_blockdx_process_status_checkbox()

        self.manager.process_status_checkbox_state.set.assert_called_once_with(False)
        self.manager.process_status_checkbox_string_var.set.assert_called_once_with(
            widgets_strings.blockdx_not_running_string
        )


class TestBlockDxFrameManagerConfigValidation(unittest.TestCase):
    """Test suite for BlockDxFrameManager config validation logic."""

    def setUp(self):
        """Set up test fixtures for config validation tests."""
        # Create mock AppContainer
        self.mock_container = MagicMock()
        self.mock_container.conf_data.blockdx_selectedWallets_blocknet = "BLOCK"

        # Create mock parent with all required attributes
        self.mock_parent = MagicMock()
        self.mock_parent.process_running = False
        self.mock_parent.is_config_sync = False
        self.mock_parent.utility = MagicMock()
        self.mock_parent.utility.blockdx_conf_local = None

        # Create mock root_gui with blocknet_manager
        self.mock_root_gui = MagicMock()
        self.mock_parent.root_gui = self.mock_root_gui

        # Create mock blocknet_manager
        self.mock_blocknet_manager = MagicMock()
        self.mock_root_gui.blocknet_manager = self.mock_blocknet_manager

        # Create mock utility for blocknet_manager
        self.mock_blocknet_manager.utility = MagicMock()
        self.mock_blocknet_manager.utility.data_folder = None
        self.mock_blocknet_manager.utility.blocknet_conf_local = None
        self.mock_blocknet_manager.utility.valid_rpc = False

        # Create mock patches to avoid tkinter issues
        self.mock_ctk = MagicMock()
        self.mock_ctk_frame = MagicMock()
        self.mock_ctk_label = MagicMock()
        self.mock_ctk_boolean_var = MagicMock()
        self.mock_ctk_string_var = MagicMock()
        self.mock_ctk_checkbox = MagicMock()

        # Patch tkinter components and get_container
        self.patches = [
            patch('gui.blockdx_frame_manager.ctk', self.mock_ctk),
            patch('gui.blockdx_frame_manager.ctk.CTkFrame', self.mock_ctk_frame),
            patch('gui.blockdx_frame_manager.ctk.CTkLabel', self.mock_ctk_label),
            patch('gui.blockdx_frame_manager.ctk.BooleanVar', self.mock_ctk_boolean_var),
            patch('gui.blockdx_frame_manager.ctk.StringVar', self.mock_ctk_string_var),
            patch('gui.blockdx_frame_manager.ctkCheckBoxMod.CTkCheckBox', self.mock_ctk_checkbox),
            patch('gui.blockdx_frame_manager.get_container', return_value=self.mock_container),
        ]

        for p in self.patches:
            p.start()

        # Mock StringVar and BooleanVar to return mock objects
        self.mock_ctk_string_var.return_value = MagicMock()
        self.mock_ctk_boolean_var.return_value = MagicMock()

        # Create the manager
        self.manager = BlockDxFrameManager(self.mock_parent)

    def tearDown(self):
        """Clean up patches after each test."""
        for p in self.patches:
            p.stop()

    def _setup_valid_core_setup(self):
        """Helper to set up valid core setup."""
        self.mock_blocknet_manager.utility.data_folder = "/mock/data"
        self.mock_blocknet_manager.utility.blocknet_conf_local = {
            "global": {"rpcuser": "user", "rpcpassword": "pass"}
        }
        self.mock_blocknet_manager.utility.valid_rpc = True

    def _setup_valid_blockdx_conf(self):
        """Helper to set up valid blockdx config."""
        self.mock_parent.utility.blockdx_conf_local = {
            "user": "user",
            "password": "pass",
            "xbridgeConfPath": "/mock/data/xbridge.conf",
            "selectedWallets": [self.mock_container.conf_data.blockdx_selectedWallets_blocknet]
        }

    def test_valid_core_setup_valid_rpc_config_sync(self):
        """Test with valid core setup, valid RPC, and config sync."""
        self._setup_valid_core_setup()
        self._setup_valid_blockdx_conf()
        self.mock_parent.is_config_sync = True

        self.manager.update_blockdx_config_button_checkbox()

        self.manager.valid_config_checkbox_string_var.set.assert_called_with(
            widgets_strings.blockdx_valid_config_string
        )
        self.manager.valid_config_checkbox_state.set.assert_called_once_with(True)

    def test_valid_core_setup_valid_rpc_config_not_sync(self):
        """Test with valid core setup, valid RPC, but config not sync."""
        self._setup_valid_core_setup()
        self.mock_parent.utility.blockdx_conf_local = {
            "user": "different_user",
            "password": "different_pass",
            "xbridgeConfPath": "/mock/data/xbridge.conf",
            "selectedWallets": [self.mock_container.conf_data.blockdx_selectedWallets_blocknet]
        }
        self.mock_parent.is_config_sync = False

        self.manager.update_blockdx_config_button_checkbox()

        self.manager.valid_config_checkbox_string_var.set.assert_called_with(
            widgets_strings.blockdx_not_valid_config_string
        )
        self.manager.valid_config_checkbox_state.set.assert_called_once_with(False)

    def test_valid_core_setup_no_rpc(self):
        """Test with valid core setup but no RPC."""
        self._setup_valid_core_setup()
        self.mock_blocknet_manager.utility.valid_rpc = False
        self._setup_valid_blockdx_conf()
        self.mock_parent.is_config_sync = True

        self.manager.update_blockdx_config_button_checkbox()

        self.manager.valid_config_checkbox_string_var.set.assert_called_with(
            widgets_strings.blockdx_missing_blocknet_config_string
        )
        self.manager.valid_config_checkbox_state.set.assert_called_once_with(False)

    def test_valid_core_setup_missing_blocknet_config(self):
        """Test with valid core setup but missing blocknet config."""
        self.mock_blocknet_manager.utility.data_folder = "/mock/data"
        self.mock_blocknet_manager.utility.blocknet_conf_local = None
        self.mock_blocknet_manager.utility.valid_rpc = False

        self.manager.update_blockdx_config_button_checkbox()

        self.manager.valid_config_checkbox_string_var.set.assert_called_once_with(
            widgets_strings.blockdx_missing_blocknet_config_string
        )
        self.manager.valid_config_checkbox_state.set.assert_called_once_with(False)

    def test_valid_core_setup_missing_data_folder(self):
        """Test with missing data folder."""
        self.mock_blocknet_manager.utility.data_folder = None
        self.mock_blocknet_manager.utility.blocknet_conf_local = {
            "global": {"rpcuser": "user", "rpcpassword": "pass"}
        }
        self.mock_blocknet_manager.utility.valid_rpc = False

        self.manager.update_blockdx_config_button_checkbox()

        self.manager.valid_config_checkbox_string_var.set.assert_called_once_with(
            widgets_strings.blockdx_missing_blocknet_config_string
        )
        self.manager.valid_config_checkbox_state.set.assert_called_once_with(False)

    def test_valid_core_setup_missing_blockdx_conf(self):
        """Test with valid core setup but missing blockdx conf."""
        self._setup_valid_core_setup()
        self.mock_parent.utility.blockdx_conf_local = None

        self.manager.update_blockdx_config_button_checkbox()

        self.manager.valid_config_checkbox_string_var.set.assert_called_with(
            widgets_strings.blockdx_not_valid_config_string
        )
        self.manager.valid_config_checkbox_state.set.assert_called_once_with(False)

    def test_valid_core_setup_missing_selected_wallets(self):
        """Test with valid core setup but missing selected wallets."""
        self._setup_valid_core_setup()
        self.mock_parent.utility.blockdx_conf_local = {
            "user": "user",
            "password": "pass",
            "xbridgeConfPath": "/mock/data/xbridge.conf",
            "selectedWallets": []
        }

        self.manager.update_blockdx_config_button_checkbox()

        self.manager.valid_config_checkbox_string_var.set.assert_called_with(
            widgets_strings.blockdx_not_valid_config_string
        )
        self.manager.valid_config_checkbox_state.set.assert_called_once_with(False)

    def test_valid_core_setup_wrong_xbridge_path(self):
        """Test with valid core setup but wrong xbridge path."""
        self._setup_valid_core_setup()
        self.mock_parent.utility.blockdx_conf_local = {
            "user": "user",
            "password": "pass",
            "xbridgeConfPath": "/wrong/path/xbridge.conf",
            "selectedWallets": [self.mock_container.conf_data.blockdx_selectedWallets_blocknet]
        }

        self.manager.update_blockdx_config_button_checkbox()

        self.manager.valid_config_checkbox_string_var.set.assert_called_with(
            widgets_strings.blockdx_not_valid_config_string
        )
        self.manager.valid_config_checkbox_state.set.assert_called_once_with(False)


if __name__ == '__main__':
    unittest.main()
