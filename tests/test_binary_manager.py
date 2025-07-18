import unittest
import os
import sys
from unittest.mock import MagicMock, patch, call
from threading import Thread
import time
import asyncio
from watchdog.events import FileSystemEvent

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gui.binary_manager import BinaryManager, BinaryFileHandler
from utilities import utils, global_variables
import widgets_strings
import customtkinter as ctk

class TestBinaryManager(unittest.TestCase):
    def setUp(self):
        # Reset mocks for a clean state in each test
        if hasattr(self, 'mock_utils'):
            self.mock_utils.reset_mock()
        if hasattr(self, 'mock_root_gui') and hasattr(self.mock_root_gui, 'tooltip_manager'):
            self.mock_root_gui.tooltip_manager.reset_mock()

        # Mock global_variables and utils
        self.mock_global_variables = MagicMock()
        self.mock_global_variables.aio_folder = "/mock/aio_folder"
        self.mock_global_variables.blocknet_release_url = "http://mock.com/blocknet"
        self.mock_global_variables.blockdx_release_url = "http://mock.com/blockdx"
        self.mock_global_variables.xlite_release_url = "http://mock.com/xlite"
        self.mock_global_variables.system = "Linux" # Default system for testing
        self.mock_global_variables.blockdx_curpath = "BLOCK-DX-1.0.0"
        self.mock_global_variables.xlite_curpath = "XLite-1.0.0"
        self.mock_global_variables.conf_data.blocknet_bin_path = ["blocknet-4.4.1"]

        # Mock root_gui and its managers
        self.mock_root_gui = MagicMock(spec=ctk.CTk)
        self.mock_root_gui.time_disable_button = 3000
        self.mock_root_gui.tooltip_manager = MagicMock()

        # Explicitly mock utility objects for managers
        self.mock_root_gui.blocknet_manager = MagicMock()
        self.mock_root_gui.blocknet_manager.utility = MagicMock()
        self.mock_root_gui.blockdx_manager = MagicMock()
        self.mock_root_gui.blockdx_manager.utility = MagicMock()
        self.mock_root_gui.xlite_manager = MagicMock()
        self.mock_root_gui.xlite_manager.utility = MagicMock()

        # Mock images
        self.mock_root_gui.install_greyed_img = MagicMock()
        self.mock_root_gui.install_img = MagicMock()
        self.mock_root_gui.delete_greyed_img = MagicMock()
        self.mock_root_gui.delete_img = MagicMock()
        self.mock_root_gui.stop_greyed_img = MagicMock()
        self.mock_root_gui.stop_img = MagicMock()
        self.mock_root_gui.start_greyed_img = MagicMock()
        self.mock_root_gui.start_img = MagicMock()

        # Patch global variables and utils
        self.patcher_global_variables = patch('gui.binary_manager.global_variables', new=self.mock_global_variables)
        self.patcher_utils = patch('gui.binary_manager.utils', new=MagicMock(spec=utils))
        self.patcher_os_listdir = patch('os.listdir', return_value=[])
        self.patcher_os_path_isdir = patch('os.path.isdir', return_value=True)
        self.patcher_os_path_isfile = patch('os.path.isfile', return_value=False) # Default to False, specific tests will override
        self.patcher_os_path_exists = patch('os.path.exists', return_value=True)
        self.patcher_os_makedirs = patch('os.makedirs')
        self.patcher_shutil_rmtree = patch('shutil.rmtree')
        self.patcher_os_remove = patch('os.remove')
        self.patcher_thread = patch('gui.binary_manager.Thread')
        self.patcher_observer = patch('gui.binary_manager.Observer')
        self.patcher_binary_file_handler = patch('gui.binary_manager.BinaryFileHandler')

        self.mock_global_variables = self.patcher_global_variables.start()
        self.mock_utils = self.patcher_utils.start()
        self.mock_os_listdir = self.patcher_os_listdir.start()
        self.mock_os_path_isdir = self.patcher_os_path_isdir.start()
        self.mock_os_path_isfile = self.patcher_os_path_isfile.start()
        self.mock_os_path_exists = self.patcher_os_path_exists.start()
        self.mock_os_makedirs = self.patcher_os_makedirs.start()
        self.mock_shutil_rmtree = self.patcher_shutil_rmtree.start()
        self.mock_os_remove = self.patcher_os_remove.start()
        self.mock_thread = self.patcher_thread.start()
        self.mock_observer = self.patcher_observer.start()
        self.mock_binary_file_handler = self.patcher_binary_file_handler.start()
        self.mock_observer.return_value.schedule = MagicMock()
        self.mock_observer.return_value.start = MagicMock()

        # Initialize BinaryManager
        self.binary_manager = BinaryManager(self.mock_root_gui)
        self.binary_manager.frame_manager = MagicMock() # Mock frame_manager after init
        self.binary_manager.frame_manager.parent = self.binary_manager # Mock parent for frame_manager

        # Set up mock boolvars for frame_manager
        self.binary_manager.frame_manager.blocknet_installed_boolvar = MagicMock(spec=ctk.BooleanVar)
        self.binary_manager.frame_manager.blockdx_installed_boolvar = MagicMock(spec=ctk.BooleanVar)
        self.binary_manager.frame_manager.xlite_installed_boolvar = MagicMock(spec=ctk.BooleanVar)
        self.binary_manager.frame_manager.blocknet_installed_boolvar.get.return_value = False
        self.binary_manager.frame_manager.blockdx_installed_boolvar.get.return_value = False
        self.binary_manager.frame_manager.xlite_installed_boolvar.get.return_value = False

        self.binary_manager.frame_manager.install_delete_blocknet_button = MagicMock()
        self.binary_manager.frame_manager.install_delete_blockdx_button = MagicMock()
        self.binary_manager.frame_manager.install_delete_xlite_button = MagicMock()

        self.binary_manager.frame_manager.install_delete_blocknet_string_var = MagicMock()
        self.binary_manager.frame_manager.install_delete_blockdx_string_var = MagicMock()
        self.binary_manager.frame_manager.install_delete_xlite_string_var = MagicMock()

        self.binary_manager.frame_manager.blocknet_start_close_button = MagicMock()
        self.binary_manager.frame_manager.blockdx_start_close_button = MagicMock()
        self.binary_manager.frame_manager.xlite_toggle_execution_button = MagicMock()

        self.binary_manager.frame_manager.blocknet_start_close_button_string_var = MagicMock()
        self.binary_manager.frame_manager.blockdx_start_close_button_string_var = MagicMock()
        self.binary_manager.frame_manager.xlite_toggle_execution_string_var = MagicMock()

        # Mock manager versions and process running states
        self.mock_root_gui.blocknet_manager.version = ["v4.4.1"]
        self.mock_root_gui.blockdx_manager.version = ["v1.0.0"]
        self.mock_root_gui.xlite_manager.version = ["v1.0.0"]

        self.mock_root_gui.blocknet_manager.blocknet_process_running = False
        self.mock_root_gui.blockdx_manager.process_running = False
        self.mock_root_gui.xlite_manager.process_running = False

        self.mock_root_gui.blocknet_manager.utility.downloading_bin = False
        self.mock_root_gui.blockdx_manager.utility.downloading_bin = False
        self.mock_root_gui.xlite_manager.utility.downloading_bin = False

        self.mock_root_gui.blocknet_manager.utility.bootstrap_checking = False
        self.mock_root_gui.blocknet_manager.utility.valid_rpc = True

        self.mock_root_gui.blocknet_manager.utility.binary_percent_download = None
        self.mock_root_gui.blockdx_manager.utility.binary_percent_download = None
        self.mock_root_gui.xlite_manager.utility.binary_percent_download = None

    def tearDown(self):
        self.patcher_global_variables.stop()
        self.patcher_utils.stop()
        self.patcher_os_listdir.stop()
        self.patcher_os_path_isdir.stop()
        self.patcher_os_path_isfile.stop()
        self.patcher_os_path_exists.stop()
        self.patcher_os_makedirs.stop()
        self.patcher_shutil_rmtree.stop()
        self.patcher_os_remove.stop()
        self.patcher_thread.stop()
        self.patcher_observer.stop()
        self.patcher_binary_file_handler.stop()

    def test_init(self):
        self.assertIsNotNone(self.binary_manager.root_gui)
        self.assertFalse(self.binary_manager.disable_start_blocknet_button)
        self.assertFalse(self.binary_manager.disable_start_xlite_button)
        self.assertFalse(self.binary_manager.disable_start_blockdx_button)
        self.mock_observer.return_value.schedule.assert_called_once_with(
            self.binary_manager.handler, self.mock_global_variables.aio_folder, recursive=False
        )
        self.mock_observer.return_value.start.assert_called_once()

    def test_setup(self):
        with patch('gui.binary_manager.BinaryFrameManager') as MockBinaryFrameManager:
            asyncio.run(self.binary_manager.setup())
            MockBinaryFrameManager.assert_called_once_with(self.binary_manager)
            self.mock_root_gui.after.assert_has_calls([
                call(0, self.binary_manager.check_and_update_aio_folder),
                call(0, self.binary_manager.update_all_binary_buttons),
                call(0, self.binary_manager.update_xbridge_bots_buttons)
            ])

    @patch('gui.binary_manager.Thread')
    def test_start_or_close_binary_start(self, mock_thread):
        # Test starting a binary
        self.binary_manager._start_or_close_binary(
            process_running=False,
            stop_func=MagicMock(),
            start_func=MagicMock(),
            button=self.binary_manager.frame_manager.blocknet_start_close_button,
            disable_flag='disable_start_blocknet_button'
        )
        self.mock_utils.disable_button.assert_called_with(
            self.binary_manager.frame_manager.blocknet_start_close_button,
            img=self.mock_root_gui.start_greyed_img
        )
        self.assertTrue(self.binary_manager.disable_start_blocknet_button)
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()
        self.mock_root_gui.after.assert_called_once_with(
            self.mock_root_gui.time_disable_button,
            self.binary_manager._enable_binary_start_button,
            'disable_start_blocknet_button'
        )

    @patch('gui.binary_manager.Thread')
    def test_start_or_close_binary_stop(self, mock_thread):
        # Test stopping a binary
        self.binary_manager._start_or_close_binary(
            process_running=True,
            stop_func=MagicMock(),
            start_func=MagicMock(),
            button=self.binary_manager.frame_manager.blocknet_start_close_button,
            disable_flag='disable_start_blocknet_button'
        )
        self.mock_utils.disable_button.assert_called_with(
            self.binary_manager.frame_manager.blocknet_start_close_button,
            img=self.mock_root_gui.stop_greyed_img
        )
        self.assertTrue(self.binary_manager.disable_start_blocknet_button)
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()
        self.mock_root_gui.after.assert_called_once_with(
            self.mock_root_gui.time_disable_button,
            self.binary_manager._enable_binary_start_button,
            'disable_start_blocknet_button'
        )

    def test_enable_binary_start_button(self):
        self.binary_manager.disable_start_blocknet_button = True
        self.binary_manager._enable_binary_start_button('disable_start_blocknet_button')
        self.assertFalse(self.binary_manager.disable_start_blocknet_button)

    @patch.object(BinaryManager, '_start_or_close_binary')
    def test_start_or_close_blocknet(self, mock_start_or_close_binary):
        self.mock_root_gui.blocknet_manager.blocknet_process_running = False
        self.binary_manager.start_or_close_blocknet()
        self.mock_root_gui.blocknet_manager.check_config.assert_called_once()
        mock_start_or_close_binary.assert_called_once_with(
            process_running=False,
            stop_func=self.mock_root_gui.blocknet_manager.utility.close_blocknet,
            start_func=self.mock_root_gui.blocknet_manager.utility.start_blocknet,
            button=self.binary_manager.frame_manager.blocknet_start_close_button,
            disable_flag='disable_start_blocknet_button'
        )

    @patch.object(BinaryManager, '_start_or_close_binary')
    def test_start_or_close_blockdx(self, mock_start_or_close_binary):
        self.mock_root_gui.blockdx_manager.process_running = False
        self.binary_manager.start_or_close_blockdx()
        self.mock_root_gui.blockdx_manager.blockdx_check_config.assert_called_once()
        mock_start_or_close_binary.assert_called_once_with(
            process_running=False,
            stop_func=self.mock_root_gui.blockdx_manager.utility.close_blockdx,
            start_func=self.mock_root_gui.blockdx_manager.utility.start_blockdx,
            button=self.binary_manager.frame_manager.blockdx_start_close_button,
            disable_flag='disable_start_blockdx_button'
        )

    @patch.object(BinaryManager, '_start_or_close_binary')
    def test_start_or_close_xlite(self, mock_start_or_close_binary):
        self.mock_root_gui.xlite_manager.process_running = False
        self.mock_root_gui.stored_password = "test_password"
        self.binary_manager.start_or_close_xlite()
        mock_start_or_close_binary.assert_called_once()
        args, kwargs = mock_start_or_close_binary.call_args
        self.assertFalse(kwargs['process_running'])
        self.assertEqual(kwargs['stop_func'], self.mock_root_gui.xlite_manager.utility.close_xlite)
        self.assertEqual(kwargs['button'], self.binary_manager.frame_manager.xlite_toggle_execution_button)
        self.assertEqual(kwargs['disable_flag'], 'disable_start_xlite_button')
        # Check the lambda function for start_func
        start_func_lambda = kwargs['start_func']
        start_func_lambda()
        self.mock_root_gui.xlite_manager.utility.start_xlite.assert_called_once_with(
            env_vars=['CC_WALLET_PASS=test_password', 'CC_WALLET_AUTOLOGIN=true']
        )

    def test_install_delete_blocknet_command_install(self):
        self.binary_manager.frame_manager.blocknet_installed_boolvar.get.return_value = False
        with patch.object(self.binary_manager, 'download_blocknet_command') as mock_download:
            self.binary_manager.install_delete_blocknet_command()
            mock_download.assert_called_once()

    def test_install_delete_blocknet_command_delete(self):
        self.binary_manager.frame_manager.blocknet_installed_boolvar.get.return_value = True
        with patch.object(self.binary_manager, 'delete_blocknet_command') as mock_delete:
            self.binary_manager.install_delete_blocknet_command()
            mock_delete.assert_called_once()

    def test_download_blocknet_command(self):
        self.binary_manager.download_blocknet_command()
        self.mock_utils.disable_button.assert_called_once_with(
            self.binary_manager.frame_manager.install_delete_blocknet_button,
            img=self.mock_root_gui.install_greyed_img
        )
        self.mock_thread.assert_called_once_with(
            target=self.mock_root_gui.blocknet_manager.utility.download_blocknet_bin,
            daemon=True
        )
        self.mock_thread.return_value.start.assert_called_once()

    def test_delete_blocknet_command(self):
        self.mock_root_gui.blocknet_manager.version = ["v4.4.1"]
        self.mock_os_listdir.return_value = ["blocknet-4.4.1", "other_folder"]
        self.mock_os_path_isdir.side_effect = lambda x: "blocknet-" in x or "other_folder" in x

        self.binary_manager.delete_blocknet_command()
        self.mock_shutil_rmtree.assert_called_once_with(
            os.path.join(self.mock_global_variables.aio_folder, "blocknet-4.4.1")
        )

    def test_install_delete_blockdx_command_install(self):
        self.binary_manager.frame_manager.blockdx_installed_boolvar.get.return_value = False
        with patch.object(self.binary_manager, 'download_blockdx_command') as mock_download:
            self.binary_manager.install_delete_blockdx_command()
            mock_download.assert_called_once()

    def test_install_delete_blockdx_command_delete(self):
        self.binary_manager.frame_manager.blockdx_installed_boolvar.get.return_value = True
        with patch.object(self.binary_manager, 'delete_blockdx_command') as mock_delete:
            self.binary_manager.install_delete_blockdx_command()
            mock_delete.assert_called_once()

    def test_download_blockdx_command(self):
        self.binary_manager.download_blockdx_command()
        self.mock_utils.disable_button.assert_called_once_with(
            self.binary_manager.frame_manager.install_delete_blockdx_button,
            img=self.mock_root_gui.install_greyed_img
        )
        self.mock_thread.assert_called_once_with(
            target=self.mock_root_gui.blockdx_manager.utility.download_blockdx_bin,
            daemon=True
        )
        self.mock_thread.return_value.start.assert_called_once()

    def test_delete_blockdx_command_linux(self):
        self.mock_global_variables.system = "Linux"
        self.mock_root_gui.blockdx_manager.version = ["v1.0.0"]
        self.mock_os_listdir.return_value = ["BLOCK-DX-1.0.0", "other_folder"]
        self.mock_os_path_isdir.side_effect = lambda x: "BLOCK-DX-" in x or "other_folder" in x

        self.binary_manager.delete_blockdx_command()
        self.mock_shutil_rmtree.assert_called_once_with(
            os.path.join(self.mock_global_variables.aio_folder, "BLOCK-DX-1.0.0")
        )

    def test_delete_blockdx_command_darwin(self):
        self.mock_global_variables.system = "Darwin"
        self.mock_global_variables.blockdx_release_url = "http://mock.com/blockdx/blockdx.dmg"
        self.mock_os_listdir.return_value = ["blockdx.dmg", "other_file"]
        self.mock_os_path_isfile.side_effect = lambda x: "blockdx.dmg" in x or "other_file" in x

        self.binary_manager.delete_blockdx_command()
        self.mock_root_gui.blockdx_manager.unmount_dmg.assert_called_once()
        self.mock_os_remove.assert_called_once_with(
            os.path.join(self.mock_global_variables.aio_folder, "blockdx.dmg")
        )

    def test_install_delete_xlite_command_install(self):
        self.binary_manager.frame_manager.xlite_installed_boolvar.get.return_value = False
        with patch.object(self.binary_manager, 'download_xlite_command') as mock_download:
            self.binary_manager.install_delete_xlite_command()
            mock_download.assert_called_once()

    def test_install_delete_xlite_command_delete(self):
        self.binary_manager.frame_manager.xlite_installed_boolvar.get.return_value = True
        with patch.object(self.binary_manager, 'delete_xlite_command') as mock_delete:
            self.binary_manager.install_delete_xlite_command()
            mock_delete.assert_called_once()

    def test_download_xlite_command(self):
        self.binary_manager.download_xlite_command()
        self.mock_utils.disable_button.assert_called_once_with(
            self.binary_manager.frame_manager.install_delete_xlite_button,
            img=self.mock_root_gui.install_greyed_img
        )
        self.mock_thread.assert_called_once_with(
            target=self.mock_root_gui.xlite_manager.utility.download_xlite_bin,
            daemon=True
        )
        self.mock_thread.return_value.start.assert_called_once()

    def test_delete_xlite_command_linux(self):
        self.mock_global_variables.system = "Linux"
        self.mock_root_gui.xlite_manager.version = ["v1.0.0"]
        self.mock_os_listdir.return_value = ["XLite-1.0.0", "other_folder"]
        self.mock_os_path_isdir.side_effect = lambda x: "XLite-" in x or "other_folder" in x

        self.binary_manager.delete_xlite_command()
        self.mock_shutil_rmtree.assert_called_once_with(
            os.path.join(self.mock_global_variables.aio_folder, "XLite-1.0.0")
        )

    def test_delete_xlite_command_darwin(self):
        self.mock_global_variables.system = "Darwin"
        self.mock_global_variables.xlite_release_url = "http://mock.com/xlite/xlite.dmg"
        self.mock_os_listdir.return_value = ["xlite.dmg", "other_file"]
        self.mock_os_path_isfile.side_effect = lambda x: "xlite.dmg" in x or "other_file" in x

        self.binary_manager.delete_xlite_command()
        self.mock_root_gui.xlite_manager.utility.unmount_dmg.assert_called_once()
        self.mock_os_remove.assert_called_once_with(
            os.path.join(self.mock_global_variables.aio_folder, "xlite.dmg")
        )

    def test_check_and_update_aio_folder_blocknet_found(self):
        self.mock_os_listdir.return_value = ["blocknet-4.4.1"]
        self.mock_os_path_isdir.return_value = True
        self.mock_root_gui.blocknet_manager.version = ["v4.4.1"]

        self.binary_manager.check_and_update_aio_folder()
        self.binary_manager.frame_manager.blocknet_installed_boolvar.set.assert_called_once_with(True)
        self.binary_manager.frame_manager.blockdx_installed_boolvar.set.assert_called_once_with(False)
        self.binary_manager.frame_manager.xlite_installed_boolvar.set.assert_called_once_with(False)

    def test_check_and_update_aio_folder_blockdx_found_linux(self):
        self.mock_global_variables.system = "Linux"
        self.mock_os_listdir.return_value = ["BLOCK-DX-1.0.0"]
        self.mock_os_path_isdir.return_value = True
        self.mock_root_gui.blockdx_manager.version = ["v1.0.0"]

        self.binary_manager.check_and_update_aio_folder()
        self.binary_manager.frame_manager.blocknet_installed_boolvar.set.assert_called_once_with(False)
        self.binary_manager.frame_manager.blockdx_installed_boolvar.set.assert_called_once_with(True)
        self.binary_manager.frame_manager.xlite_installed_boolvar.set.assert_called_once_with(False)

    def test_check_and_update_aio_folder_xlite_found_darwin(self):
        self.mock_global_variables.system = "Darwin"
        self.mock_global_variables.xlite_release_url = "http://mock.com/xlite/xlite.dmg"
        self.mock_os_listdir.return_value = ["xlite.dmg"]
        self.mock_os_path_isdir.return_value = False
        # Set mock_os_path_isfile to return True for xlite.dmg path
        self.mock_os_path_isfile.side_effect = lambda p: "xlite.dmg" in p
        self.mock_root_gui.xlite_manager.version = ["v1.0.0"]

        self.binary_manager.frame_manager.xlite_installed_boolvar.set.reset_mock()
        self.binary_manager.check_and_update_aio_folder()
        self.binary_manager.frame_manager.blocknet_installed_boolvar.set.assert_called_once_with(False)
        self.binary_manager.frame_manager.blockdx_installed_boolvar.set.assert_called_once_with(False)
        self.binary_manager.frame_manager.xlite_installed_boolvar.set.assert_called_once_with(True)

    def test_update_binary_buttons_blocknet_installed_running(self):
        self.binary_manager.frame_manager.blocknet_installed_boolvar.get.return_value = True
        self.mock_root_gui.blocknet_manager.blocknet_process_running = True
        self.binary_manager.update_binary_buttons("blocknet")

        self.binary_manager.frame_manager.blocknet_start_close_button_string_var.set.assert_called_once_with(widgets_strings.close_string)
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_any_call(
            widget=self.binary_manager.frame_manager.blocknet_start_close_button,
            msg=widgets_strings.close_string
        )
        self.mock_utils.enable_button.assert_any_call(
            self.binary_manager.frame_manager.blocknet_start_close_button,
            img=self.mock_root_gui.stop_img
        )
        self.mock_utils.disable_button.assert_any_call(
            self.binary_manager.frame_manager.install_delete_blocknet_button,
            img=self.mock_root_gui.delete_greyed_img
        )
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_any_call(
            widget=self.binary_manager.frame_manager.install_delete_blocknet_button,
            msg=os.path.join(self.mock_global_variables.aio_folder, self.mock_global_variables.conf_data.blocknet_bin_path[0])
        )
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_any_call(
            widget=self.binary_manager.frame_manager.blocknet_start_close_button,
            msg=widgets_strings.close_string
        )

    def test_update_binary_buttons_blocknet_not_installed_not_running(self):
        self.binary_manager.frame_manager.blocknet_installed_boolvar.get.return_value = False
        self.mock_root_gui.blocknet_manager.blocknet_process_running = False
        self.binary_manager.update_binary_buttons("blocknet")

        self.binary_manager.frame_manager.blocknet_start_close_button_string_var.set.assert_called_once_with(widgets_strings.start_string)
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_any_call(
            widget=self.binary_manager.frame_manager.blocknet_start_close_button,
            msg=widgets_strings.start_string
        )
        self.mock_utils.enable_button.assert_any_call( # Changed to assert_any_call
            self.binary_manager.frame_manager.blocknet_start_close_button,
            img=self.mock_root_gui.start_img
        )
        self.mock_utils.enable_button.assert_any_call( # Changed to assert_any_call
            self.binary_manager.frame_manager.install_delete_blocknet_button,
            img=self.mock_root_gui.install_img
        )
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_any_call(
            widget=self.binary_manager.frame_manager.install_delete_blocknet_button,
            msg=self.mock_global_variables.blocknet_release_url
        )
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_any_call(
            widget=self.binary_manager.frame_manager.blocknet_start_close_button,
            msg=widgets_strings.start_string
        )

    def test_update_all_binary_buttons(self):
        with patch.object(self.binary_manager, 'update_binary_buttons') as mock_update_binary_buttons:
            self.binary_manager.update_all_binary_buttons()
            mock_update_binary_buttons.assert_has_calls([
                call("blocknet"),
                call("blockdx"),
                call("xlite")
            ])
            self.mock_root_gui.after.assert_called_once_with(2000, self.binary_manager.update_all_binary_buttons)

    def test_update_blockdx_start_close_button_enabled(self):
        self.mock_root_gui.blockdx_manager.process_running = False
        self.mock_root_gui.blockdx_manager.utility.downloading_bin = False
        self.mock_root_gui.blocknet_manager.utility.valid_rpc = True # Ensure valid_rpc is True for this test
        self.binary_manager.disable_start_blockdx_button = False

        self.binary_manager.update_blockdx_start_close_button()

        self.binary_manager.frame_manager.blockdx_start_close_button_string_var.set.assert_called_once_with(widgets_strings.start_string)
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_called_once_with(
            widget=self.binary_manager.frame_manager.blockdx_start_close_button,
            msg=widgets_strings.start_string
        )
        self.mock_utils.enable_button.assert_called_once_with(
            self.binary_manager.frame_manager.blockdx_start_close_button,
            img=self.mock_root_gui.start_img
        )
        self.mock_utils.disable_button.assert_not_called()

    def test_update_blockdx_start_close_button_disabled_missing_rpc(self):
        self.mock_root_gui.blockdx_manager.process_running = False
        self.mock_root_gui.blockdx_manager.utility.downloading_bin = False
        self.mock_root_gui.blocknet_manager.utility.valid_rpc = False # This makes it disabled
        self.binary_manager.disable_start_blockdx_button = False

        self.binary_manager.update_blockdx_start_close_button()

        self.binary_manager.frame_manager.blockdx_start_close_button_string_var.set.assert_called_once_with(widgets_strings.start_string)
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_called_once_with(
            widget=self.binary_manager.frame_manager.blockdx_start_close_button,
            msg=widgets_strings.blockdx_missing_blocknet_config_string
        )
        self.mock_utils.disable_button.assert_called_once_with(
            self.binary_manager.frame_manager.blockdx_start_close_button,
            img=self.mock_root_gui.start_greyed_img
        )
        self.mock_utils.enable_button.assert_not_called()

    def test_update_xlite_start_close_button_enabled(self):
        self.mock_root_gui.xlite_manager.process_running = False
        self.mock_root_gui.xlite_manager.utility.downloading_bin = False
        self.binary_manager.disable_start_xlite_button = False

        self.binary_manager.update_xlite_start_close_button()

        self.binary_manager.frame_manager.xlite_toggle_execution_string_var.set.assert_called_once_with(widgets_strings.start_string)
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_called_once_with(
            widget=self.binary_manager.frame_manager.xlite_toggle_execution_button,
            msg=widgets_strings.start_string
        )
        self.mock_utils.enable_button.assert_called_once_with(
            self.binary_manager.frame_manager.xlite_toggle_execution_button,
            img=self.mock_root_gui.start_img
        )
        self.mock_utils.disable_button.assert_not_called()

    def test_update_xlite_start_close_button_disabled_downloading(self):
        self.mock_root_gui.xlite_manager.process_running = False
        self.mock_root_gui.xlite_manager.utility.downloading_bin = True # This makes it disabled
        self.binary_manager.disable_start_xlite_button = False

        self.binary_manager.update_xlite_start_close_button()

        self.binary_manager.frame_manager.xlite_toggle_execution_string_var.set.assert_called_once_with(widgets_strings.start_string)
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_called_once_with(
            widget=self.binary_manager.frame_manager.xlite_toggle_execution_button,
            msg=widgets_strings.start_string
        )
        self.mock_utils.disable_button.assert_called_once_with(
            self.binary_manager.frame_manager.xlite_toggle_execution_button,
            img=self.mock_root_gui.start_greyed_img
        )
        self.mock_utils.enable_button.assert_not_called()

    def test_binary_file_handler_on_modified_immediate_execution(self):
        handler = BinaryFileHandler(self.binary_manager)
        handler.last_run = time.time() - handler.max_delay - 1 # Ensure enough time has passed
        mock_event = MagicMock(spec=FileSystemEvent)
        mock_event.src_path = "/mock/path/file.txt"

        with patch.object(self.binary_manager, 'check_and_update_aio_folder') as mock_check_update:
            handler.on_modified(mock_event)
            mock_check_update.assert_called_once()
            self.assertFalse(handler.scheduled)

    def test_binary_file_handler_on_modified_scheduled_execution(self):
        handler = BinaryFileHandler(self.binary_manager)
        handler.last_run = time.time() - 1 # Less than max_delay
        mock_event = MagicMock(spec=FileSystemEvent)
        mock_event.src_path = "/mock/path/file.txt"

        with patch.object(self.binary_manager, 'check_and_update_aio_folder') as mock_check_update:
            handler.on_modified(mock_event)
            mock_check_update.assert_not_called()
            self.assertTrue(handler.scheduled)
            self.mock_root_gui.after.assert_called_once()
            # Manually call the scheduled function to test its execution
            call_args = self.mock_root_gui.after.call_args
            scheduled_func = call_args[0][1]
            scheduled_func()
            mock_check_update.assert_called_once()
            self.assertFalse(handler.scheduled)

    def test_binary_file_handler_on_modified_already_scheduled(self):
        handler = BinaryFileHandler(self.binary_manager)
        handler.scheduled = True
        handler.last_run = time.time() - 1 # Less than max_delay
        mock_event = MagicMock(spec=FileSystemEvent)
        mock_event.src_path = "/mock/path/file.txt"

        with patch.object(self.binary_manager, 'check_and_update_aio_folder') as mock_check_update:
            handler.on_modified(mock_event)
            mock_check_update.assert_not_called()
            self.mock_root_gui.after.assert_not_called()
            self.assertTrue(handler.scheduled) # Should remain scheduled