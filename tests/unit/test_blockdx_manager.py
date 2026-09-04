import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import customtkinter as ctk

from gui.blockdx_manager import BlockDXManager
from utilities.app_container import AppContainer


class TestBlockDXManager(unittest.TestCase):
    """Test suite for BlockDXManager class."""

    def setUp(self):
        """Set up common test fixtures."""
        # Mock AppContainer
        self.mock_container = MagicMock()
        self.mock_container.blockdx_release_url = (
            "https://github.com/blocknetdx/block-dx/releases/download/v1.0.0/blockdx.zip"
        )

        # Mock root_gui and its managers
        self.mock_root_gui = MagicMock(spec=ctk.CTk)
        self.mock_root_gui.blocknet_manager = MagicMock()
        self.mock_root_gui.tk = MagicMock()
        self.mock_root_gui.children = {}

        # Create BlockDXManager instance with mocked dependencies
        with (
            patch("gui.blockdx_manager.get_container", return_value=self.mock_container),
            patch("gui.blockdx_manager.BlockDXHandler") as mock_blockdx_handler,
        ):
            self.mock_blockdx_handler = mock_blockdx_handler.return_value
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
        with patch("gui.blockdx_manager.BlockDxFrameManager") as mock_blockdx_frame_manager:
            self.blockdx_manager.setup()

            # Verify frame manager was created
            mock_blockdx_frame_manager.assert_called_once_with(self.blockdx_manager)

            # Verify status update was scheduled
            self.mock_root_gui.after.assert_called_once_with(0, self.blockdx_manager.update_status_blockdx)

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
            "global": {"rpcuser": "testuser", "rpcpassword": "testpassword"}
        }

        self.blockdx_manager.blockdx_check_config()

        # Verify compare_and_update_local_conf was called with correct parameters
        expected_xbridge_conf_path = os.path.normpath(os.path.join("/mock/blocknet_data", "xbridge.conf"))
        self.mock_blockdx_handler.compare_and_update_local_conf.assert_called_once_with(
            expected_xbridge_conf_path, "testuser", "testpassword"
        )

    def test_update_status_blockdx(self):
        """Test update_status_blockdx updates UI (single-shot, scheduler handles poll)."""
        self.mock_root_gui.after.reset_mock()
        self.blockdx_manager.update_status_blockdx()

        # Verify frame manager methods were called
        self.blockdx_manager.frame_manager.update_blockdx_process_status_checkbox.assert_called_once()
        self.blockdx_manager.frame_manager.update_blockdx_config_button_checkbox.assert_called_once()

        # Single-shot: no periodic rescheduling
        self.mock_root_gui.after.assert_not_called()

    def test_snapshot_tracks_core_rpc_drop(self):
        """Core stopping (valid_rpc True->False) must dirty the snapshot.

        Regression: the second Block-DX checkbox stayed ticked after Core
        stopped because valid_rpc was not part of the snapshot, so the
        refresh was skipped as 'not dirty'.
        """
        core_utility = self.mock_root_gui.blocknet_manager.utility
        core_utility.valid_rpc = True
        core_utility.data_folder = "/mock/blocknet_data"
        core_utility.blocknet_conf_local = {"global": {}}

        self.blockdx_manager.update_status_if_dirty()
        self.assertTrue(self.blockdx_manager.frame_manager.update_blockdx_config_button_checkbox.called)

        self.blockdx_manager.frame_manager.reset_mock()
        core_utility.valid_rpc = False

        self.assertTrue(self.blockdx_manager.update_status_if_dirty())
        self.blockdx_manager.frame_manager.update_blockdx_config_button_checkbox.assert_called_once()
