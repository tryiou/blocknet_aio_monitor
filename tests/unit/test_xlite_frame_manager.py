import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import widgets_strings
from gui.xlite_frame_manager import XliteFrameManager


class TestXliteFrameManager(unittest.TestCase):
    """Test suite for XliteFrameManager"""

    def setUp(self):
        """Set up test fixtures for XliteFrameManager tests"""
        # Create mock parent with all required attributes
        self.mock_parent = MagicMock()
        self.mock_parent.process_running = False
        self.mock_parent.daemon_process_running = False
        self.mock_parent.reverse_proxy_running = False
        self.mock_parent.utility = MagicMock()
        self.mock_parent.utility.xlite_conf_local = None
        self.mock_parent.utility.xlite_daemon_confs_local = None

        # Create mock root_gui
        self.mock_root_gui = MagicMock()
        self.mock_root_gui.stored_password = None
        self.mock_parent.root_gui = self.mock_root_gui

        # Create mock patches to avoid tkinter issues
        self.mock_ctk = MagicMock()
        self.mock_ctk_frame = MagicMock()
        self.mock_ctk_label = MagicMock()
        self.mock_ctk_button = MagicMock()
        self.mock_ctk_boolean_var = MagicMock()
        self.mock_ctk_string_var = MagicMock()
        self.mock_ctk_checkbox = MagicMock()

        # Patch tkinter components
        self.patches = [
            patch("gui.xlite_frame_manager.ctk", self.mock_ctk),
            patch("gui.xlite_frame_manager.ctk.CTkFrame", self.mock_ctk_frame),
            patch("gui.xlite_frame_manager.ctk.CTkLabel", self.mock_ctk_label),
            patch("gui.xlite_frame_manager.ctk.CTkButton", self.mock_ctk_button),
            patch("gui.xlite_frame_manager.ctk.BooleanVar", self.mock_ctk_boolean_var),
            patch("gui.xlite_frame_manager.ctk.StringVar", self.mock_ctk_string_var),
            patch("gui.xlite_frame_manager.ctkCheckBoxMod.CTkCheckBox", self.mock_ctk_checkbox),
        ]

        for p in self.patches:
            p.start()

        # Mock StringVar and BooleanVar to return mock objects
        self.mock_ctk_string_var.return_value = MagicMock()
        self.mock_ctk_boolean_var.return_value = MagicMock()

        # Create the manager
        self.manager = XliteFrameManager(self.mock_parent)

    def tearDown(self):
        """Clean up patches after each test"""
        for p in self.patches:
            p.stop()

    def test_init(self):
        """Test XliteFrameManager initialization"""
        self.assertIsNotNone(self.manager)
        self.assertEqual(self.manager.parent, self.mock_parent)
        self.assertEqual(self.manager.root_gui, self.mock_root_gui)
        self.assertIsNotNone(self.manager.master_frame)
        self.assertIsNotNone(self.manager.title_frame)

    def test_grid_widgets(self):
        """Test grid_widgets method"""
        self.manager.grid_widgets(0, 0)

        # Verify all 5 checkboxes were created and gridded
        self.assertEqual(self.mock_ctk_checkbox.call_count, 5)
        self.manager.store_password_button.grid.assert_called_once()

    def test_update_process_status(self):
        """Test update_xlite_process_status_checkbox with both running states"""
        # Test running state
        self.mock_parent.process_running = True
        self.manager.update_xlite_process_status_checkbox()
        self.manager.process_status_checkbox_state.set.assert_called_with(True)
        self.manager.process_status_checkbox_string_var.set.assert_called_with(widgets_strings.xlite_running_string)

        # Reset mocks
        self.manager.process_status_checkbox_state.set.reset_mock()
        self.manager.process_status_checkbox_string_var.set.reset_mock()

        # Test not running state
        self.mock_parent.process_running = False
        self.manager.update_xlite_process_status_checkbox()
        self.manager.process_status_checkbox_state.set.assert_called_with(False)
        self.manager.process_status_checkbox_string_var.set.assert_called_with(widgets_strings.xlite_not_running_string)

    def test_update_store_password_button(self):
        """Test update_xlite_store_password_button with and without stored password"""
        # Test with password
        self.mock_root_gui.stored_password = "test_password"
        self.manager.update_xlite_store_password_button()
        self.manager.store_password_button_string_var.set.assert_called_with(
            widgets_strings.xlite_stored_password_string
        )

        # Reset mock
        self.manager.store_password_button_string_var.set.reset_mock()

        # Test without password
        self.mock_root_gui.stored_password = None
        self.manager.update_xlite_store_password_button()
        self.manager.store_password_button_string_var.set.assert_called_with(
            widgets_strings.xlite_store_password_string
        )

    def test_update_daemon_process_status(self):
        """Test update_xlite_daemon_process_status with both running states"""
        # Test running state
        self.mock_parent.daemon_process_running = True
        self.manager.update_xlite_daemon_process_status()
        self.manager.daemon_process_status_checkbox_state.set.assert_called_with(True)
        self.manager.daemon_process_status_checkbox_string_var.set.assert_called_with(
            widgets_strings.xlite_daemon_running_string
        )

        # Reset mocks
        self.manager.daemon_process_status_checkbox_state.set.reset_mock()
        self.manager.daemon_process_status_checkbox_string_var.set.reset_mock()

        # Test not running state
        self.mock_parent.daemon_process_running = False
        self.manager.update_xlite_daemon_process_status()
        self.manager.daemon_process_status_checkbox_state.set.assert_called_with(False)
        self.manager.daemon_process_status_checkbox_string_var.set.assert_called_with(
            widgets_strings.xlite_daemon_not_running_string
        )

    def test_update_valid_config_checkbox(self):
        """Test update_xlite_valid_config_checkbox with valid and invalid configs"""
        # Test valid config
        self.mock_parent.utility.xlite_conf_local = {"some": "config"}
        self.manager.update_xlite_valid_config_checkbox()
        self.manager.valid_config_checkbox_state.set.assert_called_with(True)
        self.manager.valid_config_checkbox_string_var.set.assert_called_with(widgets_strings.xlite_valid_config_string)

        # Reset mocks
        self.manager.valid_config_checkbox_state.set.reset_mock()
        self.manager.valid_config_checkbox_string_var.set.reset_mock()

        # Test invalid config
        self.mock_parent.utility.xlite_conf_local = None
        self.manager.update_xlite_valid_config_checkbox()
        self.manager.valid_config_checkbox_state.set.assert_called_with(False)
        self.manager.valid_config_checkbox_string_var.set.assert_called_with(
            widgets_strings.xlite_not_valid_config_string
        )

    def test_update_daemon_valid_config_checkbox(self):
        """Test update_xlite_daemon_valid_config_checkbox with various config states"""
        # Test valid config with master
        self.mock_parent.utility.xlite_daemon_confs_local = {"master": {"some": "config"}}
        self.manager.update_xlite_daemon_valid_config_checkbox()
        self.manager.daemon_valid_config_checkbox_state.set.assert_called_with(True)
        self.manager.daemon_valid_config_checkbox_string_var.set.assert_called_with(
            widgets_strings.xlite_daemon_valid_config_string
        )

        # Reset mocks
        self.manager.daemon_valid_config_checkbox_state.set.reset_mock()
        self.manager.daemon_valid_config_checkbox_string_var.set.reset_mock()

        # Test invalid config without master
        self.mock_parent.utility.xlite_daemon_confs_local = {"other": "config"}
        self.manager.update_xlite_daemon_valid_config_checkbox()
        self.manager.daemon_valid_config_checkbox_state.set.assert_called_with(False)
        self.manager.daemon_valid_config_checkbox_string_var.set.assert_called_with(
            widgets_strings.xlite_daemon_not_valid_config_string
        )

        # Reset mocks
        self.manager.daemon_valid_config_checkbox_state.set.reset_mock()
        self.manager.daemon_valid_config_checkbox_string_var.set.reset_mock()

        # Test invalid config with None
        self.mock_parent.utility.xlite_daemon_confs_local = None
        self.manager.update_xlite_daemon_valid_config_checkbox()
        self.manager.daemon_valid_config_checkbox_state.set.assert_called_with(False)
        self.manager.daemon_valid_config_checkbox_string_var.set.assert_called_with(
            widgets_strings.xlite_daemon_not_valid_config_string
        )

    def test_update_reverse_proxy_process_status(self):
        """Test update_xlite_reverse_proxy_process_status with both running states"""
        # Test running state
        self.mock_parent.reverse_proxy_running = True
        self.manager.update_xlite_reverse_proxy_process_status()
        self.manager.reverse_proxy_status_str.set.assert_called_with(widgets_strings.xlite_reverse_proxy_running_string)
        self.manager.reverse_proxy_process_status_checkbox_state.set.assert_called_with(True)

        # Reset mocks
        self.manager.reverse_proxy_status_str.set.reset_mock()
        self.manager.reverse_proxy_process_status_checkbox_state.set.reset_mock()

        # Test not running state
        self.mock_parent.reverse_proxy_running = False
        self.manager.update_xlite_reverse_proxy_process_status()
        self.manager.reverse_proxy_status_str.set.assert_called_with(
            widgets_strings.xlite_reverse_proxy_not_running_string
        )
        self.manager.reverse_proxy_process_status_checkbox_state.set.assert_called_with(False)

    @patch("gui.xlite_frame_manager.utils.remove_cfg_json_key")
    @patch("gui.xlite_frame_manager.os.environ")
    def test_xlite_store_password_button_mouse_click_right_click(self, mock_environ, mock_remove_cfg_json_key):
        """Test xlite_store_password_button_mouse_click with right click (wipe password)"""
        # Set up stored password
        self.mock_root_gui.stored_password = "test_password"

        # Mock event with right click (button 3)
        mock_event = MagicMock()
        mock_event.num = 3

        # Mock CC_WALLET_PASS in environment
        mock_environ.__contains__.return_value = True

        # Call the method
        result = self.manager.xlite_store_password_button_mouse_click(mock_event)

        # Verify that password was wiped (remove_cfg_json_key will also delete encryption key)
        mock_remove_cfg_json_key.assert_called_once_with("xl_pass")
        self.assertEqual(self.mock_root_gui.stored_password, None)
        mock_environ.pop.assert_any_call("CC_WALLET_PASS")
        mock_environ.pop.assert_any_call("CC_WALLET_AUTOLOGIN")
        self.assertEqual(result, "break")

    @patch("gui.xlite_frame_manager.utils.remove_cfg_json_key")
    @patch("gui.xlite_frame_manager.os.environ")
    def test_xlite_store_password_button_mouse_click_right_click_no_env_vars(
        self, mock_environ, mock_remove_cfg_json_key
    ):
        """Test xlite_store_password_button_mouse_click with right click when env vars don't exist"""
        # Set up stored password
        self.mock_root_gui.stored_password = "test_password"

        # Mock event with right click (button 3)
        mock_event = MagicMock()
        mock_event.num = 3

        # Mock CC_WALLET_PASS not in environment
        mock_environ.__contains__.return_value = False

        # Call the method
        result = self.manager.xlite_store_password_button_mouse_click(mock_event)

        # Verify that password was wiped (remove_cfg_json_key will also delete encryption key)
        mock_remove_cfg_json_key.assert_called_once_with("xl_pass")
        self.assertEqual(self.mock_root_gui.stored_password, None)
        mock_environ.pop.assert_not_called()
        self.assertEqual(result, "break")

    @patch("gui.xlite_frame_manager.ctkInputDialogMod.CTkInputDialog")
    @patch("gui.xlite_frame_manager.utils.save_cfg_json")
    @patch("gui.xlite_frame_manager.utils.encrypt_password")
    @patch("gui.xlite_frame_manager.utils.generate_key")
    def test_xlite_store_password_button_mouse_click_left_click_with_password(
        self, mock_generate_key, mock_encrypt_password, mock_save_cfg_json, mock_ctk_input_dialog
    ):
        """Test xlite_store_password_button_mouse_click with left click (store password)"""
        # Mock event with left click (button 1)
        mock_event = MagicMock()
        mock_event.num = 1

        # Mock password input dialog
        mock_dialog_instance = MagicMock()
        mock_dialog_instance.get_input.return_value = "test_password"
        mock_ctk_input_dialog.return_value = mock_dialog_instance

        # Mock encryption
        mock_generate_key.return_value = b"test_key"
        mock_encrypt_password.return_value = "encrypted_password"

        # Call the method
        result = self.manager.xlite_store_password_button_mouse_click(mock_event)

        # Verify that password was stored (key is in keyring, only encrypted password in JSON)
        mock_ctk_input_dialog.assert_called_once()
        mock_generate_key.assert_called_once()
        mock_encrypt_password.assert_called_once_with("test_password")
        mock_save_cfg_json.assert_called_once_with(key="xl_pass", data="encrypted_password")
        self.assertEqual(self.mock_root_gui.stored_password, "test_password")
        self.assertEqual(result, "break")

    @patch("gui.xlite_frame_manager.ctkInputDialogMod.CTkInputDialog")
    def test_xlite_store_password_button_mouse_click_left_click_no_password(self, mock_ctk_input_dialog):
        """Test xlite_store_password_button_mouse_click with left click (no password entered)"""
        # Mock event with left click (button 1)
        mock_event = MagicMock()
        mock_event.num = 1

        # Mock password input dialog returning None
        mock_dialog_instance = MagicMock()
        mock_dialog_instance.get_input.return_value = None
        mock_ctk_input_dialog.return_value = mock_dialog_instance

        # Call the method
        result = self.manager.xlite_store_password_button_mouse_click(mock_event)

        # Verify that no password was stored
        mock_ctk_input_dialog.assert_called_once()
        self.assertEqual(self.mock_root_gui.stored_password, None)
        self.assertEqual(result, "break")


if __name__ == "__main__":
    unittest.main()
