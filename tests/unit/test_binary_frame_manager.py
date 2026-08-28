import os
import sys
import tkinter as tk
import unittest
from unittest.mock import ANY, MagicMock, patch

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestBinaryFrameManager(unittest.TestCase):
    """Test suite for BinaryFrameManager."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a hidden root window for tkinter variables (skip if Tcl missing on Windows CI)
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception as e:
            # Windows CI may have broken Tcl (init.tcl missing) — skip GUI tests
            self.skipTest(f"Tk not available on this runner: {e}")
            self.root = MagicMock()
            self.root.withdraw = MagicMock()
            self.root.destroy = MagicMock()

        # Mock the parent and root_gui
        self.mock_parent = MagicMock()
        self.mock_root = MagicMock()
        self.mock_parent.root_gui = self.mock_root

        # Mock theme and images
        self.mock_root.theme_img = MagicMock()
        self.mock_root.install_greyed_img = MagicMock()
        self.mock_root.start_greyed_img = MagicMock()
        self.mock_root.transparent_img = MagicMock()
        self.mock_root.after = MagicMock()

        # Mock managers
        self.mock_root.blocknet_manager = MagicMock()
        self.mock_root.blocknet_manager.version = ["v1.0.0", "v1.1.0"]
        self.mock_root.blockdx_manager = MagicMock()
        self.mock_root.blockdx_manager.version = ["v2.0.0", "v2.1.0"]
        self.mock_root.xlite_manager = MagicMock()
        self.mock_root.xlite_manager.version = ["v3.0.0", "v3.1.0"]

        # Mock XBridgeBotManager
        self.mock_bot_manager = MagicMock()
        self.mock_bot_manager.get_available_branches.return_value = ["main", "develop"]

        # Mock customtkinter widgets
        self.mock_frame = MagicMock()
        self.mock_label = MagicMock()
        self.mock_button = MagicMock()
        self.mock_option_menu = MagicMock()
        self.mock_checkbox = MagicMock()

        # Setup patches
        self._setup_patches()

    def _setup_patches(self):
        """Setup all necessary patches for the test."""
        self.patcher_frame = patch("customtkinter.CTkFrame", return_value=self.mock_frame)
        self.patcher_label = patch("customtkinter.CTkLabel", return_value=self.mock_label)
        self.patcher_button = patch("customtkinter.CTkButton", return_value=self.mock_button)
        self.patcher_option_menu = patch("customtkinter.CTkOptionMenu", return_value=self.mock_option_menu)
        self.patcher_checkbox = patch("custom_tk_mods.ctkCheckBox.CTkCheckBox", return_value=self.mock_checkbox)
        self.patcher_bot_manager = patch(
            "gui.xbridge_bot_manager.XBridgeBotManager", return_value=self.mock_bot_manager
        )
        self.patcher_get_remote_branches = patch(
            "utilities.git_repo_management.GitRepoManagement.get_remote_branches", return_value=["main", "develop"]
        )

        self.patcher_frame.start()
        self.patcher_label.start()
        self.patcher_button.start()
        self.patcher_option_menu.start()
        self.patcher_checkbox.start()
        self.patcher_bot_manager.start()
        self.patcher_get_remote_branches.start()

        # Import after patching
        from gui.binary_frame_manager import BinaryFrameManager

        self.BinaryFrameManager = BinaryFrameManager

    def tearDown(self):
        """Clean up after tests."""
        self.patcher_frame.stop()
        self.patcher_label.stop()
        self.patcher_button.stop()
        self.patcher_option_menu.stop()
        self.patcher_checkbox.stop()
        self.patcher_bot_manager.stop()
        self.patcher_get_remote_branches.stop()

        if hasattr(self, "root"):
            try:  # noqa: SIM105
                self.root.destroy()
            except Exception:  # noqa: S110
                pass

    def _create_frame_manager(self):
        """Helper to create a BinaryFrameManager instance."""
        return self.BinaryFrameManager(self.mock_parent)

    def _get_all_widgets(self, frame_manager):
        """Helper to get all widgets from a frame manager."""
        return [
            frame_manager.header_label,
            frame_manager.button_switch_theme,
            frame_manager.blocknet_label,
            frame_manager.blockdx_label,
            frame_manager.xlite_label,
            frame_manager.bots_label,
            frame_manager.blocknet_version_optionmenu,
            frame_manager.blockdx_version_optionmenu,
            frame_manager.xlite_version_optionmenu,
            frame_manager.bots_version_optionmenu,
            frame_manager.blocknet_found_checkbox,
            frame_manager.blockdx_found_checkbox,
            frame_manager.xlite_found_checkbox,
            frame_manager.bots_found_checkbox,
            frame_manager.install_delete_blocknet_button,
            frame_manager.install_delete_blockdx_button,
            frame_manager.install_delete_xlite_button,
            frame_manager.install_delete_bots_button,
            frame_manager.blocknet_start_close_button,
            frame_manager.blockdx_start_close_button,
            frame_manager.xlite_toggle_execution_button,
            frame_manager.bots_toggle_execution_button,
        ]

    def test_init(self):
        """Test BinaryFrameManager initialization."""
        frame_manager = self._create_frame_manager()

        self.assertEqual(frame_manager.root_gui, self.mock_root)
        self.assertEqual(frame_manager.parent, self.mock_parent)
        self.assertIsNotNone(frame_manager.master_frame)
        self.assertIsNotNone(frame_manager.title_frame)

    def test_init_widgets(self):
        """Test that all required widgets are initialized."""
        frame_manager = self._create_frame_manager()

        # Verify all widgets exist
        widgets = self._get_all_widgets(frame_manager)
        for widget in widgets:
            self.assertIsNotNone(widget)

    def test_initial_variable_values(self):
        """Test initial values of BooleanVars and StringVars."""
        frame_manager = self._create_frame_manager()

        # Check BooleanVars
        self.assertFalse(frame_manager.blocknet_installed_boolvar.get())
        self.assertFalse(frame_manager.blockdx_installed_boolvar.get())
        self.assertFalse(frame_manager.xlite_installed_boolvar.get())
        self.assertFalse(frame_manager.bots_installed_boolvar.get())

        # Check StringVars
        self.assertEqual(frame_manager.install_delete_blocknet_string_var.get(), "")
        self.assertEqual(frame_manager.install_delete_blockdx_string_var.get(), "")
        self.assertEqual(frame_manager.install_delete_xlite_string_var.get(), "")
        self.assertEqual(frame_manager.blocknet_start_close_button_string_var.get(), "")
        self.assertEqual(frame_manager.blockdx_start_close_button_string_var.get(), "")
        self.assertEqual(frame_manager.xlite_toggle_execution_string_var.get(), "")

    def test_grid_widgets(self):
        """Test grid_widgets method."""
        frame_manager = self._create_frame_manager()

        # Replace widgets with fresh mocks to test grid calls
        frame_manager.header_label = MagicMock()
        frame_manager.button_switch_theme = MagicMock()
        frame_manager.blocknet_label = MagicMock()
        frame_manager.blockdx_label = MagicMock()
        frame_manager.xlite_label = MagicMock()
        frame_manager.bots_label = MagicMock()
        frame_manager.blocknet_version_optionmenu = MagicMock()
        frame_manager.blockdx_version_optionmenu = MagicMock()
        frame_manager.xlite_version_optionmenu = MagicMock()
        frame_manager.bots_version_optionmenu = MagicMock()
        frame_manager.blocknet_found_checkbox = MagicMock()
        frame_manager.blockdx_found_checkbox = MagicMock()
        frame_manager.xlite_found_checkbox = MagicMock()
        frame_manager.bots_found_checkbox = MagicMock()
        frame_manager.install_delete_blocknet_button = MagicMock()
        frame_manager.install_delete_blockdx_button = MagicMock()
        frame_manager.install_delete_xlite_button = MagicMock()
        frame_manager.install_delete_bots_button = MagicMock()
        frame_manager.blocknet_start_close_button = MagicMock()
        frame_manager.blockdx_start_close_button = MagicMock()
        frame_manager.xlite_toggle_execution_button = MagicMock()
        frame_manager.bots_toggle_execution_button = MagicMock()

        # Call grid_widgets
        frame_manager.grid_widgets(0, 0)

        # Verify grid calls for header and theme button
        frame_manager.header_label.grid.assert_called_once()
        frame_manager.button_switch_theme.grid.assert_called_once()

        # Verify all other widgets have grid called
        widgets_to_check = [
            frame_manager.blocknet_label,
            frame_manager.blockdx_label,
            frame_manager.xlite_label,
            frame_manager.bots_label,
            frame_manager.blocknet_version_optionmenu,
            frame_manager.blockdx_version_optionmenu,
            frame_manager.xlite_version_optionmenu,
            frame_manager.bots_version_optionmenu,
            frame_manager.blocknet_found_checkbox,
            frame_manager.blockdx_found_checkbox,
            frame_manager.xlite_found_checkbox,
            frame_manager.bots_found_checkbox,
            frame_manager.install_delete_blocknet_button,
            frame_manager.install_delete_blockdx_button,
            frame_manager.install_delete_xlite_button,
            frame_manager.install_delete_bots_button,
            frame_manager.blocknet_start_close_button,
            frame_manager.blockdx_start_close_button,
            frame_manager.xlite_toggle_execution_button,
            frame_manager.bots_toggle_execution_button,
        ]

        for widget in widgets_to_check:
            widget.grid.assert_called_once()

    @patch("utilities.utils.disable_button")
    def test_install_update_bots_command(self, mock_disable):
        """Test install_update_bots_command with valid branch."""
        frame_manager = self._create_frame_manager()
        frame_manager.bots_version_optionmenu.get.return_value = "main"
        frame_manager.xbridge_bot_manager = self.mock_bot_manager

        frame_manager.install_update_bots_command()

        # Verify disable_button was called for both buttons
        self.assertEqual(mock_disable.call_count, 2)
        mock_disable.assert_any_call(frame_manager.install_delete_bots_button, self.mock_root.install_greyed_img)
        mock_disable.assert_any_call(frame_manager.bots_toggle_execution_button, self.mock_root.start_greyed_img)

        # Verify install_or_update was called
        self.mock_bot_manager.install_or_update.assert_called_with("main")

    @patch("utilities.utils.disable_button")
    def test_install_update_bots_command_no_branch(self, mock_disable):
        """Test install_update_bots_command when no branch is selected."""
        frame_manager = self._create_frame_manager()
        frame_manager.bots_version_optionmenu.get.return_value = ""

        frame_manager.install_update_bots_command()

        # Verify no calls were made
        mock_disable.assert_not_called()
        self.mock_bot_manager.install_or_update.assert_not_called()

    def test_install_update_bots_command_no_manager(self):
        """Test install_update_bots_command when bot manager is None."""
        frame_manager = self._create_frame_manager()
        frame_manager.xbridge_bot_manager = None

        # This should not raise an exception
        frame_manager.install_update_bots_command()

    @patch("utilities.utils.disable_button")
    def test_toggle_bots_execution_command(self, mock_disable):
        """Test toggle_bots_execution_command with valid branch."""
        frame_manager = self._create_frame_manager()
        frame_manager.bots_version_optionmenu.get.return_value = "main"
        frame_manager.xbridge_bot_manager = self.mock_bot_manager

        # Mock the bot manager to have venv
        self.mock_bot_manager.repo_management = MagicMock()
        self.mock_bot_manager.repo_management.venv = MagicMock()
        self.mock_bot_manager.repo_exists.return_value = True

        frame_manager.toggle_bots_execution_command()

        # Verify disable_button was called for both buttons
        self.assertEqual(mock_disable.call_count, 2)
        mock_disable.assert_any_call(frame_manager.install_delete_bots_button, self.mock_root.install_greyed_img)
        mock_disable.assert_any_call(frame_manager.bots_toggle_execution_button, self.mock_root.start_greyed_img)

        # Verify toggle_execution was called
        self.mock_bot_manager.toggle_execution.assert_called_with("main")

    @patch("utilities.utils.disable_button")
    def test_toggle_bots_execution_command_no_branch(self, mock_disable):
        """Test toggle_bots_execution_command when no branch is selected."""
        frame_manager = self._create_frame_manager()
        frame_manager.bots_version_optionmenu.get.return_value = ""

        frame_manager.toggle_bots_execution_command()

        # Verify no calls were made
        mock_disable.assert_not_called()
        self.mock_bot_manager.toggle_execution.assert_not_called()

    def test_toggle_bots_execution_command_no_manager(self):
        """Test toggle_bots_execution_command when bot manager is None."""
        frame_manager = self._create_frame_manager()
        frame_manager.xbridge_bot_manager = None

        # This should not raise an exception
        frame_manager.toggle_bots_execution_command()

    def test_run_after_setup_venv_exists(self):
        """Test run_after_setup when venv exists."""
        frame_manager = self._create_frame_manager()
        frame_manager.xbridge_bot_manager = self.mock_bot_manager
        self.mock_bot_manager.repo_management.venv = True

        frame_manager.run_after_setup()

        # Verify toggle_execution was called
        self.mock_bot_manager.toggle_execution.assert_called_once()

    def test_run_after_setup_venv_not_exists(self):
        """Test run_after_setup when venv doesn't exist."""
        frame_manager = self._create_frame_manager()
        # Reset after count from _defer_branch_fetch
        self.mock_root.after.reset_mock()
        # Ensure no UiSyncController driving retries
        self.mock_root.ui_sync = None
        self.mock_root._closing = False
        frame_manager.xbridge_bot_manager = self.mock_bot_manager
        self.mock_bot_manager.repo_management.venv = False

        frame_manager.run_after_setup()

        # Verify after was called to retry (1000ms)
        self.mock_root.after.assert_called_once_with(1000, unittest.mock.ANY)


if __name__ == "__main__":
    unittest.main()
