"""Tests for gui/blocknet_frame_manager.py"""
from unittest.mock import Mock, patch, MagicMock
import pytest
import customtkinter as ctk
from gui.blocknet_frame_manager import BlocknetCoreFrameManager
from gui import constants
import widgets_strings


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_parent():
    """Create a mock parent object with minimal required attributes"""
    parent = Mock()
    parent.root_gui = Mock()
    parent.utility = Mock()
    parent.utility.data_folder = "/test/data"
    parent.utility.bootstrap_checking = False
    parent.utility.bootstrap_percent_download = None
    parent.utility.bootstrap_extracting = False
    parent.utility.blocknet_conf_local = None
    parent.utility.xbridge_conf_local = None
    parent.utility.valid_rpc = False
    parent.utility.check_data_folder_existence = Mock(return_value=False)

    # Make set_custom_data_path update data_folder
    def set_custom_data_path(path):
        parent.utility.data_folder = path

    parent.utility.set_custom_data_path = Mock(side_effect=set_custom_data_path)

    parent.blocknet_process_running = False
    parent.root_gui.install_img = Mock()
    parent.root_gui.install_greyed_img = Mock()
    parent.root_gui.transparent_img = Mock()
    parent.root_gui.custom_path = None
    parent.bootstrap_thread = None
    return parent


@pytest.fixture
def manager(mock_parent):
    """Create a BlocknetCoreFrameManager instance with mocked dependencies"""
    with patch('gui.blocknet_frame_manager.ctk.CTkFrame'), \
            patch('gui.blocknet_frame_manager.ctk.CTkLabel'), \
            patch('gui.blocknet_frame_manager.ctk.CTkEntry'), \
            patch('gui.blocknet_frame_manager.ctk.CTkButton'), \
            patch('gui.blocknet_frame_manager.ctkCheckBoxMod.CTkCheckBox'), \
            patch('gui.blocknet_frame_manager.ctk.StringVar') as mock_string_var, \
            patch('gui.blocknet_frame_manager.ctk.BooleanVar') as mock_boolean_var:
        # Create mock instances for each variable
        mock_string_var.return_value = Mock()
        mock_boolean_var.return_value = Mock()

        m = BlocknetCoreFrameManager(mock_parent)

        # Mock all the string and boolean variables
        m.download_bootstrap_string_var = Mock()
        m.data_path_status_checkbox_string_var = Mock()
        m.data_path_status_checkbox_state = Mock()
        m.process_status_checkbox_string_var = Mock()
        m.process_status_checkbox_state = Mock()
        m.conf_status_checkbox_string_var = Mock()
        m.conf_status_checkbox_state = Mock()
        m.rpc_connection_checkbox_string_var = Mock()
        m.rpc_connection_checkbox_state = Mock()
        m.data_path_entry_string_var = Mock()

        # Mock the widgets
        m.label = Mock()
        m.data_path_label = Mock()
        m.data_path_entry = Mock()
        m.custom_path_button = Mock()
        m.download_bootstrap_button = Mock()
        m.data_path_status_checkbox = Mock()
        m.process_status_checkbox = Mock()
        m.conf_status_checkbox = Mock()
        m.rpc_connection_checkbox = Mock()

        yield m


# ============================================================================
# TEST CLASSES
# ============================================================================

class TestBlocknetCoreFrameManager:
    """Test BlocknetCoreFrameManager class"""

    # -------------------------------------------------------------------------
    # INITIALIZATION TESTS
    # -------------------------------------------------------------------------

    def test_init(self, mock_parent):
        """Test initialization of BlocknetCoreFrameManager"""
        with patch('gui.blocknet_frame_manager.ctk.CTkFrame'), \
                patch('gui.blocknet_frame_manager.ctk.CTkLabel'), \
                patch('gui.blocknet_frame_manager.ctk.CTkEntry'), \
                patch('gui.blocknet_frame_manager.ctk.CTkButton'), \
                patch('gui.blocknet_frame_manager.ctkCheckBoxMod.CTkCheckBox'), \
                patch('gui.blocknet_frame_manager.ctk.StringVar') as mock_string_var, \
                patch('gui.blocknet_frame_manager.ctk.BooleanVar') as mock_boolean_var:
            mock_string_var.return_value = Mock()
            mock_boolean_var.return_value = Mock()

            manager = BlocknetCoreFrameManager(mock_parent)

            assert manager.root_gui == mock_parent.root_gui
            assert manager.parent == mock_parent

    # -------------------------------------------------------------------------
    # GRID WIDGETS TESTS
    # -------------------------------------------------------------------------

    def test_grid_widgets(self, manager):
        """Test grid_widgets method"""
        manager.grid_widgets(0, 0)

        # Verify all widgets were gridded
        manager.label.grid.assert_called_once()
        manager.data_path_label.grid.assert_called_once()
        manager.data_path_entry.grid.assert_called_once()
        manager.custom_path_button.grid.assert_called_once()
        manager.download_bootstrap_button.grid.assert_called_once()
        manager.data_path_status_checkbox.grid.assert_called_once()
        manager.process_status_checkbox.grid.assert_called_once()
        manager.conf_status_checkbox.grid.assert_called_once()
        manager.rpc_connection_checkbox.grid.assert_called_once()

    # -------------------------------------------------------------------------
    # BOOTSTRAP BUTTON UPDATE TESTS
    # -------------------------------------------------------------------------

    @patch('gui.blocknet_frame_manager.utils.enable_button')
    @patch('gui.blocknet_frame_manager.utils.disable_button')
    @pytest.mark.parametrize("bootstrap_checking,bootstrap_percent_download,bootstrap_extracting,expected_text", [
        (True, None, None, "Loading"),  # Checking but no progress
        (True, 50.5, None, "50.5%"),  # Downloading with percentage
        (True, None, True, "Unpacking"),  # Extracting
    ])
    def test_update_blocknet_bootstrap_button_downloading_states(
            self, mock_disable, mock_enable, manager, mock_parent,
            bootstrap_checking, bootstrap_percent_download, bootstrap_extracting, expected_text
    ):
        """Test update_blocknet_bootstrap_button in various downloading states"""
        mock_parent.utility.bootstrap_checking = bootstrap_checking
        mock_parent.utility.bootstrap_percent_download = bootstrap_percent_download
        mock_parent.utility.bootstrap_extracting = bootstrap_extracting

        manager.update_blocknet_bootstrap_button()

        mock_disable.assert_called_once_with(manager.download_bootstrap_button,
                                             img=mock_parent.root_gui.install_greyed_img)
        mock_enable.assert_not_called()

        # Verify the correct text was set
        assert any(call[0][0] == expected_text for call in manager.download_bootstrap_string_var.set.call_args_list)

    @patch('gui.blocknet_frame_manager.utils.enable_button')
    @patch('gui.blocknet_frame_manager.utils.disable_button')
    def test_update_blocknet_bootstrap_button_enabled(self, mock_disable, mock_enable, manager, mock_parent):
        """Test update_blocknet_bootstrap_button when enabled"""
        mock_parent.utility.bootstrap_checking = False
        mock_parent.utility.data_folder = "/test/data"
        mock_parent.blocknet_process_running = False

        manager.update_blocknet_bootstrap_button()

        mock_enable.assert_called_once_with(manager.download_bootstrap_button, img=mock_parent.root_gui.install_img)
        mock_disable.assert_not_called()
        manager.download_bootstrap_string_var.set.assert_called_once_with("Bootstrap")

    # -------------------------------------------------------------------------
    # PROCESS STATUS CHECKBOX TESTS
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("process_running,expected_text,expected_state", [
        (True, widgets_strings.blocknet_running_string, True),
        (False, widgets_strings.blocknet_not_running_string, False),
    ])
    def test_update_blocknet_process_status_checkbox(
            self, manager, mock_parent, process_running, expected_text, expected_state
    ):
        """Test update_blocknet_process_status_checkbox for both running and not running states"""
        mock_parent.blocknet_process_running = process_running

        manager.update_blocknet_process_status_checkbox()

        manager.process_status_checkbox_string_var.set.assert_called_once_with(expected_text)
        manager.process_status_checkbox_state.set.assert_called_once_with(expected_state)

    # -------------------------------------------------------------------------
    # CUSTOM PATH BUTTON UPDATE TESTS
    # -------------------------------------------------------------------------

    @patch('gui.blocknet_frame_manager.utils.enable_button')
    @patch('gui.blocknet_frame_manager.utils.disable_button')
    @pytest.mark.parametrize("blocknet_process_running,bootstrap_checking,bootstrap_percent_download,should_enable", [
        (False, False, None, True),  # Enabled: no process, no bootstrap
        (True, False, None, False),  # Disabled: process running
        (False, True, None, False),  # Disabled: bootstrap checking
        (False, False, 50.5, False),  # Disabled: bootstrap downloading
    ])
    def test_update_blocknet_custom_path_button(
            self, mock_disable, mock_enable, manager, mock_parent,
            blocknet_process_running, bootstrap_checking, bootstrap_percent_download, should_enable
    ):
        """Test update_blocknet_custom_path_button for all states"""
        mock_parent.blocknet_process_running = blocknet_process_running
        mock_parent.utility.bootstrap_checking = bootstrap_checking
        mock_parent.utility.bootstrap_percent_download = bootstrap_percent_download

        manager.update_blocknet_custom_path_button()

        if should_enable:
            mock_enable.assert_called_once_with(manager.custom_path_button)
            mock_disable.assert_not_called()
        else:
            mock_disable.assert_called_once_with(manager.custom_path_button)
            mock_enable.assert_not_called()

    # -------------------------------------------------------------------------
    # CONFIG STATUS CHECKBOX TESTS
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("blocknet_conf_local,xbridge_conf_local,expected_text,expected_state", [
        ({"global": {}}, {"Main": {}}, widgets_strings.blocknet_valid_config_string, True),
        (None, None, widgets_strings.blocknet_not_valid_config_string, False),
        ({"global": {}}, None, widgets_strings.blocknet_not_valid_config_string, False),
        (None, {"Main": {}}, widgets_strings.blocknet_not_valid_config_string, False),
    ])
    def test_update_blocknet_conf_status_checkbox(
            self, manager, mock_parent, blocknet_conf_local, xbridge_conf_local, expected_text, expected_state
    ):
        """Test update_blocknet_conf_status_checkbox for all config states"""
        mock_parent.utility.blocknet_conf_local = blocknet_conf_local
        mock_parent.utility.xbridge_conf_local = xbridge_conf_local

        manager.update_blocknet_conf_status_checkbox()

        manager.conf_status_checkbox_string_var.set.assert_called_once_with(expected_text)
        manager.conf_status_checkbox_state.set.assert_called_once_with(expected_state)

    # -------------------------------------------------------------------------
    # DATA PATH STATUS CHECKBOX TESTS
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("path_exists,expected_text,expected_state", [
        (True, widgets_strings.blocknet_data_path_created_string, True),
        (False, widgets_strings.blocknet_data_path_notfound_string, False),
    ])
    def test_update_blocknet_data_path_status_checkbox(
            self, manager, mock_parent, path_exists, expected_text, expected_state
    ):
        """Test update_blocknet_data_path_status_checkbox for both existing and non-existing paths"""
        mock_parent.utility.check_data_folder_existence = Mock(return_value=path_exists)

        manager.update_blocknet_data_path_status_checkbox()

        manager.data_path_status_checkbox_string_var.set.assert_called_once_with(expected_text)
        manager.data_path_status_checkbox_state.set.assert_called_once_with(expected_state)

    # -------------------------------------------------------------------------
    # RPC CONNECTION CHECKBOX TESTS
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("valid_rpc,expected_text,expected_state", [
        (True, widgets_strings.blocknet_active_rpc_string, True),
        (False, widgets_strings.blocknet_inactive_rpc_string, False),
    ])
    def test_update_blocknet_rpc_connection_checkbox(
            self, manager, mock_parent, valid_rpc, expected_text, expected_state
    ):
        """Test update_blocknet_rpc_connection_checkbox for both valid and invalid RPC states"""
        mock_parent.utility.valid_rpc = valid_rpc

        manager.update_blocknet_rpc_connection_checkbox()

        manager.rpc_connection_checkbox_string_var.set.assert_called_once_with(expected_text)
        manager.rpc_connection_checkbox_state.set.assert_called_once_with(expected_state)

    # -------------------------------------------------------------------------
    # CUSTOM PATH SET TESTS
    # -------------------------------------------------------------------------

    @patch('gui.blocknet_frame_manager.utils.save_cfg_json')
    @pytest.mark.parametrize("existing_custom_path", [None, "/existing/path"])
    def test_on_custom_path_set(self, mock_save_cfg_json, manager, mock_parent, existing_custom_path):
        """Test on_custom_path_set for both new and existing custom paths"""
        mock_parent.custom_path = existing_custom_path
        custom_path = "/new/custom/path"

        manager.on_custom_path_set(custom_path)

        mock_parent.utility.set_custom_data_path.assert_called_once_with(custom_path)
        # Check that set was called with the custom path (may have been called during init too)
        assert any(call[0][0] == custom_path for call in manager.data_path_entry_string_var.set.call_args_list)
        assert mock_parent.custom_path == custom_path
        mock_save_cfg_json.assert_called_once_with('custom_path', custom_path)

    # -------------------------------------------------------------------------
    # CUSTOM PATH DIALOG TESTS
    # -------------------------------------------------------------------------

    @patch('gui.blocknet_frame_manager.utils.save_cfg_json')
    @patch('gui.blocknet_frame_manager.ctk.filedialog.askdirectory')
    @patch('gui.blocknet_frame_manager.global_variables')
    @patch('gui.blocknet_frame_manager.os.path.exists')
    @patch('gui.blocknet_frame_manager.os.path.expandvars')
    @patch('gui.blocknet_frame_manager.os.path.expanduser')
    @pytest.mark.parametrize(
        "custom_path,blocknet_default_paths,system,expanduser_return,expandvars_return,exists_side_effect,expected_initialdir",
        [
            # No custom path, default exists
            (None, {"Linux": "/default/path"}, "Linux", "/default/path", "/default/path", [True], "/default/path"),
            # No custom path, default doesn't exist but parent does
            (None, {"Linux": "/default/path/subfolder"}, "Linux", "/default/path/subfolder", "/default/path/subfolder",
             [False, True], "/default/path"),
            # No custom path, no default path
            (None, {}, "Linux", None, None, None, None),
            # Existing custom path
            ("/existing/custom/path", None, None, None, None, None, "/existing/custom/path"),
        ])
    def test_open_custom_path_dialog(
            self, mock_expanduser, mock_expandvars, mock_exists, mock_global, mock_askdirectory, mock_save_cfg_json,
            manager, mock_parent, custom_path, blocknet_default_paths, system, expanduser_return, expandvars_return,
            exists_side_effect, expected_initialdir
    ):
        """Test open_custom_path_dialog for all path scenarios"""
        mock_parent.root_gui.custom_path = custom_path
        if blocknet_default_paths is not None:
            mock_global.conf_data.blocknet_default_paths = blocknet_default_paths
        if system is not None:
            mock_global.system = system
        if expanduser_return is not None:
            mock_expanduser.return_value = expanduser_return
        if expandvars_return is not None:
            mock_expandvars.return_value = expandvars_return
        if exists_side_effect is not None:
            mock_exists.side_effect = exists_side_effect

        mock_askdirectory.return_value = "/selected/path"

        manager.open_custom_path_dialog()

        mock_askdirectory.assert_called_once_with(
            parent=mock_parent.root_gui,
            title="Select Custom Path for Blocknet Core Datadir",
            mustexist=False,
            initialdir=expected_initialdir
        )
        mock_parent.utility.set_custom_data_path.assert_called_once_with("/selected/path")
        # Check that set was called with the selected path (may have been called during init too)
        assert any(call[0][0] == "/selected/path" for call in manager.data_path_entry_string_var.set.call_args_list)
        assert mock_parent.custom_path == "/selected/path"
        mock_save_cfg_json.assert_called_once_with('custom_path', '/selected/path')

    # -------------------------------------------------------------------------
    # DOWNLOAD BOOTSTRAP COMMAND TESTS
    # -------------------------------------------------------------------------

    @patch('gui.blocknet_frame_manager.utils.disable_button')
    @patch('gui.blocknet_frame_manager.Thread')
    def test_download_bootstrap_command(self, mock_thread, mock_disable_button, manager, mock_parent):
        """Test download_bootstrap_command method"""
        manager.download_bootstrap_command()

        mock_disable_button.assert_called_once_with(manager.download_bootstrap_button,
                                                    img=mock_parent.root_gui.install_greyed_img)
        mock_thread.assert_called_once_with(target=mock_parent.utility.download_bootstrap, daemon=True)
        assert mock_parent.bootstrap_thread == mock_thread.return_value
        mock_thread.return_value.start.assert_called_once()
