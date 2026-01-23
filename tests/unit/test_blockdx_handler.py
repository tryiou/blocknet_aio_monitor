import json
import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch, call, mock_open

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.bin_handlers.blockdx_handler import BlockDXHandler


class TestBlockDXHandler(unittest.TestCase):
    """Test suite for BlockDXHandler following DRY/SOC/KISS principles."""

    def setUp(self):
        """Set up common test fixtures and mocks."""
        # Mock global_variables
        self.mock_global_variables = MagicMock()
        self.mock_global_variables.aio_folder = "/mock/aio_folder"
        self.mock_global_variables.system = "Linux"
        self.mock_global_variables.machine = "x86_64"
        self.mock_global_variables.blockdx_volume_name = "Block DX"
        self.mock_global_variables.blockdx_url = "http://mock.com/blockdx/v1.0.0/blockdx.dmg"
        self.mock_global_variables.conf_data = MagicMock()
        self.mock_global_variables.conf_data.blockdx_bin_path = {
            "Linux": "BLOCK-DX-1.0.0",
            "Darwin": "Block DX.app/Contents/MacOS"
        }
        self.mock_global_variables.conf_data.blockdx_bin_name = {
            "Linux": "block-dx",
            "Darwin": ["Block DX.app", "Contents", "MacOS", "Block DX"]
        }
        self.mock_global_variables.conf_data.blockdx_default_paths = {
            "Linux": "/home/user/.blockdx",
            "Darwin": "/Users/user/Library/Application Support/Block DX"
        }
        self.mock_global_variables.conf_data.blockdx_releases_urls = {
            ("Linux",
             "x86_64"): "https://github.com/BlocknetDX/block-dx/releases/download/v1.9.0/block-dx-v1.9.0-linux-x64.zip",
            ("Darwin",
             "x86_64"): "https://github.com/BlocknetDX/block-dx/releases/download/v1.9.0/block-dx-v1.9.0-mac-x64.dmg"
        }
        self.mock_global_variables.conf_data.blockdx_base_conf = {
            "rpcuser": "defaultuser",
            "rpcpassword": "defaultpassword",
            "FullLog": "true"
        }
        self.mock_global_variables.conf_data.blockdx_selectedWallets_blocknet = "BLOCK"

        # Create common mocks
        self._setup_common_mocks()

        # Create handler instance
        self.handler = BlockDXHandler()
        self.handler.dmg_mount_path = os.path.join(
            self.mock_global_variables.aio_folder,
            self.mock_global_variables.blockdx_volume_name
        )

    def _setup_common_mocks(self):
        """Set up commonly used mocks for all tests."""
        # External dependencies
        self.patcher_global_variables = patch(
            'utilities.bin_handlers.blockdx_handler.global_variables',
            new=self.mock_global_variables
        )
        self.patcher_os_path_exists = patch('os.path.exists', return_value=True)
        self.patcher_os_makedirs = patch('os.makedirs')
        self.patcher_os_chmod = patch('os.chmod')
        self.patcher_os_path_join = patch('os.path.join', side_effect=os.path.join)
        self.patcher_os_path_normpath = patch('os.path.normpath', side_effect=os.path.normpath)
        self.patcher_os_path_expanduser = patch('os.path.expanduser', side_effect=lambda x: x)
        self.patcher_os_path_expandvars = patch('os.path.expandvars', side_effect=lambda x: x)
        self.patcher_open = patch('builtins.open', mock_open(read_data=''))
        self.patcher_get_blockdx_data_folder = patch(
            'utilities.bin_handlers.blockdx_handler.get_blockdx_data_folder',
            return_value="/mock/blockdx_data_folder"
        )
        self.patcher_os_path_getsize = patch('os.path.getsize', return_value=100)
        self.patcher_os_name = patch('os.name', new="posix")
        self.patcher_sys_platform = patch('sys.platform')
        self.patcher_requests_get = patch('requests.get')
        self.patcher_json_load = patch('json.load')
        self.patcher_psutil_process = patch('psutil.Process')
        self.patcher_os_ismount = patch('os.path.ismount', return_value=True)

        # BaseBinUtil methods
        self.patcher_base_binutil_subprocess_Popen = patch(
            'utilities.bin_handlers.base_binutil.subprocess.Popen'
        )
        self.patcher_base_binutil_global_variables = patch(
            'utilities.bin_handlers.base_binutil.global_variables',
            new=self.mock_global_variables
        )
        self.patcher_base_binutil_graceful_terminate = patch(
            'utilities.bin_handlers.blockdx_handler.BaseBinUtil.graceful_terminate'
        )
        self.patcher_base_binutil_download_file = patch(
            'utilities.bin_handlers.blockdx_handler.BaseBinUtil.download_file'
        )
        self.patcher_base_binutil_terminate_processes = patch(
            'utilities.bin_handlers.blockdx_handler.BaseBinUtil.terminate_processes'
        )
        self.patcher_base_binutil_handle_dmg = patch(
            'utilities.bin_handlers.blockdx_handler.BaseBinUtil.handle_dmg'
        )
        self.patcher_base_binutil_sys = patch('utilities.bin_handlers.base_binutil.sys')

        # Start all patches
        self.mock_global_variables = self.patcher_global_variables.start()
        self.mock_os_path_exists = self.patcher_os_path_exists.start()
        self.mock_os_makedirs = self.patcher_os_makedirs.start()
        self.mock_os_chmod = self.patcher_os_chmod.start()
        self.mock_os_path_join = self.patcher_os_path_join.start()
        self.mock_os_path_normpath = self.patcher_os_path_normpath.start()
        self.mock_os_path_expanduser = self.patcher_os_path_expanduser.start()
        self.mock_os_path_expandvars = self.patcher_os_path_expandvars.start()
        self.mock_open = self.patcher_open.start()
        self.mock_get_blockdx_data_folder = self.patcher_get_blockdx_data_folder.start()
        self.mock_os_path_getsize = self.patcher_os_path_getsize.start()
        self.mock_os_name = self.patcher_os_name.start()
        self.mock_sys_platform = self.patcher_sys_platform.start()
        self.mock_sys_platform.return_value = "linux"
        self.mock_requests_get = self.patcher_requests_get.start()
        self.mock_requests_get.return_value = MagicMock(
            status_code=200,
            headers={'Content-Length': '100'}
        )
        self.mock_requests_get.return_value.iter_content.return_value = [b'mock_content']
        self.mock_requests_get.return_value.raise_for_status.return_value = None
        self.mock_json_load = self.patcher_json_load.start()
        self.mock_psutil_process = self.patcher_psutil_process.start()
        self.mock_psutil_process.return_value.pid = 789
        self.mock_os_ismount = self.patcher_os_ismount.start()

        self.mock_base_binutil_subprocess_Popen = self.patcher_base_binutil_subprocess_Popen.start()
        self.mock_base_binutil_global_variables = self.patcher_base_binutil_global_variables.start()
        self.mock_base_binutil_graceful_terminate = self.patcher_base_binutil_graceful_terminate.start()
        self.mock_base_binutil_graceful_terminate.side_effect = lambda **kwargs: setattr(
            self.handler, 'blockdx_process', None
        )
        self.mock_base_binutil_download_file = self.patcher_base_binutil_download_file.start()
        self.mock_base_binutil_download_file.return_value = True
        self.mock_base_binutil_terminate_processes = self.patcher_base_binutil_terminate_processes.start()
        self.mock_base_binutil_terminate_processes.return_value = None
        self.mock_base_binutil_handle_dmg = self.patcher_base_binutil_handle_dmg.start()
        self.mock_base_binutil_sys = self.patcher_base_binutil_sys.start()
        self.mock_base_binutil_sys.platform = "linux"

    def tearDown(self):
        """Clean up all patches after each test."""
        patchers = [
            self.patcher_global_variables, self.patcher_os_path_exists, self.patcher_os_makedirs,
            self.patcher_os_chmod, self.patcher_os_path_join, self.patcher_os_path_normpath,
            self.patcher_os_path_expanduser, self.patcher_os_path_expandvars, self.patcher_open,
            self.patcher_get_blockdx_data_folder, self.patcher_os_path_getsize, self.patcher_os_name,
            self.patcher_sys_platform, self.patcher_requests_get, self.patcher_json_load,
            self.patcher_psutil_process, self.patcher_os_ismount,
            self.patcher_base_binutil_subprocess_Popen, self.patcher_base_binutil_global_variables,
            self.patcher_base_binutil_graceful_terminate, self.patcher_base_binutil_download_file,
            self.patcher_base_binutil_terminate_processes, self.patcher_base_binutil_handle_dmg,
            self.patcher_base_binutil_sys
        ]
        for patcher in patchers:
            patcher.stop()
        patch.stopall()

    def _create_handler_with_os(self, system, machine=None):
        """Helper to create handler with specific OS configuration."""
        self.mock_global_variables.system = system
        if machine:
            self.mock_global_variables.machine = machine
        return BlockDXHandler()

    # =========================================================================
    # INITIALIZATION TESTS
    # =========================================================================

    def test_init(self):
        """Test BlockDXHandler initialization."""
        with patch('utilities.bin_handlers.blockdx_handler.get_blockdx_data_folder',
                   return_value="/mock/blockdx_data_folder"):
            with patch('builtins.open', mock_open(read_data='')):
                with patch('json.load', return_value={}):
                    handler = BlockDXHandler()
                    self.assertFalse(handler.downloading_bin)
                    self.assertIsNone(handler.blockdx_process)
                    self.assertEqual(handler.blockdx_pids, [])
                    self.assertIsNotNone(handler.blockdx_conf_local)
                    self.assertFalse(handler.is_config_sync)

    def test_parse_blockdx_conf_json_error(self):
        """Test parse_blockdx_conf handles JSON parsing errors."""
        self.mock_os_path_exists.return_value = True
        self.mock_json_load.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        self.handler.parse_blockdx_conf()

        # Should handle error gracefully and set empty conf
        self.assertEqual(self.handler.blockdx_conf_local, {})
        self.mock_os_makedirs.assert_not_called()  # Folder exists

    def test_parse_blockdx_conf_creates_folder(self):
        """Test parse_blockdx_conf creates folder if it doesn't exist."""
        self.mock_os_path_exists.return_value = False

        self.handler.parse_blockdx_conf()

        # Should create the data folder
        self.mock_os_makedirs.assert_called_once()
        self.assertEqual(self.handler.blockdx_conf_local, {})

    def test_get_blockdx_data_folder_linux(self):
        """Test get_blockdx_data_folder for Linux."""
        # Stop the patch that's set up in setUp to test the real function
        self.patcher_get_blockdx_data_folder.stop()

        from utilities.bin_handlers.blockdx_handler import get_blockdx_data_folder

        self.mock_global_variables.system = "Linux"
        self.mock_global_variables.conf_data.blockdx_default_paths = {
            "Linux": "/home/user/.blockdx"
        }

        folder = get_blockdx_data_folder()
        self.assertEqual(folder, "/home/user/.blockdx")

        # Restart the patch for other tests
        self.patcher_get_blockdx_data_folder.start()

    def test_get_blockdx_data_folder_darwin(self):
        """Test get_blockdx_data_folder for Darwin."""
        # Stop the patch that's set up in setUp to test the real function
        self.patcher_get_blockdx_data_folder.stop()

        from utilities.bin_handlers.blockdx_handler import get_blockdx_data_folder

        self.mock_global_variables.system = "Darwin"
        self.mock_global_variables.conf_data.blockdx_default_paths = {
            "Darwin": "/Users/user/Library/Application Support/Block DX"
        }

        folder = get_blockdx_data_folder()
        self.assertEqual(folder, "/Users/user/Library/Application Support/Block DX")

        # Restart the patch for other tests
        self.patcher_get_blockdx_data_folder.start()

    def test_get_blockdx_data_folder_unsupported(self):
        """Test get_blockdx_data_folder raises ValueError for unsupported OS."""
        # Stop the patch that's set up in setUp to test the real function
        self.patcher_get_blockdx_data_folder.stop()

        from utilities.bin_handlers.blockdx_handler import get_blockdx_data_folder

        self.mock_global_variables.system = "Windows"
        self.mock_global_variables.conf_data.blockdx_default_paths = {}

        with self.assertRaises(ValueError) as context:
            get_blockdx_data_folder()

        self.assertIn("Unsupported system", str(context.exception))

        # Restart the patch for other tests
        self.patcher_get_blockdx_data_folder.start()

    # =========================================================================
    # DOWNLOAD TESTS
    # =========================================================================

    def test_download_blockdx_bin_linux_zip(self):
        """Test downloading BlockDX binary for Linux (ZIP format)."""
        self.mock_global_variables.system = "Linux"
        self.mock_sys_platform.return_value = "linux"
        self.mock_base_binutil_sys.platform = "linux"
        self.handler.executable_path = os.path.join(
            self.mock_global_variables.aio_folder,
            self.mock_global_variables.conf_data.blockdx_bin_path["Linux"],
            self.mock_global_variables.conf_data.blockdx_bin_name["Linux"]
        )

        self.handler.download_blockdx_bin()

        self.mock_base_binutil_download_file.assert_called_once_with(
            self.mock_global_variables.conf_data.blockdx_releases_urls[("Linux", "x86_64")],
            os.path.join(self.mock_global_variables.aio_folder, "tmp_dx_bin"),
            self.handler.executable_path,
            self.mock_global_variables.aio_folder,
            'posix',
            "binary_percent_download",
            self.handler
        )

    def test_download_blockdx_bin_darwin_dmg(self):
        """Test downloading BlockDX binary for Darwin (DMG format)."""
        self.mock_global_variables.system = "Darwin"
        self.mock_sys_platform.return_value = "darwin"
        self.mock_base_binutil_sys.platform = "darwin"
        handler = self._create_handler_with_os("Darwin")
        handler.dmg_mount_path = os.path.join(
            self.mock_global_variables.aio_folder,
            self.mock_global_variables.blockdx_volume_name
        )
        self.mock_open.reset_mock()

        handler.download_blockdx_bin()

        self.mock_base_binutil_download_file.assert_called_once_with(
            self.mock_global_variables.conf_data.blockdx_releases_urls[("Darwin", "x86_64")],
            os.path.join(self.mock_global_variables.aio_folder, "tmp_dx_bin"),
            handler.executable_path,
            self.mock_global_variables.aio_folder,
            'posix',
            "binary_percent_download",
            handler
        )
        self.mock_os_chmod.assert_not_called()

    def test_download_blockdx_bin_download_failed(self):
        """Test handling download failure."""
        self.mock_global_variables.conf_data.blockdx_releases_urls = MagicMock()
        self.mock_global_variables.conf_data.blockdx_releases_urls.get.return_value = (
            "http://mock.com/valid_url.zip"
        )
        self.mock_base_binutil_download_file.return_value = False

        self.handler.download_blockdx_bin()
        self.mock_base_binutil_download_file.assert_called_once()
        self.mock_os_chmod.assert_not_called()

    # =========================================================================
    # CONFIGURATION TESTS
    # =========================================================================

    def test_compare_and_update_local_conf_no_existing_file(self):
        """Test creating new config when no existing file exists."""
        self.mock_os_path_exists.return_value = False
        self.mock_json_load.return_value = {}
        self.handler.compare_and_update_local_conf("/mock/xbridge.conf", "user", "pass")

        # Verify write was called (open is called twice: once for read, once for write)
        self.mock_open.assert_any_call(
            os.path.join("/mock/blockdx_data_folder", "app-meta.json"), 'w'
        )

        written_content_str = "".join(
            [call_arg.args[0] for call_arg in self.mock_open.return_value.write.call_args_list]
        )
        written_content = json.loads(written_content_str)

        self.assertEqual(written_content['user'], "user")
        self.assertEqual(written_content['password'], "pass")
        self.assertEqual(written_content['xbridgeConfPath'], "/mock/xbridge.conf")
        self.assertIn(
            self.mock_global_variables.conf_data.blockdx_selectedWallets_blocknet,
            written_content['selectedWallets']
        )
        self.assertFalse(self.handler.is_config_sync)

    def test_compare_and_update_local_conf_existing_file_no_changes(self):
        """Test no changes when config is already up to date."""
        self.mock_os_path_exists.return_value = True
        self.mock_json_load.return_value = {
            "user": "testuser",
            "password": "testpass",
            "xbridgeConfPath": "/mock/xbridge.conf",
            "FullLog": "true",
            "selectedWallets": [self.mock_global_variables.conf_data.blockdx_selectedWallets_blocknet]
        }
        handler = self._create_handler_with_os("Linux")
        handler.compare_and_update_local_conf("/mock/xbridge.conf", "testuser", "testpass")
        self.mock_open.assert_any_call(
            os.path.join("/mock/blockdx_data_folder", "app-meta.json"), 'r'
        )
        self.assertNotIn(
            call(os.path.join("/mock/blockdx_data_folder", "app-meta.json"), 'w'),
            self.mock_open.call_args_list
        )
        self.assertTrue(handler.is_config_sync)

    def test_compare_and_update_local_conf_non_list_selected_wallets(self):
        """Test converting non-list selectedWallets to list."""
        self.mock_os_path_exists.return_value = True
        self.mock_json_load.return_value = {
            "user": "testuser",
            "password": "testpass",
            "xbridgeConfPath": "/mock/xbridge.conf",
            "FullLog": "true",
            "selectedWallets": "OLD_WALLET"  # String instead of list
        }
        self.handler.compare_and_update_local_conf("/mock/xbridge.conf", "testuser", "testpass")

        written_content_str = "".join(
            [call_arg.args[0] for call_arg in self.mock_open.return_value.write.call_args_list]
        )
        written_content = json.loads(written_content_str)

        self.assertIsInstance(written_content['selectedWallets'], list)
        self.assertIn(
            self.mock_global_variables.conf_data.blockdx_selectedWallets_blocknet,
            written_content['selectedWallets']
        )
        self.assertFalse(self.handler.is_config_sync)

    def test_compare_and_update_local_conf_existing_file_with_changes(self):
        """Test updating config when changes are detected."""
        self.mock_os_path_exists.return_value = True
        self.mock_json_load.return_value = {
            "user": "olduser",
            "password": "oldpass",
            "xbridgeConfPath": "/mock/xbridge.conf",
            "FullLog": "true",
            "selectedWallets": ["OLD_WALLET"]
        }
        self.handler.compare_and_update_local_conf("/mock/xbridge.conf", "newuser", "newpass")
        self.mock_open.assert_any_call(
            os.path.join("/mock/blockdx_data_folder", "app-meta.json"), 'r'
        )
        self.mock_open.assert_any_call(
            os.path.join("/mock/blockdx_data_folder", "app-meta.json"), 'w'
        )

        written_content_str = "".join(
            [call_arg.args[0] for call_arg in self.mock_open.return_value.write.call_args_list]
        )
        written_content = json.loads(written_content_str)

        self.assertEqual(written_content['user'], "newuser")
        self.assertEqual(written_content['password'], "newpass")
        self.assertEqual(written_content['xbridgeConfPath'], "/mock/xbridge.conf")
        self.assertIn(
            self.mock_global_variables.conf_data.blockdx_selectedWallets_blocknet,
            written_content['selectedWallets']
        )
        self.assertFalse(self.handler.is_config_sync)

    # =========================================================================
    # START/STOP TESTS
    # =========================================================================

    def test_start_blockdx_linux(self):
        """Test starting BlockDX on Linux."""
        self.mock_global_variables.system = "Linux"
        self.mock_sys_platform.return_value = "linux"
        self.mock_base_binutil_sys.platform = "linux"
        self.mock_os_path_exists.return_value = True

        self.handler.start_blockdx()
        expected_cmd = [self.handler.executable_path]
        expected_cwd = os.path.join(
            self.mock_global_variables.aio_folder,
            self.mock_global_variables.conf_data.blockdx_bin_path["Linux"]
        )
        self.mock_base_binutil_subprocess_Popen.assert_called_once_with(
            expected_cmd,
            cwd=expected_cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
            start_new_session=True
        )
        self.assertIsNotNone(self.handler.blockdx_process)

    def test_start_blockdx_darwin(self):
        """Test starting BlockDX on Darwin."""
        self.mock_global_variables.system = "Darwin"
        self.mock_sys_platform.return_value = "darwin"
        self.mock_base_binutil_sys.platform = "darwin"
        handler = self._create_handler_with_os("Darwin")
        handler.dmg_mount_path = os.path.join(
            self.mock_global_variables.aio_folder,
            self.mock_global_variables.blockdx_volume_name
        )
        self.mock_open.reset_mock()
        self.mock_base_binutil_download_file.return_value = True
        self.mock_os_path_exists.return_value = True

        handler.start_blockdx()
        expected_cmd = [
            os.path.join(
                handler.dmg_mount_path,
                *self.mock_global_variables.conf_data.blockdx_bin_name["Darwin"]
            )
        ]
        expected_cwd = os.path.join(handler.dmg_mount_path, "Block DX.app", "Contents", "MacOS")
        self.mock_base_binutil_handle_dmg.assert_called_once_with("mount")
        self.mock_base_binutil_subprocess_Popen.assert_called_once_with(
            expected_cmd,
            cwd=expected_cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=None,
            start_new_session=True
        )
        self.assertIsNotNone(handler.blockdx_process)

    def test_start_blockdx_binary_not_found(self):
        """Test handling when binary is not found and download fails."""
        self.mock_os_path_exists.return_value = False
        self.mock_base_binutil_download_file.return_value = False
        self.handler.executable_path = os.path.join(
            self.mock_global_variables.aio_folder, "non_existent_binary"
        )
        self.handler.start_blockdx()
        self.mock_base_binutil_download_file.assert_called_once()
        self.mock_base_binutil_subprocess_Popen.assert_not_called()
        self.assertIsNone(self.handler.blockdx_process)

    def test_start_blockdx_exception_handling(self):
        """Test exception handling in start_blockdx."""
        self.mock_os_path_exists.return_value = True
        self.mock_base_binutil_subprocess_Popen.side_effect = Exception("Process start failed")

        self.handler.start_blockdx()

        # Should not crash, process should remain None
        self.assertIsNone(self.handler.blockdx_process)

    def test_download_blockdx_bin_unsupported_os(self):
        """Test ValueError when downloading for unsupported OS/architecture."""
        # Create a new mock that returns None for the get method
        mock_urls = MagicMock()
        mock_urls.get.return_value = None
        self.mock_global_variables.conf_data.blockdx_releases_urls = mock_urls

        with self.assertRaises(ValueError) as context:
            self.handler.download_blockdx_bin()

        self.assertIn("Unsupported OS or architecture", str(context.exception))

    def test_close_blockdx_with_process(self):
        """Test closing BlockDX when process is running."""
        mock_process = MagicMock()
        mock_process.pid = 123
        self.handler.blockdx_process = mock_process
        self.handler.blockdx_pids = [123, 456]

        self.handler.close_blockdx()

        self.mock_base_binutil_graceful_terminate.assert_called_once_with(timeout=10)
        self.mock_base_binutil_terminate_processes.assert_not_called()
        self.assertIsNone(self.handler.blockdx_process)
        self.assertEqual(self.handler.blockdx_pids, [123, 456])

    def test_close_blockdx_no_process(self):
        """Test closing BlockDX when no process is running."""
        self.handler.blockdx_process = None
        self.handler.blockdx_pids = []
        self.handler.close_blockdx()
        self.mock_base_binutil_terminate_processes.assert_called_once_with([], "BlockDX")

    def test_close_blockdx_pids(self):
        """Test closing BlockDX PIDs directly."""
        handler = self._create_handler_with_os("Linux")
        handler.blockdx_pids = [123, 456, 789]

        handler.close_blockdx_pids()

        self.mock_base_binutil_terminate_processes.assert_called_once_with(
            [123, 456, 789], "BlockDX"
        )

    # =========================================================================
    # DMG TESTS
    # =========================================================================

    def test_unmount_dmg(self):
        """Test unmounting DMG on Darwin."""
        self.mock_global_variables.system = "Darwin"
        self.mock_sys_platform.return_value = "darwin"
        self.mock_base_binutil_sys.platform = "darwin"
        handler = self._create_handler_with_os("Darwin")
        handler.dmg_mount_path = os.path.join(
            self.mock_global_variables.aio_folder,
            self.mock_global_variables.blockdx_volume_name
        )

        handler.unmount_dmg()

        self.mock_base_binutil_handle_dmg.assert_called_once_with("unmount")

    def test_unmount_dmg_not_darwin(self):
        """Test unmount_dmg does nothing on non-Darwin systems."""
        self.mock_global_variables.system = "Linux"
        self.mock_sys_platform.return_value = "linux"
        self.mock_base_binutil_sys.platform = "linux"
        self.handler.unmount_dmg()
        self.mock_base_binutil_handle_dmg.assert_not_called()

    def test_unmount_dmg_no_process_found(self):
        """Test unmount_dmg when DMG is not mounted."""
        self.mock_global_variables.system = "Darwin"
        self.mock_sys_platform.return_value = "darwin"
        self.mock_base_binutil_sys.platform = "darwin"
        self.mock_os_ismount.return_value = False
        handler = self._create_handler_with_os("Darwin")
        handler.dmg_mount_path = os.path.join(
            self.mock_global_variables.aio_folder,
            self.mock_global_variables.blockdx_volume_name
        )
        self.mock_open.reset_mock()

        handler.unmount_dmg()
        self.mock_base_binutil_handle_dmg.assert_called_with("unmount")

    def test_unmount_dmg_exception_handling(self):
        """Test unmount_dmg handles exceptions gracefully."""
        self.mock_global_variables.system = "Darwin"
        self.mock_sys_platform.return_value = "darwin"
        self.mock_base_binutil_sys.platform = "darwin"
        handler = self._create_handler_with_os("Darwin")
        handler.dmg_mount_path = os.path.join(
            self.mock_global_variables.aio_folder,
            self.mock_global_variables.blockdx_volume_name
        )
        self.mock_open.reset_mock()

        # Make handle_dmg raise an exception
        self.mock_base_binutil_handle_dmg.side_effect = Exception("Unmount failed")

        # Should not crash, just log warning
        handler.unmount_dmg()
        self.mock_base_binutil_handle_dmg.assert_called_with("unmount")


if __name__ == '__main__':
    unittest.main()
