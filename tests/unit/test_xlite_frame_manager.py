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

        # Create mock patches to avoid tkinter issues (factories yield fresh mocks per widget)
        self.mock_ctk = MagicMock()
        self.mock_ctk_boolean_var = MagicMock()
        self.mock_ctk_string_var = MagicMock()

        def _fresh(*args, **kwargs):
            return MagicMock()

        # Patch tkinter components
        self.patches = [
            patch("gui.xlite_frame_manager.ctk", self.mock_ctk),
            patch("gui.layout.widgets.make_frame", side_effect=_fresh),
            patch("gui.xlite_frame_manager.make_caption", side_effect=_fresh),
            patch("gui.xlite_frame_manager.make_label", side_effect=_fresh),
            patch("gui.xlite_frame_manager.make_button", side_effect=_fresh),
            patch("gui.xlite_frame_manager.make_checkbox", side_effect=_fresh),
            patch("gui.xlite_frame_manager.SegmentedPills"),
            patch("gui.xlite_frame_manager.ctk.BooleanVar", self.mock_ctk_boolean_var),
            patch("gui.xlite_frame_manager.ctk.StringVar", self.mock_ctk_string_var),
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
        """Title row order caption/label/pills/button; 2x2 checkbox grid (XLITE_SPEC)."""
        self.manager.grid_widgets()

        self.manager.xlite_label.grid.assert_called_once_with(row=0, column=0, padx=2, pady=2, sticky="w")
        self.manager.xbridge_block_source_label.grid.assert_called_once_with(
            row=0, column=1, padx=2, pady=2, sticky="e"
        )
        self.manager.xbridge_block_pills.widget.grid.assert_called_once_with(
            row=0, column=2, padx=2, pady=2, sticky="w"
        )
        self.manager.store_password_button.grid.assert_called_once_with(row=0, column=3, padx=2, pady=2, sticky="e")
        self.manager.process_status_checkbox.grid.assert_called_once_with(row=1, column=0, padx=5, pady=5, sticky="ew")
        self.manager.daemon_process_status_checkbox.grid.assert_called_once_with(
            row=1, column=1, padx=5, pady=5, sticky="ew"
        )
        self.manager.valid_config_checkbox.grid.assert_called_once_with(row=2, column=0, padx=5, pady=5, sticky="ew")
        self.manager.daemon_valid_config_checkbox.grid.assert_called_once_with(
            row=2, column=1, padx=5, pady=5, sticky="ew"
        )

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
        """Reverse-proxy panel removed; the manager poll hook remains a harmless no-op."""
        self.manager.update_xlite_reverse_proxy_process_status()

    @patch("gui.xlite_frame_manager.utils.wipe_stored_password")
    @patch("gui.xlite_frame_manager.os.environ")
    def test_xlite_store_password_button_mouse_click_right_click(self, mock_environ, mock_wipe):
        """Test xlite_store_password_button_mouse_click with right click (wipe password)"""
        mock_wipe.return_value = True
        # Set up stored password
        self.mock_root_gui.stored_password = "test_password"

        # Mock event with right click (button 3)
        mock_event = MagicMock()
        mock_event.num = 3

        # Mock CC_WALLET_PASS in environment
        mock_environ.__contains__.return_value = True

        # Call the method
        result = self.manager.xlite_store_password_button_mouse_click(mock_event)

        # Verify that password was wiped
        mock_wipe.assert_called_once_with()
        self.assertEqual(self.mock_root_gui.stored_password, None)
        mock_environ.pop.assert_any_call("CC_WALLET_PASS")
        mock_environ.pop.assert_any_call("CC_WALLET_AUTOLOGIN")
        self.assertEqual(result, "break")

    @patch("gui.xlite_frame_manager.utils.wipe_stored_password")
    @patch("gui.xlite_frame_manager.os.environ")
    def test_xlite_store_password_button_mouse_click_right_click_no_env_vars(self, mock_environ, mock_wipe):
        """Test xlite_store_password_button_mouse_click with right click when env vars don't exist"""
        mock_wipe.return_value = True
        # Set up stored password
        self.mock_root_gui.stored_password = "test_password"

        # Mock event with right click (button 3)
        mock_event = MagicMock()
        mock_event.num = 3

        # Mock CC_WALLET_PASS not in environment
        mock_environ.__contains__.return_value = False

        # Call the method
        result = self.manager.xlite_store_password_button_mouse_click(mock_event)

        # Verify that password was wiped
        mock_wipe.assert_called_once_with()
        self.assertEqual(self.mock_root_gui.stored_password, None)
        mock_environ.pop.assert_not_called()
        self.assertEqual(result, "break")

    @patch("gui.xlite_frame_manager.utils.wipe_stored_password")
    @patch("gui.xlite_frame_manager.os.environ")
    def test_xlite_store_password_button_mouse_click_right_click_failure_keeps_password(self, mock_environ, mock_wipe):
        """Failed wipe keeps the in-memory password (truthful UI)."""
        mock_wipe.return_value = False
        self.mock_root_gui.stored_password = "test_password"

        mock_event = MagicMock()
        mock_event.num = 3
        mock_environ.__contains__.return_value = True

        result = self.manager.xlite_store_password_button_mouse_click(mock_event)

        mock_wipe.assert_called_once_with()
        self.assertEqual(self.mock_root_gui.stored_password, "test_password")
        self.assertEqual(result, "break")

    @patch("gui.xlite_frame_manager.ctkInputDialogMod.CTkInputDialog")
    @patch("gui.xlite_frame_manager.utils.store_password")
    def test_xlite_store_password_button_mouse_click_left_click_with_password(
        self, mock_store_password, mock_ctk_input_dialog
    ):
        """Test xlite_store_password_button_mouse_click with left click (store password)"""
        mock_store_password.return_value = True
        # Mock event with left click (button 1)
        mock_event = MagicMock()
        mock_event.num = 1

        # Mock password input dialog
        mock_dialog_instance = MagicMock()
        mock_dialog_instance.get_input.return_value = "test_password"
        mock_ctk_input_dialog.return_value = mock_dialog_instance

        # Call the method
        result = self.manager.xlite_store_password_button_mouse_click(mock_event)

        # Verify that password was stored via the single-route file store
        mock_ctk_input_dialog.assert_called_once()
        mock_store_password.assert_called_once_with("test_password")
        self.assertEqual(self.mock_root_gui.stored_password, "test_password")
        self.assertEqual(result, "break")

    @patch("gui.xlite_frame_manager.ctkInputDialogMod.CTkInputDialog")
    @patch("gui.xlite_frame_manager.utils.store_password")
    def test_xlite_store_password_button_mouse_click_left_click_store_failure(
        self, mock_store_password, mock_ctk_input_dialog
    ):
        """Failed store keeps the previous in-memory state."""
        mock_store_password.return_value = False
        mock_event = MagicMock()
        mock_event.num = 1

        mock_dialog_instance = MagicMock()
        mock_dialog_instance.get_input.return_value = "test_password"
        mock_ctk_input_dialog.return_value = mock_dialog_instance

        result = self.manager.xlite_store_password_button_mouse_click(mock_event)

        mock_store_password.assert_called_once_with("test_password")
        self.assertEqual(self.mock_root_gui.stored_password, None)
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

    def test_xbridge_block_source_widget_created(self):
        """Pills offer Core/XLite via the SegmentedPills adapter, left of Password Stored."""
        from gui.xlite_frame_manager import SegmentedPills

        SegmentedPills.assert_called_once()
        _, kwargs = SegmentedPills.call_args
        self.assertEqual(
            kwargs["values"],
            [widgets_strings.xbridge_block_source_core_string, widgets_strings.xbridge_block_source_xlite_string],
        )
        self.assertIs(kwargs["variable"], self.manager.xbridge_block_source_var)
        self.manager.grid_widgets()
        self.manager.xbridge_block_pills.widget.grid.assert_called_once_with(
            row=0, column=2, padx=2, pady=2, sticky="w"
        )
        self.manager.store_password_button.grid.assert_called_once_with(row=0, column=3, padx=2, pady=2, sticky="e")

    def _string_var_initial_values(self):
        return [c.kwargs.get("value") for c in self.mock_ctk.StringVar.call_args_list]

    def test_xbridge_block_source_initial_auto_core_without_daemon_block(self):
        """No stored pref + daemon without BLOCK: selector starts on Core."""
        self.mock_root_gui.xbridge_block_source = None
        self.mock_parent.utility.xlite_daemon_confs_local = {"BTC": {}}
        XliteFrameManager(self.mock_parent)

        self.assertIn(widgets_strings.xbridge_block_source_core_string, self._string_var_initial_values())

    def test_xbridge_block_source_initial_auto_xlite_with_daemon_block(self):
        """No stored pref + daemon holding BLOCK settings: selector starts on XLite."""
        self.mock_root_gui.xbridge_block_source = None
        self.mock_parent.utility.xlite_daemon_confs_local = {
            "BLOCK": {"rpcUsername": "u", "rpcPassword": "p", "rpcPort": "1"},
            "master": {},
        }
        XliteFrameManager(self.mock_parent)

        self.assertIn(widgets_strings.xbridge_block_source_xlite_string, self._string_var_initial_values())

    def test_xbridge_block_source_initial_auto_core_with_incomplete_daemon_block(self):
        """No stored pref + daemon BLOCK entry without RPC settings: selector starts on Core."""
        self.mock_root_gui.xbridge_block_source = None
        self.mock_parent.utility.xlite_daemon_confs_local = {"BLOCK": {}, "master": {}}
        XliteFrameManager(self.mock_parent)

        self.assertIn(widgets_strings.xbridge_block_source_core_string, self._string_var_initial_values())

    def test_xbridge_block_source_initial_honors_stored_pref(self):
        """Stored pref wins over auto-resolution at startup."""
        self.mock_root_gui.xbridge_block_source = "xlite"
        self.mock_parent.utility.xlite_daemon_confs_local = None
        XliteFrameManager(self.mock_parent)

        self.assertIn(widgets_strings.xbridge_block_source_xlite_string, self._string_var_initial_values())

    def test_paint_delegates_to_pills_adapter(self):
        """Per-state pill text lives in SegmentedPills; the frame only triggers repaint."""
        self.manager._paint_xbridge_pills()

        self.manager.xbridge_block_pills.repaint.assert_called_once()

    def test_on_xbridge_block_source_changed_repaints(self):
        """User pick repaints pill text after persisting."""
        self.manager.xbridge_block_pills.repaint.reset_mock()
        with (
            patch("utilities.utils.save_cfg_json"),
            patch.object(self.manager, "_paint_xbridge_pills") as mock_paint,
        ):
            self.manager.on_xbridge_block_source_changed(widgets_strings.xbridge_block_source_core_string)

        mock_paint.assert_called_once()

    def test_on_xbridge_block_source_changed_persists_and_rearms(self):
        """User pick persists like theme and re-arms the conf check."""
        with patch("utilities.utils.save_cfg_json") as mock_save:
            self.manager.on_xbridge_block_source_changed(widgets_strings.xbridge_block_source_core_string)

        mock_save.assert_called_once_with("xbridge_block_source", "core")
        self.assertEqual(self.mock_root_gui.xbridge_block_source, "core")
        self.assertFalse(self.mock_root_gui.disable_daemons_conf_check)

        with patch("utilities.utils.save_cfg_json") as mock_save:
            self.manager.on_xbridge_block_source_changed(widgets_strings.xbridge_block_source_xlite_string)

        mock_save.assert_called_once_with("xbridge_block_source", "xlite")
        self.assertEqual(self.mock_root_gui.xbridge_block_source, "xlite")

    def test_on_xbridge_block_source_changed_ignores_garbage(self):
        """Unknown selection values never persist and never dirty the sync snapshot."""
        self.mock_parent._last_snapshot = ("steady", "state")
        with patch("utilities.utils.save_cfg_json") as mock_save:
            self.manager.on_xbridge_block_source_changed("banana")

        mock_save.assert_not_called()
        self.assertEqual(self.mock_parent._last_snapshot, ("steady", "state"))

    def _set_daemon_confs(self, daemon_confs):
        self.mock_parent.utility.xlite_daemon_confs_local = daemon_confs

    def test_update_widget_disabled_without_daemon_block(self):
        """Daemon without BLOCK: no choice to make, control disabled."""
        self._set_daemon_confs({"BTC": {}})

        self.manager.update_xbridge_block_source_widget()

        self.manager.xbridge_block_segmented.configure.assert_called_with(state="disabled")

    def test_update_widget_enabled_with_daemon_block(self):
        """Daemon holding BLOCK settings: control enabled."""
        self._set_daemon_confs({"BLOCK": {"rpcUsername": "u", "rpcPassword": "p", "rpcPort": "1"}})

        self.manager.update_xbridge_block_source_widget()

        self.manager.xbridge_block_segmented.configure.assert_called_with(state="normal")

    def test_on_xbridge_block_source_changed_dirties_sync_snapshot(self):
        """The pick must actually apply: UiSync only runs update_status_xlite on snapshot change."""
        self.mock_parent._last_snapshot = ("steady", "state")
        with patch("utilities.utils.save_cfg_json"):
            self.manager.on_xbridge_block_source_changed(widgets_strings.xbridge_block_source_xlite_string)

        self.assertIsNone(self.mock_parent._last_snapshot)
        self.assertFalse(self.mock_root_gui.disable_daemons_conf_check)

    def test_update_widget_resyncs_selection_under_auto(self):
        """No stored pref: selection tracks auto-resolution as daemon BLOCK appears/disappears."""
        self.mock_root_gui.xbridge_block_source = None
        self._set_daemon_confs({"BLOCK": {"rpcUsername": "u", "rpcPassword": "p", "rpcPort": "1"}})

        self.manager.update_xbridge_block_source_widget()

        self.manager.xbridge_block_pills.set.assert_called_with(widgets_strings.xbridge_block_source_xlite_string)

    def test_update_widget_resync_skipped_when_already_correct(self):
        """No stored pref + selection already matching auto: no redundant set()."""
        self.mock_root_gui.xbridge_block_source = None
        self._set_daemon_confs({"BTC": {}})
        self.manager.xbridge_block_pills.get.return_value = widgets_strings.xbridge_block_source_core_string

        self.manager.update_xbridge_block_source_widget()

        self.manager.xbridge_block_pills.set.assert_not_called()

    def test_update_widget_keeps_stored_selection(self):
        """Stored pref: selection never moves."""
        self.mock_root_gui.xbridge_block_source = "core"
        self._set_daemon_confs({"BLOCK": {"rpcUsername": "u", "rpcPassword": "p", "rpcPort": "1"}})

        self.manager.update_xbridge_block_source_widget()

        self.manager.xbridge_block_pills.set.assert_not_called()


if __name__ == "__main__":
    unittest.main()
