import unittest
from unittest.mock import MagicMock, patch, call
import tkinter as tk
import customtkinter as ctk


class TestBinaryFrameManager(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        # Create a hidden root window for tkinter variables
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the window
        
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
        
        # Patch all customtkinter components
        self.patcher_frame = patch('customtkinter.CTkFrame', return_value=self.mock_frame)
        self.patcher_label = patch('customtkinter.CTkLabel', return_value=self.mock_label)
        self.patcher_button = patch('customtkinter.CTkButton', return_value=self.mock_button)
        self.patcher_option_menu = patch('customtkinter.CTkOptionMenu', return_value=self.mock_option_menu)
        self.patcher_checkbox = patch('custom_tk_mods.ctkCheckBox.CTkCheckBox', return_value=self.mock_checkbox)
        self.patcher_bot_manager = patch('gui.xbridge_bot_manager.XBridgeBotManager', return_value=self.mock_bot_manager)
        
        self.patcher_frame.start()
        self.patcher_label.start()
        self.patcher_button.start()
        self.patcher_option_menu.start()
        self.patcher_checkbox.start()
        self.patcher_bot_manager.start()
        
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
        
        if hasattr(self, 'root'):
            self.root.destroy()
    
    def test_init(self):
        """Test BinaryFrameManager initialization."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        
        self.assertEqual(frame_manager.root_gui, self.mock_root)
        self.assertEqual(frame_manager.parent, self.mock_parent)
        self.assertIsNotNone(frame_manager.master_frame)
        self.assertIsNotNone(frame_manager.title_frame)
    
    def test_init_widgets(self):
        """Test widget initialization."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        
        # Check that widgets are created
        self.assertIsNotNone(frame_manager.header_label)
        self.assertIsNotNone(frame_manager.button_switch_theme)
        self.assertIsNotNone(frame_manager.blocknet_label)
        self.assertIsNotNone(frame_manager.blockdx_label)
        self.assertIsNotNone(frame_manager.xlite_label)
        self.assertIsNotNone(frame_manager.bots_label)
        
        # Check option menus
        self.assertIsNotNone(frame_manager.blocknet_version_optionmenu)
        self.assertIsNotNone(frame_manager.blockdx_version_optionmenu)
        self.assertIsNotNone(frame_manager.xlite_version_optionmenu)
        self.assertIsNotNone(frame_manager.bots_version_optionmenu)
        
        # Check checkboxes
        self.assertIsNotNone(frame_manager.blocknet_found_checkbox)
        self.assertIsNotNone(frame_manager.blockdx_found_checkbox)
        self.assertIsNotNone(frame_manager.xlite_found_checkbox)
        self.assertIsNotNone(frame_manager.bots_found_checkbox)
        
        # Check buttons
        self.assertIsNotNone(frame_manager.install_delete_blocknet_button)
        self.assertIsNotNone(frame_manager.install_delete_blockdx_button)
        self.assertIsNotNone(frame_manager.install_delete_xlite_button)
        self.assertIsNotNone(frame_manager.install_delete_bots_button)
        self.assertIsNotNone(frame_manager.blocknet_start_close_button)
        self.assertIsNotNone(frame_manager.blockdx_start_close_button)
        self.assertIsNotNone(frame_manager.xlite_toggle_execution_button)
        self.assertIsNotNone(frame_manager.bots_toggle_execution_button)
        
        # Check StringVars
        self.assertIsNotNone(frame_manager.install_delete_blocknet_string_var)
        self.assertIsNotNone(frame_manager.install_delete_blockdx_string_var)
        self.assertIsNotNone(frame_manager.install_delete_xlite_string_var)
        self.assertIsNotNone(frame_manager.blocknet_start_close_button_string_var)
        self.assertIsNotNone(frame_manager.blockdx_start_close_button_string_var)
        self.assertIsNotNone(frame_manager.xlite_toggle_execution_string_var)
        
        # Check BooleanVars
        self.assertIsNotNone(frame_manager.blocknet_installed_boolvar)
        self.assertIsNotNone(frame_manager.blockdx_installed_boolvar)
        self.assertIsNotNone(frame_manager.xlite_installed_boolvar)
        self.assertIsNotNone(frame_manager.bots_installed_boolvar)
    
    def test_install_update_bots_command(self):
        """Test install_update_bots_command method."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        
        # Mock version selection
        frame_manager.bots_version_optionmenu.get.return_value = "main"
        
        # Replace the actual bot manager with our mock
        frame_manager.xbridge_bot_manager = self.mock_bot_manager
        
        # Mock utility functions
        with patch('utilities.utils.disable_button') as mock_disable:
            frame_manager.install_update_bots_command()
            
            # Verify disable_button was called for both buttons
            self.assertEqual(mock_disable.call_count, 2)
            mock_disable.assert_any_call(frame_manager.install_delete_bots_button, self.mock_root.install_greyed_img)
            mock_disable.assert_any_call(frame_manager.bots_toggle_execution_button, self.mock_root.start_greyed_img)
            
            # Verify install_or_update was called on the actual bot manager
            self.mock_bot_manager.install_or_update.assert_called_with("main")
    
    def test_toggle_bots_execution_command(self):
        """Test toggle_bots_execution_command method."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        
        # Mock version selection
        frame_manager.bots_version_optionmenu.get.return_value = "main"
        
        # Replace the actual bot manager with our mock
        frame_manager.xbridge_bot_manager = self.mock_bot_manager
        
        # Mock the bot manager to have venv
        self.mock_bot_manager.repo_management = MagicMock()
        self.mock_bot_manager.repo_management.venv = MagicMock()
        self.mock_bot_manager.repo_exists.return_value = True
        
        # Mock utility functions
        with patch('utilities.utils.disable_button') as mock_disable:
            frame_manager.toggle_bots_execution_command()
            
            # Verify disable_button was called for both buttons
            self.assertEqual(mock_disable.call_count, 2)
            mock_disable.assert_any_call(frame_manager.install_delete_bots_button, self.mock_root.install_greyed_img)
            mock_disable.assert_any_call(frame_manager.bots_toggle_execution_button, self.mock_root.start_greyed_img)
            
            # Verify toggle_execution was called on the actual bot manager
            self.mock_bot_manager.toggle_execution.assert_called_with("main")
    
    def test_run_after_setup(self):
        """Test run_after_setup method."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        
        # Replace the actual bot manager with our mock
        frame_manager.xbridge_bot_manager = self.mock_bot_manager
        
        # Test when venv exists
        self.mock_bot_manager.repo_management.venv = True
        frame_manager.run_after_setup()
        self.mock_bot_manager.toggle_execution.assert_called_once()
        
        # Test when venv doesn't exist
        self.mock_bot_manager.repo_management.venv = False
        frame_manager.run_after_setup()
        self.mock_root.after.assert_called()
    
    def test_grid_widgets(self):
        """Test grid_widgets method."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        
        # Mock widgets
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
        
        # Test grid_widgets
        frame_manager.grid_widgets(0, 0)
        
        # Verify grid calls
        frame_manager.header_label.grid.assert_called_once()
        frame_manager.button_switch_theme.grid.assert_called_once()
        frame_manager.blocknet_label.grid.assert_called_once()
        frame_manager.blockdx_label.grid.assert_called_once()
        frame_manager.xlite_label.grid.assert_called_once()
        frame_manager.bots_label.grid.assert_called_once()
        
        # Verify all widgets have grid called
        widgets_to_check = [
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
            frame_manager.bots_toggle_execution_button
        ]
        
        for widget in widgets_to_check:
            widget.grid.assert_called_once()
    
    def test_install_update_bots_command_no_branch(self):
        """Test install_update_bots_command when no branch is selected."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        
        # Mock empty version selection
        frame_manager.bots_version_optionmenu.get.return_value = ""
        
        with patch('utilities.utils.disable_button') as mock_disable:
            frame_manager.install_update_bots_command()
            
            # Verify no calls were made
            mock_disable.assert_not_called()
            self.mock_bot_manager.install_or_update.assert_not_called()
    
    def test_toggle_bots_execution_command_no_branch(self):
        """Test toggle_bots_execution_command when no branch is selected."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        
        # Mock empty version selection
        frame_manager.bots_version_optionmenu.get.return_value = ""
        
        with patch('utilities.utils.disable_button') as mock_disable:
            frame_manager.toggle_bots_execution_command()
            
            # Verify no calls were made
            mock_disable.assert_not_called()
            self.mock_bot_manager.toggle_execution.assert_not_called()
    
    def test_install_update_bots_command_no_manager(self):
        """Test install_update_bots_command when bot manager is None."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        frame_manager.xbridge_bot_manager = None
        
        # This should not raise an exception
        frame_manager.install_update_bots_command()

    def test_toggle_bots_execution_command_no_manager(self):
        """Test toggle_bots_execution_command when bot manager is None."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        frame_manager.xbridge_bot_manager = None
        
        # This should not raise an exception
        frame_manager.toggle_bots_execution_command()

    def test_boolean_vars_initial_values(self):
        """Test initial values of BooleanVars."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        
        # Check initial boolean values
        self.assertFalse(frame_manager.blocknet_installed_boolvar.get())
        self.assertFalse(frame_manager.blockdx_installed_boolvar.get())
        self.assertFalse(frame_manager.xlite_installed_boolvar.get())
        self.assertFalse(frame_manager.bots_installed_boolvar.get())

    def test_string_vars_initial_values(self):
        """Test initial values of StringVars."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        
        # Check initial string values (should be empty)
        self.assertEqual(frame_manager.install_delete_blocknet_string_var.get(), '')
        self.assertEqual(frame_manager.install_delete_blockdx_string_var.get(), '')
        self.assertEqual(frame_manager.install_delete_xlite_string_var.get(), '')
        self.assertEqual(frame_manager.blocknet_start_close_button_string_var.get(), '')
        self.assertEqual(frame_manager.blockdx_start_close_button_string_var.get(), '')
        self.assertEqual(frame_manager.xlite_toggle_execution_string_var.get(), '')

    def test_widgets_created_with_correct_types(self):
        """Test that all required widgets are created."""
        frame_manager = self.BinaryFrameManager(self.mock_parent)
        
        # Verify widgets exist (they'll be mocked, but should be assigned)
        self.assertIsNotNone(frame_manager.header_label)
        self.assertIsNotNone(frame_manager.button_switch_theme)
        self.assertIsNotNone(frame_manager.blocknet_label)
        self.assertIsNotNone(frame_manager.blockdx_label)
        self.assertIsNotNone(frame_manager.xlite_label)
        self.assertIsNotNone(frame_manager.bots_label)
        
        # Verify option menus exist
        self.assertIsNotNone(frame_manager.blocknet_version_optionmenu)
        self.assertIsNotNone(frame_manager.blockdx_version_optionmenu)
        self.assertIsNotNone(frame_manager.xlite_version_optionmenu)
        self.assertIsNotNone(frame_manager.bots_version_optionmenu)
        
        # Verify checkboxes exist
        self.assertIsNotNone(frame_manager.blocknet_found_checkbox)
        self.assertIsNotNone(frame_manager.blockdx_found_checkbox)
        self.assertIsNotNone(frame_manager.xlite_found_checkbox)
        self.assertIsNotNone(frame_manager.bots_found_checkbox)
        
        # Verify buttons exist
        self.assertIsNotNone(frame_manager.install_delete_blocknet_button)
        self.assertIsNotNone(frame_manager.install_delete_blockdx_button)
        self.assertIsNotNone(frame_manager.install_delete_xlite_button)
        self.assertIsNotNone(frame_manager.install_delete_bots_button)
        self.assertIsNotNone(frame_manager.blocknet_start_close_button)
        self.assertIsNotNone(frame_manager.blockdx_start_close_button)
        self.assertIsNotNone(frame_manager.xlite_toggle_execution_button)
        self.assertIsNotNone(frame_manager.bots_toggle_execution_button)