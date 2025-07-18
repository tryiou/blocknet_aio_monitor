import unittest
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock, call

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gui.blocknet_manager import BlocknetManager
from utilities import global_variables
import customtkinter as ctk

class TestBlocknetManager(unittest.TestCase):
    def setUp(self):
        # Mock global_variables
        self.mock_global_variables = MagicMock()
        self.mock_global_variables.blocknet_release_url = "https://github.com/BlocknetDX/blocknet-core/releases/download/4.4.1/blocknet-4.4.1-linux64.tar.gz"

        # Mock root_gui and its managers
        self.mock_root_gui = MagicMock(spec=ctk.CTk)
        self.mock_root_gui.tk = MagicMock()
        self.mock_root_gui.children = {}
        self.mock_root_gui.xlite_manager = MagicMock()
        self.mock_root_gui.custom_path = "/mock/custom/path"

        # Patch customtkinter components
        self.patcher_ctk_frame = patch('customtkinter.CTkFrame')
        self.patcher_ctk_label = patch('customtkinter.CTkLabel')
        self.patcher_boolean_var = patch('customtkinter.BooleanVar')
        self.patcher_string_var = patch('customtkinter.StringVar')
        self.patcher_ctk_checkbox = patch('custom_tk_mods.ctkCheckBox.CTkCheckBox')

        self.mock_ctk_frame = self.patcher_ctk_frame.start()
        self.mock_ctk_label = self.patcher_ctk_label.start()
        self.mock_boolean_var = self.patcher_boolean_var.start()
        self.mock_string_var = self.patcher_string_var.start()
        self.mock_ctk_checkbox = self.patcher_ctk_checkbox.start()

        # Patch global variables
        self.patcher_global_variables = patch('gui.blocknet_manager.global_variables', new=self.mock_global_variables)
        self.mock_global_variables = self.patcher_global_variables.start()

        # Patch BlocknetHandler
        self.patcher_blocknet_handler = patch('gui.blocknet_manager.BlocknetHandler')
        self.MockBlocknetHandler = self.patcher_blocknet_handler.start()

        # Initialize BlocknetManager
        self.blocknet_manager = BlocknetManager(self.mock_root_gui)
        self.blocknet_manager.utility = self.MockBlocknetHandler.return_value # Assign the mock instance
        self.blocknet_manager.frame_manager = MagicMock() # Mock frame_manager after init

    def tearDown(self):
        self.patcher_global_variables.stop()
        self.patcher_blocknet_handler.stop()
        self.patcher_ctk_frame.stop()
        self.patcher_ctk_label.stop()
        self.patcher_boolean_var.stop()
        self.patcher_string_var.stop()
        self.patcher_ctk_checkbox.stop()

    def test_init(self):
        self.assertIsNotNone(self.blocknet_manager.root_gui)
        self.assertIsNotNone(self.blocknet_manager.utility)
        self.assertEqual(self.blocknet_manager.version, ["4.4.1"])
        self.assertFalse(self.blocknet_manager.blocknet_process_running)
        self.assertIsNone(self.blocknet_manager.bootstrap_thread)
        self.MockBlocknetHandler.assert_called_once_with(custom_path="/mock/custom/path")

    def test_setup(self):
        with patch('gui.blocknet_manager.BlocknetCoreFrameManager') as MockBlocknetCoreFrameManager:
            import asyncio
            asyncio.run(self.blocknet_manager.setup())
            MockBlocknetCoreFrameManager.assert_called_once_with(self.blocknet_manager)
            self.mock_root_gui.after.assert_called_once_with(0, self.blocknet_manager.update_status_blocknet_core)

    def test_check_config_with_xlite_daemon_confs(self):
        self.mock_root_gui.xlite_manager.utility.xlite_daemon_confs_local = {"daemon_key": "daemon_value"}
        self.blocknet_manager.check_config()
        self.blocknet_manager.utility.compare_and_update_local_conf.assert_called_once_with(
            {"daemon_key": "daemon_value"}
        )

    def test_check_config_without_xlite_daemon_confs(self):
        self.mock_root_gui.xlite_manager.utility.xlite_daemon_confs_local = None
        self.blocknet_manager.check_config()
        self.blocknet_manager.utility.compare_and_update_local_conf.assert_called_once_with(
            None
        )

    def test_update_status_blocknet_core(self):
        self.blocknet_manager.update_status_blocknet_core()
        self.blocknet_manager.frame_manager.update_blocknet_bootstrap_button.assert_called_once()
        self.blocknet_manager.frame_manager.update_blocknet_process_status_checkbox.assert_called_once()
        self.blocknet_manager.frame_manager.update_blocknet_custom_path_button.assert_called_once()
        self.blocknet_manager.frame_manager.update_blocknet_conf_status_checkbox.assert_called_once()
        self.blocknet_manager.frame_manager.update_blocknet_data_path_status_checkbox.assert_called_once()
        self.blocknet_manager.frame_manager.update_blocknet_rpc_connection_checkbox.assert_called_once()
        self.mock_root_gui.after.assert_called_once_with(2000, self.blocknet_manager.update_status_blocknet_core)
