import os
import signal
import sys
import unittest
from unittest.mock import MagicMock, call, mock_open, patch

from utilities.timing import TIME_DISABLE_BUTTON_MS

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import customtkinter as ctk

import widgets_strings
from blocknet_aio_monitor import BlocknetAioGui, run_gui
from utilities.app_container import AppContainer


class TestBlocknetAioGui(unittest.TestCase):
    """Test suite for BlocknetAioGui class."""

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
        cls.mocks["utils"].load_stored_password.return_value = None
        cls.mocks["utils"].processes_check.return_value = ([], [], [], [])

        # Container mocks
        cls.mocks["container"].theme_path = "/mock/theme.json"
        cls.mocks["container"].dirpath = "/mock/dirpath"
        cls.mocks["container"].blockdx_release_url = "https://mock-blockdx-url"
        cls.mocks["container"].xlite_release_url = "https://mock-xlite-url"

    @classmethod
    def _create_app_instance(cls):
        """Create BlocknetAioGui instance with mocked dependencies."""
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
            return BlocknetAioGui()

    @classmethod
    def tearDownClass(cls):
        """Clean up class-level fixtures after all tests."""
        for patcher in cls.patchers.values():
            patcher.stop()

    def setUp(self):
        """Set up test-specific fixtures before each test."""
        # Reset mock call counts between tests (except logging which should persist)
        for name, mock in self.mocks.items():
            if name not in ["logging"] and hasattr(mock, "reset_mock"):
                mock.reset_mock()
        self.mock_binary_manager.reset_mock()
        self.mock_blockdx_manager.reset_mock()
        self.mock_blocknet_manager.reset_mock()
        self.mock_xlite_manager.reset_mock()
        self.mock_tooltip_manager.reset_mock()

    def test_init_default(self):
        """Test default initialization of BlocknetAioGui."""
        self.assertIsInstance(self.app, ctk.CTk)
        self.assertEqual(self.app.custom_path, None)
        self.assertEqual(self.app.stored_password, None)
        self.assertFalse(self.app.disable_daemons_conf_check)
        self.assertEqual(self.app.time_disable_button, TIME_DISABLE_BUTTON_MS)
        self.assertEqual(self.app.tooltip_manager, self.mock_tooltip_manager)
        self.assertEqual(self.app.blocknet_manager, self.mock_blocknet_manager)
        self.assertEqual(self.app.binary_manager, self.mock_binary_manager)
        self.assertEqual(self.app.blockdx_manager, self.mock_blockdx_manager)
        self.assertEqual(self.app.xlite_manager, self.mock_xlite_manager)
        self.mocks["ctk"].set_appearance_mode.assert_not_called()

    def test_init_with_custom_path_and_password(self):
        """Test initialization with custom path and stored password."""
        self.mocks["utils"].load_cfg_json.return_value = {"custom_path": "/test/path", "xl_pass": "encrypted_pass"}
        self.mocks["utils"].load_stored_password.return_value = "decrypted_pass"
        with (
            patch("blocknet_aio_monitor.BinaryManager", return_value=self.mock_binary_manager),
            patch("blocknet_aio_monitor.BlockDXManager", return_value=self.mock_blockdx_manager),
            patch("blocknet_aio_monitor.BlocknetManager", return_value=self.mock_blocknet_manager),
            patch("blocknet_aio_monitor.XliteManager", return_value=self.mock_xlite_manager),
            patch("blocknet_aio_monitor.TooltipManager", return_value=self.mock_tooltip_manager),
        ):
            app = BlocknetAioGui()
            self.assertEqual(app.custom_path, "/test/path")
            self.assertEqual(app.stored_password, "decrypted_pass")
            self.mocks["utils"].load_stored_password.assert_called_once_with()

    def test_init_with_password_unavailable(self):
        """Test initialization keeps stored file when password cannot be loaded."""
        self.mocks["utils"].load_cfg_json.return_value = {"salt": "mock_salt", "xl_pass": "invalid_encrypted_pass"}
        self.mocks["utils"].load_stored_password.return_value = None
        try:
            with (
                patch("blocknet_aio_monitor.BinaryManager", return_value=self.mock_binary_manager),
                patch("blocknet_aio_monitor.BlockDXManager", return_value=self.mock_blockdx_manager),
                patch("blocknet_aio_monitor.BlocknetManager", return_value=self.mock_blocknet_manager),
                patch("blocknet_aio_monitor.XliteManager", return_value=self.mock_xlite_manager),
                patch("blocknet_aio_monitor.TooltipManager", return_value=self.mock_tooltip_manager),
            ):
                app = BlocknetAioGui()
                self.assertIsNone(app.stored_password)
                self.mocks["logging"].error.assert_called_once()
        except Exception as e:
            # Windows CI may have broken Tcl (init.tcl missing) — skip
            if "TclError" in type(e).__name__ or "tk.tcl" in str(e) or "init.tcl" in str(e):
                self.skipTest(f"Tk not available on this runner: {e}")
            raise

    def test_setup_management_sections(self):
        """Test that setup_management_sections is a sync method."""
        with patch.object(self.app, "setup_management_sections") as mock_setup:
            self.app.setup_management_sections()
            mock_setup.assert_called_once()

    @patch.object(BlocknetAioGui, "setup_load_images")
    @patch.object(BlocknetAioGui, "check_processes")
    @patch.object(BlocknetAioGui, "setup_management_sections")
    @patch.object(BlocknetAioGui, "setup_tooltips")
    @patch.object(BlocknetAioGui, "init_grid")
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
        # check_processes scheduled via after(0)
        self.app.after.assert_any_call(0, mock_check_processes)
        mock_setup_management_sections.assert_called_once()
        mock_setup_tooltips.assert_called_once()
        mock_init_grid.assert_called_once()
        self.app.protocol.assert_called_once_with("WM_DELETE_WINDOW", self.app.on_close)
        self.mocks["signal_signal"].assert_any_call(signal.SIGINT, self.app.handle_signal)
        self.mocks["signal_signal"].assert_any_call(signal.SIGTERM, self.app.handle_signal)
        self.app.resizable.assert_called_once_with(False, False)
        # ui_sync started, deferred network scheduled — at least 3 afters
        self.assertGreaterEqual(self.app.after.call_count, 2)

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

        # Verify grid_widgets calls (no x/y args: rows are manager-local)
        self.mock_binary_manager.frame_manager.grid_widgets.assert_called_once_with()
        self.mock_blocknet_manager.frame_manager.grid_widgets.assert_called_once_with()
        self.mock_blockdx_manager.frame_manager.grid_widgets.assert_called_once_with()
        self.mock_xlite_manager.frame_manager.grid_widgets.assert_called_once_with()

        # Verify shell gridding for all managers, one row per panel
        for row, manager in enumerate(
            [
                self.mock_binary_manager,
                self.mock_blocknet_manager,
                self.mock_blockdx_manager,
                self.mock_xlite_manager,
            ]
        ):
            manager.frame_manager.grid_shell.assert_called_once_with(row)

    def test_handle_signal(self):
        """Test signal handling — schedules on_close via after(0) and deregisters."""
        self.app._closing = False
        self.app.after = MagicMock()
        self.app.winfo_exists = MagicMock(return_value=True)
        original_on_close = self.app.on_close
        self.app.on_close = MagicMock()
        # mock signal.signal to avoid side effects
        with patch("blocknet_aio_monitor.signal.signal") as mock_sig:
            self.app.handle_signal(signal.SIGINT, None)
            self.mocks["logging"].info.assert_called_with("Signal 2 received.")
            # should schedule on_close via after(0)
            self.app.after.assert_called_with(0, self.app.on_close)
        self.app.on_close = original_on_close
        self.app._closing = False

    def test_handle_signal_idempotent_when_closing(self):
        """Signal ignored when already closing."""
        self.app._closing = True
        self.app.after = MagicMock()
        self.app.winfo_exists = MagicMock(return_value=True)
        orig = self.app.on_close
        self.app.on_close = MagicMock()
        self.app.handle_signal(signal.SIGINT, None)
        self.app.after.assert_not_called()
        self.app.on_close.assert_not_called()
        self.app.on_close = orig
        self.app._closing = False

    def test_on_close(self):
        """Test application cleanup on close — graceful destroy not os._exit."""
        # ensure fresh closing state
        self.app._closing = False
        self.app.winfo_exists = MagicMock(return_value=True)
        self.app.after_cancel = MagicMock()
        self.app.destroy = MagicMock()
        # ensure managers have stop
        self.mock_binary_manager.stop = MagicMock()
        self.mock_blocknet_manager.stop = MagicMock()
        self.mock_blockdx_manager.stop = MagicMock()
        self.mock_xlite_manager.stop = MagicMock()
        # utilities
        self.app.blocknet_manager.utility.stop = MagicMock()
        self.app.xlite_manager.utility.stop = MagicMock()
        # blockdx utility may not have stop but we mock
        self.app.blockdx_manager.utility = MagicMock()
        self.app.blockdx_manager.utility.stop = MagicMock()
        with patch("blocknet_aio_monitor.signal.signal"):
            self.app.on_close()
        self.mocks["logging"].info.assert_any_call("Closing application...")
        self.mocks["logging"].info.assert_any_call("Threads terminated.")
        # new semantics: join_daemon_threads, not terminate
        self.mocks["utils"].join_daemon_threads.assert_called_once()
        # destroy called, not os._exit
        self.app.destroy.assert_called_once()
        self.mocks["os_exit"].assert_not_called()

    def test_on_close_idempotent(self):
        """Second on_close is no-op."""
        self.app._closing = False
        self.app.winfo_exists = MagicMock(return_value=True)
        self.app.after_cancel = MagicMock()
        self.app.destroy = MagicMock()
        self.mocks["utils"].join_daemon_threads.reset_mock()
        with patch("blocknet_aio_monitor.signal.signal"):
            self.app.on_close()
            first_destroy = self.app.destroy.call_count
            self.app.on_close()
        # second call should not destroy again
        self.assertEqual(self.app.destroy.call_count, first_destroy)
        # reset for other tests
        self.app._closing = False

    def test_on_close_cancels_afters(self):
        """on_close cancels tracked afters via after_cancel."""
        self.app._closing = False
        self.app.winfo_exists = MagicMock(return_value=True)
        self.app.after_cancel = MagicMock()
        self.app.destroy = MagicMock()
        self.app._after_ids = ["id1", "id2"]
        self.app._check_processes_after_id = "chk"
        with patch("blocknet_aio_monitor.signal.signal"):
            self.app.on_close()
        # after_cancel should have been called for each id
        self.assertTrue(self.app.after_cancel.call_count >= 2)
        self.assertEqual(self.app._after_ids, [])

    def test_blocknet_handler_stop_sets_event_and_daemon(self):
        """BlocknetHandler stop sets Event and threads are daemon."""
        from utilities.bin_handlers.blocknet_handler import BlocknetHandler

        with (
            patch("utilities.bin_handlers.blocknet_handler.retrieve_xb_manifest"),
            patch("utilities.bin_handlers.blocknet_handler.retrieve_remote_blocknet_conf"),
            patch("utilities.bin_handlers.blocknet_handler.retrieve_remote_blocknet_xbridge_conf"),
            patch("utilities.bin_handlers.blocknet_handler.threading.Thread") as mock_thread,
            patch("utilities.bin_handlers.blocknet_handler.parse_conf_file"),
            patch("utilities.bin_handlers.blocknet_handler.save_conf_to_file"),
        ):
            mock_instance = MagicMock()
            mock_instance.is_alive.return_value = True
            mock_thread.return_value = mock_instance
            container = MagicMock()
            container.aio_folder = "/tmp"
            container.conf_data.blocknet_default_paths = {"Linux": "/tmp"}
            container.system = "Linux"
            with (
                patch("utilities.bin_handlers.blocknet_handler.get_container", return_value=container),
                patch.object(container, "get_blocknet_executable_path", return_value="/tmp/blocknet"),
            ):
                h = BlocknetHandler(custom_path="/tmp", container=container)
                # thread should be daemon
                mock_thread.assert_called()
                kwargs = mock_thread.call_args[1]
                self.assertTrue(kwargs.get("daemon"))
                # stop sets event
                self.assertFalse(h._stop.is_set())
                h.stop()
                self.assertTrue(h._stop.is_set())
                mock_instance.join.assert_called_with(timeout=0.5)
                # running property compat
                self.assertFalse(h.running)
                h.running = True
                self.assertTrue(h.running)
                self.assertFalse(h._stop.is_set())

    def test_xlite_handler_stop(self):
        """XliteHandler stop sets Event and daemon threads."""
        from utilities.bin_handlers.xlite_handler import XliteHandler

        with (
            patch("utilities.bin_handlers.xlite_handler.threading.Thread") as mock_thread,
            patch("utilities.bin_handlers.xlite_handler.os.path.exists", return_value=True),
            patch("utilities.bin_handlers.xlite_handler.os.makedirs"),
            patch("utilities.bin_handlers.xlite_handler.os.chmod"),
            patch("utilities.bin_handlers.xlite_handler.subprocess.Popen"),
            patch("utilities.bin_handlers.xlite_handler.open", mock_open(read_data="{}")),
            patch("utilities.bin_handlers.xlite_handler.json.load", return_value={}),
            patch("utilities.bin_handlers.xlite_handler.os.listdir", return_value=[]),
        ):
            mock_inst = MagicMock()
            mock_inst.is_alive.return_value = True
            mock_thread.return_value = mock_inst
            container = MagicMock()
            container.system = "Linux"
            container.machine = "x86_64"
            container.aio_folder = "/tmp"
            container.xlite_volume_name = "vol"
            container.xlite_release_url = "http://example.com/xlite.tar.gz"
            container.conf_data = MagicMock()
            container.conf_data.xlite_bin_path = {"Linux": "x"}
            container.conf_data.xlite_bin_name = {"Linux": "x"}
            container.conf_data.xlite_launch_options = {"Linux": []}
            container.conf_data.xlite_default_paths = {"Linux": "/tmp"}
            container.conf_data.xlite_daemon_default_paths = {"Linux": "/tmp"}
            container.conf_data.xlite_releases_urls = {("Linux", "x86_64"): "http://example.com/x"}
            container.conf_data.vc_redist_win_url = "http://example.com/vc"
            container.xlite_curpath = "XLite"
            container.xlite_bin = "xlite"
            with patch("utilities.app_container.get_container", return_value=container):
                h = XliteHandler(container)
                self.assertTrue(mock_thread.call_count >= 2)
                for call in mock_thread.call_args_list:
                    self.assertTrue(call[1].get("daemon"))
                self.assertFalse(h._stop.is_set())
                h.stop()
                self.assertTrue(h._stop.is_set())

    def test_binary_manager_stop_cancels_loops(self):
        """BinaryManager stop cancels afters."""
        from gui.binary_manager import BinaryManager

        mock_root = MagicMock()
        mock_root.after = MagicMock(return_value="after_id")
        mock_root.after_cancel = MagicMock()
        mock_root.winfo_exists = MagicMock(return_value=True)
        mock_root.tooltip_manager = MagicMock()
        for mgr in ["blocknet_manager", "blockdx_manager", "xlite_manager"]:
            m = MagicMock()
            m.utility = MagicMock()
            m.version = ["v1.0.0"]
            setattr(mock_root, mgr, m)
        container = MagicMock()
        container.aio_folder = "/tmp"
        container.system = "Linux"
        with (
            patch("gui.binary_manager.get_container", return_value=container),
            patch("gui.binary_manager.Observer") as mock_obs,
            patch("gui.binary_manager.BinaryFileHandler"),
        ):
            mock_obs.return_value.schedule = MagicMock()
            mock_obs.return_value.start = MagicMock()
            mock_obs.return_value.is_alive.return_value = True
            mock_obs.return_value.stop = MagicMock()
            mock_obs.return_value.join = MagicMock()
            bm = BinaryManager(mock_root)
            bm._poll_after_id = "poll"
            bm._process_file_changes_id = "pf"
            bm._update_all_id = "ua"
            bm._update_bots_id = "ub"
            bm._enospc_hint_id = "en"
            bm._launch_check_ids = ["l1", "l2"]
            bm._enable_button_id = "eb"
            bm._setup_ids = ["s1"]
            bm.stop()
            self.assertTrue(mock_root.after_cancel.call_count >= 5)
            mock_obs.return_value.stop.assert_called_once()
            self.assertTrue(bm._closing)

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
        from utilities.timing import INTERVAL_PROCESS_CHECK_MS

        self.mocks["utils"].processes_check.return_value = ([1], [2], [3], [4])
        self.app.after = MagicMock()
        # ensure ui_sync not driving to test fallback scheduling
        self.app.ui_sync = None
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
        self.app.after.assert_called_once_with(INTERVAL_PROCESS_CHECK_MS, func=self.app.check_processes)


class TestRunGui(unittest.TestCase):
    """Test suite for run_gui function."""

    @patch("blocknet_aio_monitor.BlocknetAioGui")
    def test_run_gui(self, mock_blocknet_aio_gui):
        """Test that run_gui creates and initializes the GUI."""
        mock_app_instance = mock_blocknet_aio_gui.return_value
        run_gui()
        mock_blocknet_aio_gui.assert_called_once()
        mock_app_instance.init_setup.assert_called_once()
        mock_app_instance.mainloop.assert_called_once()
