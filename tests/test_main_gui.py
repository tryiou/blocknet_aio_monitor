import unittest
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock, call
import asyncio
import signal

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from blocknet_aio_monitor import Blocknet_AIO_GUI, run_gui
from utilities import global_variables, utils
import customtkinter as ctk
from PIL import Image
import widgets_strings

class TestBlocknetAioGui(unittest.TestCase):
    def setUp(self):
        # Mock external dependencies and global variables
        self.patcher_ctk = patch('blocknet_aio_monitor.ctk', autospec=True)
        self.patcher_Image = patch('blocknet_aio_monitor.Image', autospec=True)
        self.patcher_os_path_join = patch('os.path.join', side_effect=os.path.join)
        self.patcher_utils = patch('blocknet_aio_monitor.utils', autospec=True)
        self.patcher_global_variables = patch('blocknet_aio_monitor.global_variables', autospec=True)
        self.patcher_asyncio_gather = patch('asyncio.gather')
        self.patcher_asyncio_run = patch('asyncio.run')
        self.patcher_signal_signal = patch('signal.signal')
        self.patcher_os_exit = patch('os._exit')
        self.patcher_logging = patch('blocknet_aio_monitor.logging')

        self.mock_ctk = self.patcher_ctk.start()
        self.mock_Image = self.patcher_Image.start()
        self.mock_os_path_join = self.patcher_os_path_join.start()
        self.mock_utils = self.patcher_utils.start()
        self.mock_global_variables = self.patcher_global_variables.start()
        self.mock_asyncio_gather = self.patcher_asyncio_gather.start()
        self.mock_asyncio_run = self.patcher_asyncio_run.start()
        self.mock_signal_signal = self.patcher_signal_signal.start()
        self.mock_os_exit = self.patcher_os_exit.start()
        self.mock_logging = self.patcher_logging.start()

        # Configure mocks
        self.mock_ctk.CTk.return_value = MagicMock(spec=ctk.CTk)
        self.mock_ctk.CTk.return_value.after = MagicMock()
        self.mock_ctk.CTk.return_value.protocol = MagicMock()
        self.mock_ctk.CTk.return_value.title = MagicMock()
        self.mock_ctk.CTk.return_value.resizable = MagicMock()
        self.mock_ctk.CTk.return_value.mainloop = MagicMock()
        self.mock_ctk.get_appearance_mode.return_value = "Dark" # Default theme
        self.mock_ctk.set_appearance_mode = MagicMock()

        self.mock_Image.open.return_value.resize.return_value = MagicMock()
        self.mock_ctk.CTkImage.return_value = MagicMock()

        self.mock_utils.load_cfg_json.return_value = {} # Default empty config
        self.mock_utils.decrypt_password.return_value = "decrypted_pass"
        self.mock_utils.processes_check.return_value = ([], [], [], []) # No processes running by default

        self.mock_global_variables.themepath = "/mock/theme.json"
        self.mock_global_variables.DIRPATH = "/mock/dirpath"

        # Mock manager instances
        self.mock_binary_manager = MagicMock()
        self.mock_blockdx_manager = MagicMock()
        self.mock_blocknet_manager = MagicMock()
        self.mock_xlite_manager = MagicMock()
        self.mock_tooltip_manager = MagicMock()

        with patch('blocknet_aio_monitor.BinaryManager', return_value=self.mock_binary_manager), \
             patch('blocknet_aio_monitor.BlockDXManager', return_value=self.mock_blockdx_manager), \
             patch('blocknet_aio_monitor.BlocknetManager', return_value=self.mock_blocknet_manager), \
             patch('blocknet_aio_monitor.XliteManager', return_value=self.mock_xlite_manager), \
             patch('blocknet_aio_monitor.TooltipManager', return_value=self.mock_tooltip_manager):
            self.app = Blocknet_AIO_GUI()

    def tearDown(self):
        self.patcher_ctk.stop()
        self.patcher_Image.stop()
        self.patcher_os_path_join.stop()
        self.patcher_utils.stop()
        self.patcher_global_variables.stop()
        self.patcher_asyncio_gather.stop()
        self.patcher_asyncio_run.stop()
        self.patcher_signal_signal.stop()
        self.patcher_os_exit.stop()
        self.patcher_logging.stop()

    def test_init_default(self):
        self.assertIsInstance(self.app, ctk.CTk)
        self.assertEqual(self.app.custom_path, None)
        self.assertEqual(self.app.stored_password, None)
        self.assertFalse(self.app.disable_daemons_conf_check)
        self.assertEqual(self.app.time_disable_button, 3000)
        self.assertEqual(self.app.tooltip_manager, self.mock_tooltip_manager)
        self.assertEqual(self.app.blocknet_manager, self.mock_blocknet_manager)
        self.assertEqual(self.app.binary_manager, self.mock_binary_manager)
        self.assertEqual(self.app.blockdx_manager, self.mock_blockdx_manager)
        self.assertEqual(self.app.xlite_manager, self.mock_xlite_manager)
        self.mock_utils.load_cfg_json.assert_called_once()
        # Note: set_default_color_theme is called at module level, not during __init__
        # Note: adjust_theme is a real method, not mocked in this test
        self.mock_ctk.set_appearance_mode.assert_not_called() # No theme adjustment if cfg is empty or theme matches

    def test_init_with_custom_path_and_password(self):
        self.mock_utils.load_cfg_json.return_value = {
            'custom_path': '/test/path',
            'salt': 'mock_salt',
            'xl_pass': 'encrypted_pass'
        }
        with patch('blocknet_aio_monitor.BinaryManager', return_value=self.mock_binary_manager), \
             patch('blocknet_aio_monitor.BlockDXManager', return_value=self.mock_blockdx_manager), \
             patch('blocknet_aio_monitor.BlocknetManager', return_value=self.mock_blocknet_manager), \
             patch('blocknet_aio_monitor.XliteManager', return_value=self.mock_xlite_manager), \
             patch('blocknet_aio_monitor.TooltipManager', return_value=self.mock_tooltip_manager):
            app = Blocknet_AIO_GUI()
            self.assertEqual(app.custom_path, '/test/path')
            self.assertEqual(app.stored_password, 'decrypted_pass')
            self.mock_utils.decrypt_password.assert_called_once_with('encrypted_pass', b'mock_salt')

    def test_init_with_password_decryption_error(self):
        self.mock_utils.load_cfg_json.return_value = {
            'salt': 'mock_salt',
            'xl_pass': 'invalid_encrypted_pass'
        }
        self.mock_utils.decrypt_password.side_effect = Exception("Decryption failed")
        with patch('blocknet_aio_monitor.BinaryManager', return_value=self.mock_binary_manager), \
             patch('blocknet_aio_monitor.BlockDXManager', return_value=self.mock_blockdx_manager), \
             patch('blocknet_aio_monitor.BlocknetManager', return_value=self.mock_blocknet_manager), \
             patch('blocknet_aio_monitor.XliteManager', return_value=self.mock_xlite_manager), \
             patch('blocknet_aio_monitor.TooltipManager', return_value=self.mock_tooltip_manager):
            app = Blocknet_AIO_GUI()
            self.assertIsNone(app.stored_password)
            self.mock_logging.error.assert_called_once()

    @patch.object(Blocknet_AIO_GUI, 'binary_manager')
    @patch.object(Blocknet_AIO_GUI, 'blocknet_manager')
    @patch.object(Blocknet_AIO_GUI, 'blockdx_manager')
    @patch.object(Blocknet_AIO_GUI, 'xlite_manager')
    async def test_setup_management_sections(self, mock_xlite_manager, mock_blockdx_manager, mock_blocknet_manager, mock_binary_manager):
        await self.app.setup_management_sections()
        self.mock_asyncio_gather.assert_called_once_with(
            mock_binary_manager.setup(),
            mock_blocknet_manager.setup(),
            mock_blockdx_manager.setup(),
            mock_xlite_manager.setup()
        )

    @patch.object(Blocknet_AIO_GUI, 'setup_load_images')
    @patch.object(Blocknet_AIO_GUI, 'check_processes')
    @patch.object(Blocknet_AIO_GUI, 'setup_management_sections')
    @patch.object(Blocknet_AIO_GUI, 'setup_tooltips')
    @patch.object(Blocknet_AIO_GUI, 'init_grid')
    def test_init_setup(self, mock_init_grid, mock_setup_tooltips, mock_setup_management_sections, mock_check_processes, mock_setup_load_images):
        # Mock the CTk instance methods
        self.app.title = MagicMock()
        self.app.after = MagicMock()
        self.app.protocol = MagicMock()
        self.app.resizable = MagicMock()
        
        self.app.init_setup()
        self.app.title.assert_called_once_with(widgets_strings.app_title_string)
        mock_setup_load_images.assert_called_once()
        self.app.after.assert_called_once_with(0, mock_check_processes)
        mock_setup_management_sections.assert_called_once()
        mock_setup_tooltips.assert_called_once()
        mock_init_grid.assert_called_once()
        self.app.protocol.assert_called_once_with("WM_DELETE_WINDOW", self.app.on_close)
        self.mock_signal_signal.assert_any_call(signal.SIGINT, self.app.handle_signal)
        self.mock_signal_signal.assert_any_call(signal.SIGTERM, self.app.handle_signal)
        self.app.resizable.assert_called_once_with(False, False)
        # Just check that asyncio.run was called, not the specific coroutine
        self.mock_asyncio_run.assert_called_once()

    def test_setup_load_images(self):
        self.app.setup_load_images()
        self.mock_Image.open.assert_called() # Check if Image.open was called for various images
        self.mock_ctk.CTkImage.assert_called() # Check if CTkImage was called for various images
        self.assertIsNotNone(self.app.theme_img)
        self.assertIsNotNone(self.app.transparent_img)
        self.assertIsNotNone(self.app.start_img)
        # Add assertions for other images if needed

    def test_setup_tooltips(self):
        self.app.setup_tooltips()
        self.mock_tooltip_manager.register_tooltip.assert_called() # Check if register_tooltip was called multiple times

    def test_init_grid(self):
        self.app.init_grid()
        self.mock_binary_manager.frame_manager.grid_widgets.assert_called_once_with(0, 0)
        self.mock_blocknet_manager.frame_manager.grid_widgets.assert_called_once_with(0, 0)
        self.mock_blockdx_manager.frame_manager.grid_widgets.assert_called_once_with(0, 0)
        self.mock_xlite_manager.frame_manager.grid_widgets.assert_called_once_with(0, 0)
        # Check grid_frames calls
        self.mock_binary_manager.frame_manager.master_frame.grid.assert_called_once()
        self.mock_binary_manager.frame_manager.title_frame.grid.assert_called_once()
        self.mock_blocknet_manager.frame_manager.master_frame.grid.assert_called_once()
        self.mock_blocknet_manager.frame_manager.title_frame.grid.assert_called_once()
        self.mock_blockdx_manager.frame_manager.master_frame.grid.assert_called_once()
        self.mock_blockdx_manager.frame_manager.title_frame.grid.assert_called_once()
        self.mock_xlite_manager.frame_manager.master_frame.grid.assert_called_once()
        self.mock_xlite_manager.frame_manager.title_frame.grid.assert_called_once()

    def test_handle_signal(self):
        self.app.on_close = MagicMock() # Mock on_close to prevent os._exit during test
        self.app.handle_signal(signal.SIGINT, None)
        self.mock_logging.info.assert_called_once_with("Signal 2 received.") # SIGINT is 2
        self.app.on_close.assert_called_once()

    def test_on_close(self):
        self.app.on_close()
        self.mock_logging.info.assert_has_calls([
            call("Closing application..."),
            call("Threads terminated.")
        ])
        self.mock_utils.terminate_all_threads.assert_called_once()
        self.mock_os_exit.assert_called_once_with(0)

    def test_adjust_theme_no_cfg(self):
        self.app.cfg = None
        self.app.adjust_theme()
        self.mock_ctk.get_appearance_mode.assert_not_called()
        self.mock_ctk.set_appearance_mode.assert_not_called()

    def test_adjust_theme_theme_matches(self):
        self.app.cfg = {'theme': 'Dark'}
        self.mock_ctk.get_appearance_mode.return_value = "Dark"
        self.app.adjust_theme()
        self.mock_ctk.get_appearance_mode.assert_called_once()
        self.mock_ctk.set_appearance_mode.assert_not_called()

    def test_adjust_theme_theme_mismatch_dark_to_light(self):
        self.app.cfg = {'theme': 'Light'}
        self.mock_ctk.get_appearance_mode.return_value = "Dark"
        self.app.adjust_theme()
        self.mock_ctk.get_appearance_mode.assert_called_once()
        self.mock_ctk.set_appearance_mode.assert_called_once_with("Light")

    def test_adjust_theme_theme_mismatch_light_to_dark(self):
        self.app.cfg = {'theme': 'Dark'}
        self.mock_ctk.get_appearance_mode.return_value = "Light"
        self.app.adjust_theme()
        self.mock_ctk.get_appearance_mode.assert_called_once()
        self.mock_ctk.set_appearance_mode.assert_called_once_with("Dark")

    def test_switch_theme_command_dark_to_light(self):
        self.mock_ctk.get_appearance_mode.return_value = "Dark"
        self.app.switch_theme_command()
        self.mock_ctk.set_appearance_mode.assert_called_once_with("Light")
        self.mock_utils.save_cfg_json.assert_called_once_with("theme", "Light")

    def test_switch_theme_command_light_to_dark(self):
        self.mock_ctk.get_appearance_mode.return_value = "Light"
        self.app.switch_theme_command()
        self.mock_ctk.set_appearance_mode.assert_called_once_with("Dark")
        self.mock_utils.save_cfg_json.assert_called_once_with("theme", "Dark")

    def test_check_processes(self):
        self.mock_utils.processes_check.return_value = ([1], [2], [3], [4]) # Simulate running processes
        # Mock the after method to avoid actual scheduling
        self.app.after = MagicMock()
        self.app.check_processes()

        self.mock_utils.processes_check.assert_called_once()
        self.assertTrue(self.app.blocknet_manager.blocknet_process_running)
        self.assertEqual(self.app.blocknet_manager.utility.blocknet_pids, [1])
        self.assertTrue(self.app.blockdx_manager.process_running)
        self.assertEqual(self.app.blockdx_manager.utility.blockdx_pids, [2])
        self.assertTrue(self.app.xlite_manager.process_running)
        self.assertEqual(self.app.xlite_manager.utility.xlite_pids, [3])
        self.assertTrue(self.app.xlite_manager.daemon_process_running)
        self.assertEqual(self.app.xlite_manager.utility.xlite_daemon_pids, [4])
        self.app.after.assert_called_once_with(5000, func=self.app.check_processes)
        # Assert that the utility attributes are updated correctly
        self.assertEqual(self.app.blocknet_manager.utility.blocknet_pids, [1])
        self.assertEqual(self.app.blockdx_manager.utility.blockdx_pids, [2])
        self.assertEqual(self.app.xlite_manager.utility.xlite_pids, [3])
        self.assertEqual(self.app.xlite_manager.utility.xlite_daemon_pids, [4])

class TestRunGui(unittest.TestCase):
    @patch('blocknet_aio_monitor.Blocknet_AIO_GUI')
    def test_run_gui(self, MockBlocknetAioGui):
        mock_app_instance = MockBlocknetAioGui.return_value
        run_gui()
        MockBlocknetAioGui.assert_called_once()
        mock_app_instance.init_setup.assert_called_once()
        mock_app_instance.mainloop.assert_called_once()
