import asyncio
import os
import queue
import sys
import time
import unittest
from unittest.mock import MagicMock, patch, call

from watchdog.events import FileSystemEvent

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gui.binary_manager import BinaryManager, BinaryFileHandler
from utilities import utils
import widgets_strings
import customtkinter as ctk


class TestBinaryManager(unittest.TestCase):
    """Test suite for BinaryManager class."""

    def setUp(self):
        """Set up common mocks and BinaryManager instance for each test."""
        # Setup global variables mock
        self.mock_global_variables = MagicMock()
        self.mock_global_variables.aio_folder = "/mock/aio_folder"
        self.mock_global_variables.blocknet_release_url = "http://mock.com/blocknet"
        self.mock_global_variables.blockdx_release_url = "http://mock.com/blockdx"
        self.mock_global_variables.xlite_release_url = "http://mock.com/xlite"
        self.mock_global_variables.system = "Linux"
        self.mock_global_variables.blockdx_curpath = "BLOCK-DX-1.0.0"
        self.mock_global_variables.xlite_curpath = "XLite-1.0.0"
        self.mock_global_variables.conf_data.blocknet_bin_path = ["blocknet-4.4.1"]

        # Setup root_gui mock
        self.mock_root_gui = MagicMock(spec=ctk.CTk)
        self.mock_root_gui.time_disable_button = 3000
        self.mock_root_gui.tooltip_manager = MagicMock()

        # Setup manager mocks
        for manager_name in ['blocknet_manager', 'blockdx_manager', 'xlite_manager']:
            manager = MagicMock()
            manager.utility = MagicMock()
            manager.version = ["v4.4.1"] if manager_name == 'blocknet_manager' else ["v1.0.0"]
            setattr(self.mock_root_gui, manager_name, manager)

        # Setup process running states
        self.mock_root_gui.blocknet_manager.blocknet_process_running = False
        self.mock_root_gui.blockdx_manager.process_running = False
        self.mock_root_gui.xlite_manager.process_running = False

        # Setup download states
        for manager in [self.mock_root_gui.blocknet_manager,
                        self.mock_root_gui.blockdx_manager,
                        self.mock_root_gui.xlite_manager]:
            manager.utility.downloading_bin = False
            manager.utility.bootstrap_checking = False
            manager.utility.valid_rpc = True
            manager.utility.binary_percent_download = None

        # Setup image mocks
        for img_attr in ['install_greyed_img', 'install_img', 'delete_greyed_img',
                         'delete_img', 'stop_greyed_img', 'stop_img',
                         'start_greyed_img', 'start_img']:
            setattr(self.mock_root_gui, img_attr, MagicMock())

        # Setup patchers
        self.patcher_global_variables = patch('gui.binary_manager.global_variables',
                                              new=self.mock_global_variables)
        self.patcher_utils = patch('gui.binary_manager.utils', new=MagicMock(spec=utils))
        self.patcher_os_listdir = patch('os.listdir', return_value=[])
        self.patcher_os_path_isdir = patch('os.path.isdir', return_value=True)
        self.patcher_os_path_isfile = patch('os.path.isfile', return_value=False)
        self.patcher_os_path_exists = patch('os.path.exists', return_value=True)
        self.patcher_os_makedirs = patch('os.makedirs')
        self.patcher_shutil_rmtree = patch('shutil.rmtree')
        self.patcher_os_remove = patch('os.remove')
        self.patcher_thread = patch('gui.binary_manager.Thread')
        self.patcher_observer = patch('gui.binary_manager.Observer')
        self.patcher_binary_file_handler = patch('gui.binary_manager.BinaryFileHandler')
        self.patcher_os_stat = patch('gui.binary_manager.os.stat')

        # Start all patchers
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
        self.mock_os_stat = self.patcher_os_stat.start()

        # Configure observer mock
        self.mock_observer.return_value.schedule = MagicMock()
        self.mock_observer.return_value.start = MagicMock()
        self.mock_os_stat.return_value.st_mtime_ns = 123456789

        # Initialize BinaryManager
        self.binary_manager = BinaryManager(self.mock_root_gui)
        self.binary_manager.frame_manager = MagicMock()
        self.binary_manager.frame_manager.parent = self.binary_manager

        # Setup frame manager boolvars
        for binary in ['blocknet', 'blockdx', 'xlite']:
            boolvar = MagicMock(spec=ctk.BooleanVar)
            boolvar.get.return_value = False
            setattr(self.binary_manager.frame_manager, f'{binary}_installed_boolvar', boolvar)

        # Setup frame manager buttons and string vars
        for binary in ['blocknet', 'blockdx', 'xlite']:
            button_attr = f'{binary}_start_close_button' if binary != 'xlite' else 'xlite_toggle_execution_button'
            setattr(self.binary_manager.frame_manager, button_attr, MagicMock())
            setattr(self.binary_manager.frame_manager, f'{button_attr}_string_var', MagicMock())

        for binary in ['blocknet', 'blockdx', 'xlite']:
            setattr(self.binary_manager.frame_manager, f'install_delete_{binary}_button', MagicMock())
            setattr(self.binary_manager.frame_manager, f'install_delete_{binary}_string_var', MagicMock())

    def tearDown(self):
        """Clean up patchers and queue after each test."""
        patchers = [
            self.patcher_global_variables, self.patcher_utils, self.patcher_os_listdir,
            self.patcher_os_path_isdir, self.patcher_os_path_isfile, self.patcher_os_path_exists,
            self.patcher_os_makedirs, self.patcher_shutil_rmtree, self.patcher_os_remove,
            self.patcher_thread, self.patcher_observer, self.patcher_binary_file_handler,
            self.patcher_os_stat
        ]
        for patcher in patchers:
            patcher.stop()

        # Clean up any pending queue tasks
        try:
            while True:
                self.binary_manager.file_change_queue.get_nowait()
        except queue.Empty:
            pass

    # ==================== BinaryFileHandler Tests ====================

    def test_binary_file_handler_on_modified_immediate_execution(self):
        """Test BinaryFileHandler.on_modified with immediate execution."""
        mock_binary_manager = MagicMock()
        mock_binary_manager.file_change_queue = queue.Queue()
        handler = BinaryFileHandler(mock_binary_manager)
        handler.last_run = time.time() - handler.max_delay - 1
        mock_event = MagicMock(spec=FileSystemEvent)
        mock_event.src_path = "/mock/path/file.txt"

        handler.on_modified(mock_event)
        self.assertEqual(mock_binary_manager.file_change_queue.qsize(), 1)
        msg_type, delay_ms = mock_binary_manager.file_change_queue.get_nowait()
        self.assertEqual(msg_type, "delayed_update")
        self.assertEqual(delay_ms, 0)
        self.assertTrue(handler.scheduled)

    def test_binary_file_handler_on_modified_scheduled_execution(self):
        """Test BinaryFileHandler.on_modified with scheduled execution."""
        mock_binary_manager = MagicMock()
        mock_binary_manager.file_change_queue = queue.Queue()
        handler = BinaryFileHandler(mock_binary_manager)
        handler.last_run = time.time() - 1
        mock_event = MagicMock(spec=FileSystemEvent)
        mock_event.src_path = "/mock/path/file.txt"

        handler.on_modified(mock_event)
        self.assertEqual(mock_binary_manager.file_change_queue.qsize(), 1)
        msg_type, delay_ms = mock_binary_manager.file_change_queue.get_nowait()
        self.assertEqual(msg_type, "delayed_update")
        self.assertTrue(3950 <= delay_ms <= 4050, f"Expected delay between 3950 and 4050ms, got {delay_ms}ms")
        self.assertTrue(handler.scheduled)

    def test_binary_file_handler_on_modified_already_scheduled(self):
        """Test BinaryFileHandler.on_modified when already scheduled."""
        handler = BinaryFileHandler(self.binary_manager)
        handler.scheduled = True
        handler.last_run = time.time() - 1
        mock_event = MagicMock(spec=FileSystemEvent)
        mock_event.src_path = "/mock/path/file.txt"

        with patch.object(self.binary_manager, 'check_and_update_aio_folder') as mock_check_update:
            self.mock_root_gui.after.reset_mock()
            handler.on_modified(mock_event)
            mock_check_update.assert_not_called()
            self.assertFalse(self.mock_root_gui.after.called)
            self.assertTrue(handler.scheduled)
            self.assertEqual(self.binary_manager.file_change_queue.qsize(), 0)

    def test_binary_file_handler_schedule_delayed_task_main_thread(self):
        """Test BinaryFileHandler.schedule_delayed_task in main thread."""
        mock_binary_manager = MagicMock()
        mock_binary_manager.root_gui.after = MagicMock()
        handler = BinaryFileHandler(mock_binary_manager)

        with patch('gui.binary_manager.threading.current_thread') as mock_thread:
            mock_thread.return_value.name = 'MainThread'
            handler.schedule_delayed_task(1000)
            mock_binary_manager.root_gui.after.assert_called_once_with(1000, handler._execute_scheduled)

    def test_binary_file_handler_schedule_delayed_task_worker_thread(self):
        """Test BinaryFileHandler.schedule_delayed_task in worker thread."""
        import queue
        mock_binary_manager = MagicMock()
        mock_binary_manager.file_change_queue = queue.Queue()
        handler = BinaryFileHandler(mock_binary_manager)

        with patch('threading.current_thread') as mock_thread:
            mock_thread.return_thread.name = 'WorkerThread'
            handler.schedule_delayed_task(1000)
            self.assertEqual(mock_binary_manager.file_change_queue.qsize(), 1)
            msg_type, delay = mock_binary_manager.file_change_queue.get_nowait()
            self.assertEqual(msg_type, "delayed_task")
            self.assertEqual(delay, 1000)

    def test_binary_file_handler_execute_scheduled(self):
        """Test BinaryFileHandler._execute_scheduled method."""
        mock_binary_manager = MagicMock()
        mock_binary_manager.check_and_update_aio_folder = MagicMock()
        handler = BinaryFileHandler(mock_binary_manager)
        handler.scheduled = True

        with patch('time.time', return_value=1234567890):
            handler._execute_scheduled()
            mock_binary_manager.check_and_update_aio_folder.assert_called_once()
            self.assertEqual(handler.last_run, 1234567890)
            self.assertFalse(handler.scheduled)

    # ==================== BinaryManager Initialization Tests ====================

    def test_init(self):
        """Test BinaryManager initialization."""
        self.assertIsNotNone(self.binary_manager.root_gui)
        self.assertFalse(self.binary_manager.disable_start_blocknet_button)
        self.assertFalse(self.binary_manager.disable_start_xlite_button)
        self.assertFalse(self.binary_manager.disable_start_blockdx_button)
        self.mock_observer.return_value.schedule.assert_called_once_with(
            self.binary_manager.handler, self.mock_global_variables.aio_folder, recursive=False
        )
        self.mock_observer.return_value.start.assert_called_once()

    def test_setup(self):
        """Test BinaryManager setup method."""
        with patch('gui.binary_manager.BinaryFrameManager') as MockBinaryFrameManager:
            asyncio.run(self.binary_manager.setup())
            MockBinaryFrameManager.assert_called_once_with(self.binary_manager)
            self.mock_root_gui.after.assert_has_calls([
                call(0, self.binary_manager.check_and_update_aio_folder),
                call(0, self.binary_manager.update_all_binary_buttons),
                call(0, self.binary_manager.update_xbridge_bots_buttons)
            ])

    # ==================== Binary Start/Stop Tests ====================

    @patch('gui.binary_manager.Thread')
    def test_start_or_close_binary_start(self, mock_thread):
        """Test _start_or_close_binary when starting a binary."""
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
        self.assertEqual(self.mock_root_gui.after.call_count, 2)

    @patch('gui.binary_manager.Thread')
    def test_start_or_close_binary_stop(self, mock_thread):
        """Test _start_or_close_binary when stopping a binary."""
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
        self.assertEqual(self.mock_root_gui.after.call_count, 2)

    def test_enable_binary_start_button(self):
        """Test _enable_binary_start_button method."""
        self.binary_manager.disable_start_blocknet_button = True
        self.binary_manager._enable_binary_start_button('disable_start_blocknet_button')
        self.assertFalse(self.binary_manager.disable_start_blocknet_button)

    @patch.object(BinaryManager, '_start_or_close_binary')
    def test_start_or_close_blocknet(self, mock_start_or_close_binary):
        """Test start_or_close_blocknet method."""
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
        """Test start_or_close_blockdx method."""
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
        """Test start_or_close_xlite method."""
        self.mock_root_gui.xlite_manager.process_running = False
        self.mock_root_gui.stored_password = "test_password"
        self.binary_manager.start_or_close_xlite()
        mock_start_or_close_binary.assert_called_once()
        args, kwargs = mock_start_or_close_binary.call_args
        self.assertFalse(kwargs['process_running'])
        self.assertEqual(kwargs['stop_func'], self.mock_root_gui.xlite_manager.utility.close_xlite)
        self.assertEqual(kwargs['button'], self.binary_manager.frame_manager.xlite_toggle_execution_button)
        self.assertEqual(kwargs['disable_flag'], 'disable_start_xlite_button')
        start_func_lambda = kwargs['start_func']
        start_func_lambda()
        self.mock_root_gui.xlite_manager.utility.start_xlite.assert_called_once_with(
            env_vars=['CC_WALLET_PASS=test_password', 'CC_WALLET_AUTOLOGIN=true']
        )

    # ==================== Install/Delete Command Tests ====================

    def test_install_delete_blocknet_command_install(self):
        """Test install_delete_blocknet_command when installing."""
        self.binary_manager.frame_manager.blocknet_installed_boolvar.get.return_value = False
        with patch.object(self.binary_manager, 'download_blocknet_command') as mock_download:
            self.binary_manager.install_delete_blocknet_command()
            mock_download.assert_called_once()

    def test_install_delete_blocknet_command_delete(self):
        """Test install_delete_blocknet_command when deleting."""
        self.binary_manager.frame_manager.blocknet_installed_boolvar.get.return_value = True
        with patch.object(self.binary_manager, 'delete_blocknet_command') as mock_delete:
            self.binary_manager.install_delete_blocknet_command()
            mock_delete.assert_called_once()

    def test_download_blocknet_command(self):
        """Test download_blocknet_command method."""
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
        """Test delete_blocknet_command method."""
        self.mock_root_gui.blocknet_manager.version = ["v4.4.1"]
        self.mock_os_listdir.return_value = ["blocknet-4.4.1", "other_folder"]
        self.mock_os_path_isdir.side_effect = lambda x: "blocknet-" in x or "other_folder" in x

        self.binary_manager.delete_blocknet_command()
        self.mock_shutil_rmtree.assert_called_once_with(
            os.path.join(self.mock_global_variables.aio_folder, "blocknet-4.4.1")
        )

    def test_install_delete_blockdx_command_install(self):
        """Test install_delete_blockdx_command when installing."""
        self.binary_manager.frame_manager.blockdx_installed_boolvar.get.return_value = False
        with patch.object(self.binary_manager, 'download_blockdx_command') as mock_download:
            self.binary_manager.install_delete_blockdx_command()
            mock_download.assert_called_once()

    def test_install_delete_blockdx_command_delete(self):
        """Test install_delete_blockdx_command when deleting."""
        self.binary_manager.frame_manager.blockdx_installed_boolvar.get.return_value = True
        with patch.object(self.binary_manager, 'delete_blockdx_command') as mock_delete:
            self.binary_manager.install_delete_blockdx_command()
            mock_delete.assert_called_once()

    def test_download_blockdx_command(self):
        """Test download_blockdx_command method."""
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
        """Test delete_blockdx_command on Linux."""
        self.mock_global_variables.system = "Linux"
        self.mock_root_gui.blockdx_manager.version = ["v1.0.0"]
        self.mock_os_listdir.return_value = ["BLOCK-DX-1.0.0", "other_folder"]
        self.mock_os_path_isdir.side_effect = lambda x: "BLOCK-DX-" in x or "other_folder" in x

        self.binary_manager.delete_blockdx_command()
        self.mock_shutil_rmtree.assert_called_once_with(
            os.path.join(self.mock_global_variables.aio_folder, "BLOCK-DX-1.0.0")
        )

    def test_delete_blockdx_command_darwin(self):
        """Test delete_blockdx_command on Darwin (macOS)."""
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
        """Test install_delete_xlite_command when installing."""
        self.binary_manager.frame_manager.xlite_installed_boolvar.get.return_value = False
        with patch.object(self.binary_manager, 'download_xlite_command') as mock_download:
            self.binary_manager.install_delete_xlite_command()
            mock_download.assert_called_once()

    def test_install_delete_xlite_command_delete(self):
        """Test install_delete_xlite_command when deleting."""
        self.binary_manager.frame_manager.xlite_installed_boolvar.get.return_value = True
        with patch.object(self.binary_manager, 'delete_xlite_command') as mock_delete:
            self.binary_manager.install_delete_xlite_command()
            mock_delete.assert_called_once()

    def test_download_xlite_command(self):
        """Test download_xlite_command method."""
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
        """Test delete_xlite_command on Linux."""
        self.mock_global_variables.system = "Linux"
        self.mock_root_gui.xlite_manager.version = ["v1.0.0"]
        self.mock_os_listdir.return_value = ["XLite-1.0.0", "other_folder"]
        self.mock_os_path_isdir.side_effect = lambda x: "XLite-" in x or "other_folder" in x

        self.binary_manager.delete_xlite_command()
        self.mock_shutil_rmtree.assert_called_once_with(
            os.path.join(self.mock_global_variables.aio_folder, "XLite-1.0.0")
        )

    def test_delete_xlite_command_darwin(self):
        """Test delete_xlite_command on Darwin (macOS)."""
        self.mock_global_variables.system = "Darwin"
        self.mock_global_variables.xlite_release_url = "http://mock.com/xlite/xlite.dmg"
        self.mock_os_listdir.return_value = ["xlite.dmg", "other_file"]
        self.mock_os_path_isfile.side_effect = lambda x: "xlite.dmg" in x or "other_file" in x

        self.binary_manager.delete_xlite_command()
        self.mock_root_gui.xlite_manager.utility.unmount_dmg.assert_called_once()
        self.mock_os_remove.assert_called_once_with(
            os.path.join(self.mock_global_variables.aio_folder, "xlite.dmg")
        )

    # ==================== Folder Scanning Tests ====================

    def test_check_and_update_aio_folder_blocknet_found(self):
        """Test check_and_update_aio_folder when blocknet is found."""
        self.mock_os_listdir.return_value = ["blocknet-4.4.1"]
        self.mock_os_path_isdir.return_value = True
        self.mock_root_gui.blocknet_manager.version = ["v4.4.1"]

        self.binary_manager.check_and_update_aio_folder()
        self.binary_manager.frame_manager.blocknet_installed_boolvar.set.assert_called_once_with(True)
        self.binary_manager.frame_manager.blockdx_installed_boolvar.set.assert_called_once_with(False)
        self.binary_manager.frame_manager.xlite_installed_boolvar.set.assert_called_once_with(False)

    def test_check_and_update_aio_folder_blockdx_found_linux(self):
        """Test check_and_update_aio_folder when blockdx is found on Linux."""
        self.mock_global_variables.system = "Linux"
        self.mock_os_listdir.return_value = ["BLOCK-DX-1.0.0"]
        self.mock_os_path_isdir.return_value = True
        self.mock_root_gui.blockdx_manager.version = ["v1.0.0"]

        self.binary_manager.check_and_update_aio_folder()
        self.binary_manager.frame_manager.blocknet_installed_boolvar.set.assert_called_once_with(False)
        self.binary_manager.frame_manager.blockdx_installed_boolvar.set.assert_called_once_with(True)
        self.binary_manager.frame_manager.xlite_installed_boolvar.set.assert_called_once_with(False)

    def test_check_and_update_aio_folder_xlite_found_darwin(self):
        """Test check_and_update_aio_folder when xlite is found on Darwin."""
        self.mock_global_variables.system = "Darwin"
        self.mock_global_variables.xlite_release_url = "http://mock.com/xlite/xlite.dmg"
        self.mock_os_listdir.return_value = ["xlite.dmg"]
        self.mock_os_path_isdir.return_value = False
        self.mock_os_path_isfile.side_effect = lambda p: "xlite.dmg" in p
        self.mock_root_gui.xlite_manager.version = ["v1.0.0"]

        self.binary_manager.frame_manager.xlite_installed_boolvar.set.reset_mock()
        self.binary_manager.check_and_update_aio_folder()
        self.binary_manager.frame_manager.blocknet_installed_boolvar.set.assert_called_once_with(False)
        self.binary_manager.frame_manager.blockdx_installed_boolvar.set.assert_called_once_with(False)
        self.binary_manager.frame_manager.xlite_installed_boolvar.set.assert_called_once_with(True)

    def test_check_and_update_aio_folder_early_return(self):
        """Test check_and_update_aio_folder early return when mtime unchanged."""
        self.binary_manager.last_directory_mtime = 123456789
        self.mock_os_stat.return_value.st_mtime_ns = 123456789

        with patch.object(self.binary_manager, 'scan_directory_for_binaries') as mock_scan:
            self.binary_manager.check_and_update_aio_folder()
            mock_scan.assert_not_called()

    def test_check_and_update_aio_folder_incorrect_version(self):
        """Test check_and_update_aio_folder logs incorrect versions."""
        self.mock_os_listdir.return_value = ["blocknet-5.0.0"]  # Wrong version
        self.mock_os_path_isdir.return_value = True
        self.mock_root_gui.blocknet_manager.version = ["v4.4.1"]

        with patch('gui.binary_manager.logger') as mock_logger:
            self.binary_manager.check_and_update_aio_folder()
            mock_logger.info.assert_called()
            self.assertIn("incorrect version", mock_logger.info.call_args[0][0])

    def test_get_directory_mtime_fallback(self):
        """Test get_directory_mtime with fallback for FAT filesystems."""
        mock_stat = MagicMock()
        del mock_stat.st_mtime_ns  # Remove attribute to trigger fallback
        mock_stat.st_mtime = 1234567890.123

        with patch('os.stat', return_value=mock_stat):
            result = self.binary_manager.get_directory_mtime()
            # Allow small floating point differences
            self.assertAlmostEqual(result, 1234567890123000000, delta=1000000)

    def test_get_directory_mtime_oserror(self):
        """Test get_directory_mtime handles OSError."""
        with patch('os.stat', side_effect=OSError("Permission denied")):
            result = self.binary_manager.get_directory_mtime()
            self.assertEqual(result, 0)

    # ==================== Button Update Tests ====================

    def test_update_binary_buttons_blocknet_installed_running(self):
        """Test update_binary_buttons for blocknet when installed and running."""
        self.binary_manager.frame_manager.blocknet_installed_boolvar.get.return_value = True
        self.mock_root_gui.blocknet_manager.blocknet_process_running = True
        self.binary_manager.update_binary_buttons("blocknet")

        self.binary_manager.frame_manager.blocknet_start_close_button_string_var.set.assert_called_once_with(
            widgets_strings.close_string)
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

    def test_update_binary_buttons_blocknet_not_installed_not_running(self):
        """Test update_binary_buttons for blocknet when not installed and not running."""
        self.binary_manager.frame_manager.blocknet_installed_boolvar.get.return_value = False
        self.mock_root_gui.blocknet_manager.blocknet_process_running = False
        self.binary_manager.update_binary_buttons("blocknet")

        self.binary_manager.frame_manager.blocknet_start_close_button_string_var.set.assert_called_once_with(
            widgets_strings.start_string)
        self.mock_utils.enable_button.assert_any_call(
            self.binary_manager.frame_manager.blocknet_start_close_button,
            img=self.mock_root_gui.start_img
        )
        self.mock_utils.enable_button.assert_any_call(
            self.binary_manager.frame_manager.install_delete_blocknet_button,
            img=self.mock_root_gui.install_img
        )

    def test_update_binary_buttons_blockdx(self):
        """Test update_binary_buttons for blockdx."""
        # Set up conditions for _update_install_delete_button to call disable_button
        self.binary_manager.frame_manager.blockdx_installed_boolvar.get.return_value = False
        self.mock_root_gui.blockdx_manager.utility.downloading_bin = True

        with patch.object(self.binary_manager, 'update_blockdx_start_close_button') as mock_update:
            self.binary_manager.update_binary_buttons("blockdx")
            mock_update.assert_called_once()
            # Verify _update_install_delete_button was called (which calls disable_button)
            self.mock_utils.disable_button.assert_called()

    def test_update_binary_buttons_xlite(self):
        """Test update_binary_buttons for xlite."""
        # Set up conditions for _update_install_delete_button to call disable_button
        self.binary_manager.frame_manager.xlite_installed_boolvar.get.return_value = False
        self.mock_root_gui.xlite_manager.utility.downloading_bin = True

        with patch.object(self.binary_manager, 'update_xlite_start_close_button') as mock_update:
            self.binary_manager.update_binary_buttons("xlite")
            mock_update.assert_called_once()
            # Verify _update_install_delete_button was called (which calls disable_button)
            self.mock_utils.disable_button.assert_called()

    def test_update_all_binary_buttons(self):
        """Test update_all_binary_buttons method."""
        with patch.object(self.binary_manager, 'update_binary_buttons') as mock_update_binary_buttons:
            self.binary_manager.update_all_binary_buttons()
            mock_update_binary_buttons.assert_has_calls([
                call("blocknet"),
                call("blockdx"),
                call("xlite")
            ])
            self.assertEqual(self.mock_root_gui.after.call_count, 2)

    def test_update_all_binary_buttons_winfo_exists_false(self):
        """Test update_all_binary_buttons when winfo_exists returns False."""
        self.mock_root_gui.winfo_exists.return_value = False
        with patch.object(self.binary_manager, 'update_binary_buttons') as mock_update:
            self.binary_manager.update_all_binary_buttons()
            mock_update.assert_not_called()

    def test_update_all_binary_buttons_winfo_exists_true(self):
        """Test update_all_binary_buttons when winfo_exists returns True."""
        self.mock_root_gui.winfo_exists.return_value = True
        with patch.object(self.binary_manager, 'update_binary_buttons') as mock_update:
            self.binary_manager.update_all_binary_buttons()
            mock_update.assert_called()
            # Should schedule next update
            self.mock_root_gui.after.assert_called_with(2000, self.binary_manager.update_all_binary_buttons)

    # ==================== Start/Close Button Update Tests ====================

    def test_update_blockdx_start_close_button_enabled(self):
        """Test update_blockdx_start_close_button when enabled."""
        self.mock_root_gui.blockdx_manager.process_running = False
        self.mock_root_gui.blockdx_manager.utility.downloading_bin = False
        self.mock_root_gui.blocknet_manager.utility.valid_rpc = True
        self.binary_manager.disable_start_blockdx_button = False

        self.binary_manager.update_blockdx_start_close_button()

        self.binary_manager.frame_manager.blockdx_start_close_button_string_var.set.assert_called_once_with(
            widgets_strings.start_string)
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
        """Test update_blockdx_start_close_button when disabled due to missing RPC."""
        self.mock_root_gui.blockdx_manager.process_running = False
        self.mock_root_gui.blockdx_manager.utility.downloading_bin = False
        self.mock_root_gui.blocknet_manager.utility.valid_rpc = False
        self.binary_manager.disable_start_blockdx_button = False

        self.binary_manager.update_blockdx_start_close_button()

        self.binary_manager.frame_manager.blockdx_start_close_button_string_var.set.assert_called_once_with(
            widgets_strings.start_string)
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_called_once_with(
            widget=self.binary_manager.frame_manager.blockdx_start_close_button,
            msg=widgets_strings.blockdx_missing_blocknet_config_string
        )
        self.mock_utils.disable_button.assert_called_once_with(
            self.binary_manager.frame_manager.blockdx_start_close_button,
            img=self.mock_root_gui.start_greyed_img
        )
        self.mock_utils.enable_button.assert_not_called()

    def test_update_blockdx_start_close_button_running(self):
        """Test update_blockdx_start_close_button when process is running."""
        self.mock_root_gui.blockdx_manager.process_running = True
        self.mock_root_gui.blockdx_manager.utility.downloading_bin = False
        self.mock_root_gui.blocknet_manager.utility.valid_rpc = True

        self.binary_manager.update_blockdx_start_close_button()
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_called_with(
            widget=self.binary_manager.frame_manager.blockdx_start_close_button,
            msg=widgets_strings.close_string
        )
        self.mock_utils.enable_button.assert_called_once()

    def test_update_blockdx_start_close_button_running_disabled(self):
        """Test update_blockdx_start_close_button when running but disabled."""
        self.mock_root_gui.blockdx_manager.process_running = True
        self.mock_root_gui.blockdx_manager.utility.downloading_bin = False
        self.mock_root_gui.blocknet_manager.utility.valid_rpc = True
        self.binary_manager.disable_start_blockdx_button = True

        self.binary_manager.update_blockdx_start_close_button()
        # When running, the button should be enabled, not disabled
        self.mock_utils.enable_button.assert_called_once()

    def test_update_xlite_start_close_button_enabled(self):
        """Test update_xlite_start_close_button when enabled."""
        self.mock_root_gui.xlite_manager.process_running = False
        self.mock_root_gui.xlite_manager.utility.downloading_bin = False
        self.binary_manager.disable_start_xlite_button = False

        self.binary_manager.update_xlite_start_close_button()

        self.binary_manager.frame_manager.xlite_toggle_execution_string_var.set.assert_called_once_with(
            widgets_strings.start_string)
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
        """Test update_xlite_start_close_button when disabled due to downloading."""
        self.mock_root_gui.xlite_manager.process_running = False
        self.mock_root_gui.xlite_manager.utility.downloading_bin = True
        self.binary_manager.disable_start_xlite_button = False

        self.binary_manager.update_xlite_start_close_button()

        self.binary_manager.frame_manager.xlite_toggle_execution_string_var.set.assert_called_once_with(
            widgets_strings.start_string)
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_called_once_with(
            widget=self.binary_manager.frame_manager.xlite_toggle_execution_button,
            msg=widgets_strings.start_string
        )
        self.mock_utils.disable_button.assert_called_once_with(
            self.binary_manager.frame_manager.xlite_toggle_execution_button,
            img=self.mock_root_gui.start_greyed_img
        )
        self.mock_utils.enable_button.assert_not_called()

    def test_update_xlite_start_close_button_running(self):
        """Test update_xlite_start_close_button when process is running."""
        self.mock_root_gui.xlite_manager.process_running = True
        self.mock_root_gui.xlite_manager.utility.downloading_bin = False

        self.binary_manager.update_xlite_start_close_button()
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_called_with(
            widget=self.binary_manager.frame_manager.xlite_toggle_execution_button,
            msg=widgets_strings.close_string
        )
        self.mock_utils.enable_button.assert_called_once()

    def test_update_blocknet_start_close_button_bootstrap_checking(self):
        """Test update_blocknet_start_close_button when bootstrap_checking is True."""
        self.mock_root_gui.blocknet_manager.blocknet_process_running = False
        self.mock_root_gui.blocknet_manager.utility.bootstrap_checking = True
        self.mock_root_gui.blocknet_manager.utility.downloading_bin = False

        self.binary_manager.update_blocknet_start_close_button()
        self.mock_utils.disable_button.assert_called_once()

    # ==================== XBridge Bots Tests ====================

    def test_update_xbridge_bots_buttons_winfo_exists_false(self):
        """Test update_xbridge_bots_buttons when winfo_exists returns False."""
        self.mock_root_gui.winfo_exists.return_value = False
        with patch.object(self.binary_manager, 'update_xbridge_bots_start_close_button') as mock_start, \
                patch.object(self.binary_manager, 'update_xbridge_bots_install_delete_button') as mock_install:
            self.binary_manager.update_xbridge_bots_buttons()
            mock_start.assert_not_called()
            mock_install.assert_not_called()

    def test_update_xbridge_bots_buttons_process_poll(self):
        """Test update_xbridge_bots_buttons when process.poll() returns not None."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 0
        self.binary_manager.frame_manager.xbridge_bot_manager.process = mock_process

        self.binary_manager.update_xbridge_bots_buttons()
        self.assertIsNone(self.binary_manager.frame_manager.xbridge_bot_manager.process)

    def test_update_xbridge_bots_install_delete_button_condition_true(self):
        """Test update_xbridge_bots_install_delete_button when condition is True."""
        self.binary_manager.frame_manager.bots_installed_boolvar.get.return_value = True
        self.binary_manager.frame_manager.xbridge_bot_manager.process = MagicMock()

        self.binary_manager.update_xbridge_bots_install_delete_button()
        self.mock_utils.disable_button.assert_called_once()

    def test_update_xbridge_bots_install_delete_button_condition_false(self):
        """Test update_xbridge_bots_install_delete_button when condition is False."""
        self.binary_manager.frame_manager.bots_installed_boolvar.get.return_value = False
        self.binary_manager.frame_manager.xbridge_bot_manager.process = None
        self.binary_manager.frame_manager.xbridge_bot_manager.installer_thread = None

        self.binary_manager.update_xbridge_bots_install_delete_button()
        self.mock_utils.enable_button.assert_called_once()

    def test_update_xbridge_bots_start_close_button_running(self):
        """Test update_xbridge_bots_start_close_button when process is running."""
        mock_process = MagicMock()
        self.binary_manager.frame_manager.xbridge_bot_manager.process = mock_process
        self.binary_manager.frame_manager.xbridge_bot_manager.installer_thread = None

        self.binary_manager.update_xbridge_bots_start_close_button()
        self.mock_root_gui.tooltip_manager.update_tooltip.assert_called_with(
            widget=self.binary_manager.frame_manager.bots_toggle_execution_button,
            msg=widgets_strings.close_string
        )
        self.mock_utils.enable_button.assert_called_once()

    def test_update_xbridge_bots_start_close_button_disabled(self):
        """Test update_xbridge_bots_start_close_button when disabled."""
        self.binary_manager.frame_manager.xbridge_bot_manager.process = None
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        self.binary_manager.frame_manager.xbridge_bot_manager.installer_thread = mock_thread

        self.binary_manager.update_xbridge_bots_start_close_button()
        self.mock_utils.disable_button.assert_called_once()

    def test_update_xbridge_bots_version_optionmenu(self):
        """Test update_xbridge_bots_version_optionmenu method."""
        mock_optionmenu = MagicMock()
        self.binary_manager.frame_manager.bots_version_optionmenu = mock_optionmenu
        self.binary_manager.frame_manager.xbridge_bot_manager.get_available_branches.return_value = ["main", "dev"]

        self.binary_manager.update_xbridge_bots_version_optionmenu()
        mock_optionmenu.configure.assert_called_once_with(values=["main", "dev"])

    # ==================== Process File Changes Tests ====================

    def test_process_file_changes_delayed_update(self):
        """Test process_file_changes handles delayed_update messages."""
        self.binary_manager.file_change_queue.put(("delayed_update", 1000))
        self.binary_manager.process_file_changes()
        self.mock_root_gui.after.assert_any_call(1000, self.binary_manager.handler._execute_scheduled)

    def test_process_file_changes_delayed_task(self):
        """Test process_file_changes handles delayed_task messages."""
        self.binary_manager.file_change_queue.put(("delayed_task", 500))
        self.binary_manager.process_file_changes()
        self.mock_root_gui.after.assert_any_call(500, self.binary_manager.handler._execute_scheduled)

    def test_process_file_changes_empty_queue(self):
        """Test process_file_changes with empty queue."""
        # Queue is already empty from setUp
        self.binary_manager.process_file_changes()
        # Should schedule next check
        self.mock_root_gui.after.assert_called_with(100, self.binary_manager.process_file_changes)

    # ==================== Version Check Tests ====================

    def test_check_app_version_directory_wrong_version(self):
        """Test _check_app_version logs incorrect directory version."""
        app_info = {
            "is_dir": True,
            "version": "4.4.1",
            "darwin_file": None
        }
        item = "blocknet-5.0.0"
        full_path = "/mock/aio_folder/blocknet-5.0.0"

        with patch('gui.binary_manager.logger') as mock_logger:
            self.binary_manager._check_app_version(app_info, item, full_path)
            mock_logger.info.assert_called_once()
            self.assertIn("incorrect version", mock_logger.info.call_args[0][0])

    def test_check_app_version_file_wrong_version(self):
        """Test _check_app_version logs incorrect file version."""
        app_info = {
            "is_dir": False,
            "version": "1.0.0",
            "darwin_file": "blockdx.dmg"
        }
        item = "wrong_file.dmg"
        full_path = "/mock/aio_folder/wrong_file.dmg"

        with patch('gui.binary_manager.logger') as mock_logger, \
                patch('os.path.isfile', return_value=True):
            self.binary_manager._check_app_version(app_info, item, full_path)
            mock_logger.info.assert_called_once()
            self.assertIn("incorrect version", mock_logger.info.call_args[0][0])


if __name__ == '__main__':
    unittest.main()
