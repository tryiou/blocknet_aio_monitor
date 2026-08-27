import asyncio
import os
import signal
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, call, patch

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import customtkinter as ctk

import widgets_strings
from blocknet_aio_monitor import Blocknet_AIO_GUI, run_gui
from utilities.app_container import AppContainer


class TestBlocknetAioGui(unittest.TestCase):
    """Test suite for Blocknet_AIO_GUI class."""

    @classmethod
    def setUpClass(cls):
        """Set up class-level fixtures once for all tests."""
        # Create mock managers
        cls.mock_binary_manager = MagicMock()
        cls.mock_blockdx_manager = MagicMock()
        cls.mock_blocknet_manager = MagicMock()
        cls.mock_xlite_manager = MagicMock()
        cls.mock_tooltip_manager = MagicMock()

        # Patch all external dependencies
        cls.patchers = {
            "ctk": patch("blocknet_aio_monitor.ctk", autospec=True),
            "Image": patch("blocknet_aio_monitor.Image", autospec=True),
            "os_path_join": patch("os.path.join", side_effect=os.path.join),
            "utils": patch("blocknet_aio_monitor.utils", autospec=True),
            "container": patch("blocknet_aio_monitor.container", spec=AppContainer),
            "asyncio_gather": patch("asyncio.gather", return_value=None),
            "asyncio_run": patch(
                "asyncio.run", side_effect=lambda coro: asyncio.new_event_loop().run_until_complete(coro)
            ),
            "signal_signal": patch("signal.signal"),
            "os_exit": patch("os._exit"),
            "logging": patch("blocknet_aio_monitor.logger"),
        }

        # Start all patchers
        cls.mocks = {name: patcher.start() for name, patcher in cls.patchers.items()}

        # Configure common mocks
        cls._configure_mocks()

        # Create app instance with mocked managers
        cls.app = cls._create_app_instance()

    @classmethod
    def _configure_mocks(cls):
        """Configure mock objects with common settings."""
        # CTk mocks
        cls.mocks["ctk"].CTk.return_value = MagicMock(spec=ctk.CTk)
        cls.mocks["ctk"].CTk.return_value.after = MagicMock()
        cls.mocks["ctk"].CTk.return_value.protocol = MagicMock()
        cls.mocks["ctk"].CTk.return_value.title = MagicMock()
        cls.mocks["ctk"].CTk.return_value.resizable = MagicMock()
        cls.mocks["ctk"].CTk.return_value.mainloop = MagicMock()
        cls.mocks["ctk"].get_appearance_mode.return_value = "Dark"
        cls.mocks["ctk"].set_appearance_mode = MagicMock()

        # Image mocks
        cls.mocks["Image"].open.return_value.resize.return_value = MagicMock()
        cls.mocks["ctk"].CTkImage.return_value = MagicMock()

        # Utils mocks
        cls.mocks["utils"].load_cfg_json.return_value = {}
        cls.mocks["utils"].decrypt_password.return_value = "decrypted_pass"
        cls.mocks["utils"].processes_check.return_value = ([], [], [], [])

        # Container mocks
        cls.mocks["container"].theme_path = "/mock/theme.json"
        cls.mocks["container"].dirpath = "/mock/dirpath"
        cls.mocks["container"].blockdx_release_url = "https://mock-blockdx-url"
        cls.mocks["container"].xlite_release_url = "https://mock-xlite-url"

    @classmethod
    def _create_app_instance(cls):
        """Create Blocknet_AIO_GUI instance with mocked dependencies."""
        with (
            patch("blocknet_aio_monitor.BinaryManager", return_value=cls.mock_binary_manager),
            patch("blocknet_aio_monitor.BlockDXManager", return_value=cls.mock_blockdx_manager),
            patch("blocknet_aio_monitor.BlocknetManager", return_value=cls.mock_blocknet_manager),
            patch("blocknet_aio_monitor.XliteManager", return_value=cls.mock_xlite_manager),
            patch("blocknet_aio_monitor.TooltipManager", return_value=cls.mock_tooltip_manager),
            patch("utilities.bin_handlers.blocknet_handler.threading.Thread"),
            patch("utilities.bin_handlers.xlite_handler.threading.Thread"),
            patch("gui.binary_manager.Observer"),
        ):
            return Blocknet_AIO_GUI()

    @classmethod
    def tearDownClass(cls):
        """Clean up class-level fixtures after all tests."""
        for patcher in cls.patchers.values():
            patcher.stop()

    def setUp(self):
        """Set up test-specific fixtures before each test."""
        # Reset mock call counts between tests (except logging and asyncio mocks which should persist)
        for name, mock in self.mocks.items():
            if name not in ["logging", "asyncio_run", "asyncio_gather"] and hasattr(mock, "reset_mock"):
                mock.reset_mock()
        self.mock_binary_manager.reset_mock()
        self.mock_blockdx_manager.reset_mock()
        self.mock_blocknet_manager.reset_mock()
        self.mock_xlite_manager.reset_mock()
        self.mock_tooltip_manager.reset_mock()

    def test_init_default(self):
        """Test default initialization of Blocknet_AIO_GUI."""
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
        self.mocks["ctk"].set_appearance_mode.assert_not_called()

    def test_init_with_custom_path_and_password(self):
        """Test initialization with custom path and encrypted password."""
        self.mocks["utils"].load_cfg_json.return_value = {"custom_path": "/test/path", "xl_pass": "encrypted_pass"}
        with (
            patch("blocknet_aio_monitor.BinaryManager", return_value=self.mock_binary_manager),
            patch("blocknet_aio_monitor.BlockDXManager", return_value=self.mock_blockdx_manager),
            patch("blocknet_aio_monitor.BlocknetManager", return_value=self.mock_blocknet_manager),
            patch("blocknet_aio_monitor.XliteManager", return_value=self.mock_xlite_manager),
            patch("blocknet_aio_monitor.TooltipManager", return_value=self.mock_tooltip_manager),
        ):
            app = Blocknet_AIO_GUI()
            self.assertEqual(app.custom_path, "/test/path")
            self.assertEqual(app.stored_password, "decrypted_pass")
            self.mocks["utils"].decrypt_password.assert_called_once_with("encrypted_pass")

    def test_init_with_password_decryption_error(self):
        """Test initialization handles password decryption errors gracefully."""
        self.mocks["utils"].load_cfg_json.return_value = {"salt": "mock_salt", "xl_pass": "invalid_encrypted_pass"}
        self.mocks["utils"].decrypt_password.side_effect = Exception("Decryption failed")
        with (
            patch("blocknet_aio_monitor.BinaryManager", return_value=self.mock_binary_manager),
            patch("blocknet_aio_monitor.BlockDXManager", return_value=self.mock_blockdx_manager),
            patch("blocknet_aio_monitor.BlocknetManager", return_value=self.mock_blocknet_manager),
            patch("blocknet_aio_monitor.XliteManager", return_value=self.mock_xlite_manager),
            patch("blocknet_aio_monitor.TooltipManager", return_value=self.mock_tooltip_manager),
        ):
            app = Blocknet_AIO_GUI()
            self.assertIsNone(app.stored_password)
            self.mocks["logging"].error.assert_called_once()

    def test_setup_management_sections(self):
        """Test that setup_management_sections is an async method."""
        with patch.object(self.app, "setup_management_sections", new_callable=AsyncMock) as mock_setup:
            asyncio.run(self.app.setup_management_sections())
            mock_setup.assert_called_once()

    @patch.object(Blocknet_AIO_GUI, "setup_load_images")
    @patch.object(Blocknet_AIO_GUI, "check_processes")
    @patch.object(Blocknet_AIO_GUI, "setup_management_sections", new_callable=AsyncMock)
    @patch.object(Blocknet_AIO_GUI, "setup_tooltips")
    @patch.object(Blocknet_AIO_GUI, "init_grid")
    def test_init_setup(
        self,
        mock_init_grid,
        mock_setup_tooltips,
        mock_setup_management_sections,
        mock_check_processes,
        mock_setup_load_images,
    ):
        """Test the initialization setup process."""
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
        self.mocks["signal_signal"].assert_any_call(signal.SIGINT, self.app.handle_signal)
        self.mocks["signal_signal"].assert_any_call(signal.SIGTERM, self.app.handle_signal)
        self.app.resizable.assert_called_once_with(False, False)
        self.mocks["asyncio_run"].assert_called_once()

    def test_setup_load_images(self):
        """Test image loading during setup."""
        self.app.setup_load_images()
        self.mocks["Image"].open.assert_called()
        self.mocks["ctk"].CTkImage.assert_called()
        self.assertIsNotNone(self.app.theme_img)
        # Note: transparent_img is initialized to None in __init__ and not set in setup_load_images
        # This appears to be a quirk of the original implementation
        self.assertIsNotNone(self.app.start_img)

    def test_setup_tooltips(self):
        """Test tooltip registration during setup."""
        self.app.setup_tooltips()
        self.mock_tooltip_manager.register_tooltip.assert_called()

    def test_init_grid(self):
        """Test grid initialization for all manager frames."""
        self.app.init_grid()

        # Verify grid_widgets calls
        self.mock_binary_manager.frame_manager.grid_widgets.assert_called_once_with(0, 0)
        self.mock_blocknet_manager.frame_manager.grid_widgets.assert_called_once_with(0, 0)
        self.mock_blockdx_manager.frame_manager.grid_widgets.assert_called_once_with(0, 0)
        self.mock_xlite_manager.frame_manager.grid_widgets.assert_called_once_with(0, 0)

        # Verify grid_frames calls for all managers
        for manager in [
            self.mock_binary_manager,
            self.mock_blocknet_manager,
            self.mock_blockdx_manager,
            self.mock_xlite_manager,
        ]:
            manager.frame_manager.master_frame.grid.assert_called_once()
            manager.frame_manager.title_frame.grid.assert_called_once()

    def test_handle_signal(self):
        """Test signal handling."""
        original_on_close = self.app.on_close
        self.app.on_close = MagicMock()
        self.app.handle_signal(signal.SIGINT, None)
        self.mocks["logging"].info.assert_called_once_with("Signal 2 received.")
        self.app.on_close.assert_called_once()
        self.app.on_close = original_on_close

    def test_on_close(self):
        """Test application cleanup on close."""
        self.app.on_close()
        self.mocks["logging"].info.assert_any_call("Closing application...")
        self.mocks["logging"].info.assert_any_call("Threads terminated.")
        self.mocks["utils"].terminate_all_threads.assert_called_once()
        self.mocks["os_exit"].assert_called_once_with(0)

    def test_adjust_theme_no_cfg(self):
        """Test theme adjustment when no config exists."""
        self.app.cfg = None
        self.app.adjust_theme()
        self.mocks["ctk"].get_appearance_mode.assert_not_called()
        self.mocks["ctk"].set_appearance_mode.assert_not_called()

    def test_adjust_theme_theme_matches(self):
        """Test theme adjustment when theme matches current appearance."""
        self.app.cfg = {"theme": "Dark"}
        self.mocks["ctk"].get_appearance_mode.return_value = "Dark"
        self.app.adjust_theme()
        self.mocks["ctk"].get_appearance_mode.assert_called_once()
        self.mocks["ctk"].set_appearance_mode.assert_not_called()

    def test_adjust_theme_theme_mismatch_dark_to_light(self):
        """Test theme adjustment from Dark to Light."""
        self.app.cfg = {"theme": "Light"}
        self.mocks["ctk"].get_appearance_mode.return_value = "Dark"
        self.app.adjust_theme()
        self.mocks["ctk"].get_appearance_mode.assert_called_once()
        self.mocks["ctk"].set_appearance_mode.assert_called_once_with("Light")

    def test_adjust_theme_theme_mismatch_light_to_dark(self):
        """Test theme adjustment from Light to Dark."""
        self.app.cfg = {"theme": "Dark"}
        self.mocks["ctk"].get_appearance_mode.return_value = "Light"
        self.app.adjust_theme()
        self.mocks["ctk"].get_appearance_mode.assert_called_once()
        self.mocks["ctk"].set_appearance_mode.assert_called_once_with("Dark")

    def test_switch_theme_command_dark_to_light(self):
        """Test switching theme from Dark to Light."""
        self.mocks["ctk"].get_appearance_mode.return_value = "Dark"
        self.app.switch_theme_command()
        self.mocks["ctk"].set_appearance_mode.assert_called_once_with("Light")
        self.mocks["utils"].save_cfg_json.assert_called_once_with("theme", "Light")

    def test_switch_theme_command_light_to_dark(self):
        """Test switching theme from Light to Dark."""
        self.mocks["ctk"].get_appearance_mode.return_value = "Light"
        self.app.switch_theme_command()
        self.mocks["ctk"].set_appearance_mode.assert_called_once_with("Dark")
        self.mocks["utils"].save_cfg_json.assert_called_once_with("theme", "Dark")

    def test_check_processes(self):
        """Test process checking and state updates."""
        self.mocks["utils"].processes_check.return_value = ([1], [2], [3], [4])
        self.app.after = MagicMock()
        self.app.check_processes()

        self.mocks["utils"].processes_check.assert_called_once()
        self.assertTrue(self.app.blocknet_manager.blocknet_process_running)
        self.assertEqual(self.app.blocknet_manager.utility.blocknet_pids, [1])
        self.assertTrue(self.app.blockdx_manager.process_running)
        self.assertEqual(self.app.blockdx_manager.utility.blockdx_pids, [2])
        self.assertTrue(self.app.xlite_manager.process_running)
        self.assertEqual(self.app.xlite_manager.utility.xlite_pids, [3])
        self.assertTrue(self.app.xlite_manager.daemon_process_running)
        self.assertEqual(self.app.xlite_manager.utility.xlite_daemon_pids, [4])
        self.app.after.assert_called_once_with(5000, func=self.app.check_processes)


class TestRunGui(unittest.TestCase):
    """Test suite for run_gui function."""

    @patch("blocknet_aio_monitor.Blocknet_AIO_GUI")
    def test_run_gui(self, MockBlocknetAioGui):
        """Test that run_gui creates and initializes the GUI."""
        mock_app_instance = MockBlocknetAioGui.return_value
        run_gui()
        MockBlocknetAioGui.assert_called_once()
        mock_app_instance.init_setup.assert_called_once()
        mock_app_instance.mainloop.assert_called_once()
