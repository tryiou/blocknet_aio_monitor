import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gui.xlite_manager import XliteManager
import customtkinter as ctk


class TestXliteManager(unittest.TestCase):
    def setUp(self):
        # Mock global_variables
        self.mock_global_variables = MagicMock()
        self.mock_global_variables.xlite_release_url = "https://github.com/BlocknetDX/Xlite/releases/download/v1.0.0/Xlite-v1.0.0-linux-x64.tar.gz"

        # Mock root_gui and its managers
        self.mock_root_gui = MagicMock(spec=ctk.CTk)
        self.mock_root_gui.tk = MagicMock()
        self.mock_root_gui.children = {}
        self.mock_root_gui.blocknet_manager = MagicMock()
        self.mock_root_gui.disable_daemons_conf_check = False

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
        self.patcher_global_variables = patch('gui.xlite_manager.global_variables', new=self.mock_global_variables)
        self.mock_global_variables = self.patcher_global_variables.start()

        # Patch XliteHandler
        self.patcher_xlite_handler = patch('gui.xlite_manager.XliteHandler')
        self.MockXliteHandler = self.patcher_xlite_handler.start()

        # Initialize XliteManager
        self.xlite_manager = XliteManager(self.mock_root_gui)
        self.xlite_manager.utility = self.MockXliteHandler.return_value  # Assign the mock instance
        self.xlite_manager.frame_manager = MagicMock()  # Mock frame_manager after init

    def tearDown(self):
        self.patcher_global_variables.stop()
        self.patcher_xlite_handler.stop()
        self.patcher_ctk_frame.stop()
        self.patcher_ctk_label.stop()
        self.patcher_boolean_var.stop()
        self.patcher_string_var.stop()
        self.patcher_ctk_checkbox.stop()

    def test_init(self):
        self.assertIsNotNone(self.xlite_manager.root_gui)
        self.assertIsNotNone(self.xlite_manager.utility)
        self.assertEqual(self.xlite_manager.version, ["v1.0.0"])
        self.assertFalse(self.xlite_manager.process_running)
        self.assertFalse(self.xlite_manager.daemon_process_running)
        self.MockXliteHandler.assert_called_once()  # XliteHandler is initialized without custom_path

    def test_setup(self):
        with patch('gui.xlite_manager.XliteFrameManager') as MockXliteFrameManager:
            import asyncio
            asyncio.run(self.xlite_manager.setup())
            MockXliteFrameManager.assert_called_once_with(self.xlite_manager)
            self.mock_root_gui.after.assert_called_once_with(0, self.xlite_manager.update_status_xlite)

    def test_refresh_xlite_confs(self):
        self.xlite_manager.refresh_xlite_confs()
        self.xlite_manager.utility.parse_xlite_conf.assert_called_once()
        self.xlite_manager.utility.parse_xlite_daemon_conf.assert_called_once()

    def test_detect_new_xlite_install_and_add_to_xbridge_valid_coins_rpc(self):
        self.xlite_manager.utility.valid_coins_rpc = True
        self.mock_root_gui.blocknet_manager.blocknet_process_running = True
        self.mock_root_gui.blocknet_manager.utility.valid_rpc = True
        self.xlite_manager.utility.xlite_daemon_confs_local = {"test": "conf"}

        self.xlite_manager.detect_new_xlite_install_and_add_to_xbridge()

        self.mock_root_gui.blocknet_manager.utility.check_xbridge_conf.assert_called_once_with({"test": "conf"})
        self.mock_root_gui.blocknet_manager.utility.blocknet_rpc.send_rpc_request.assert_called_once_with(
            "dxloadxbridgeConf")
        self.assertTrue(self.mock_root_gui.disable_daemons_conf_check)

    def test_detect_new_xlite_install_and_add_to_xbridge_invalid_coins_rpc(self):
        self.xlite_manager.utility.valid_coins_rpc = False
        self.mock_root_gui.disable_daemons_conf_check = True  # Simulate it was enabled before

        self.xlite_manager.detect_new_xlite_install_and_add_to_xbridge()

        self.mock_root_gui.blocknet_manager.utility.check_xbridge_conf.assert_not_called()
        self.mock_root_gui.blocknet_manager.utility.blocknet_rpc.send_rpc_request.assert_not_called()
        self.assertFalse(self.mock_root_gui.disable_daemons_conf_check)

    def test_update_status_xlite(self):
        # Mock reverse proxy
        self.xlite_manager.reverse_proxy = MagicMock()
        self.xlite_manager.reverse_proxy_running = False
        
        with patch.object(self.xlite_manager, 'detect_new_xlite_install_and_add_to_xbridge') as mock_detect:
            self.xlite_manager.update_status_xlite()
            mock_detect.assert_called_once()
            self.xlite_manager.frame_manager.update_xlite_process_status_checkbox.assert_called_once()
            self.xlite_manager.frame_manager.update_xlite_store_password_button.assert_called_once()
            self.xlite_manager.frame_manager.update_xlite_daemon_process_status.assert_called_once()
            self.xlite_manager.frame_manager.update_xlite_valid_config_checkbox.assert_called_once()
            self.xlite_manager.frame_manager.update_xlite_daemon_valid_config_checkbox.assert_called_once()
            self.xlite_manager.frame_manager.update_xlite_reverse_proxy_process_status.assert_called_once()
            self.mock_root_gui.after.assert_called_once_with(2000, self.xlite_manager.update_status_xlite)
