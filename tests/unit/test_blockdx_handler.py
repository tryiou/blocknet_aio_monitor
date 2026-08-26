import json
import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch, call, mock_open

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.bin_handlers.blockdx_handler import BlockDXHandler
from utilities.app_container import AppContainer


class TestBlockDXHandler(unittest.TestCase):
    """Test suite for BlockDXHandler following DRY/SOC/KISS principles."""

    def setUp(self):
        """Set up common test fixtures and mocks."""
        # Create mock container
        self.mock_container = MagicMock()
        self.mock_container.system = "Linux"
        self.mock_container.machine = "x86_64"
        self.mock_container.aio_folder = "/mock/aio_folder"
        
        # BlockDX specific configurations
        self.mock_container.blockdx_volume_name = "Block DX"
        self.mock_container.blockdx_release_url = "http://mock.com/blockdx/v1.0.0/blockdx.dmg"
        self.mock_container.blockdx_curpath = "BLOCK-DX-1.0.0"
        self.mock_container.blockdx_bin = "block-dx"
        
        # Binary path configurations
        self.mock_container.conf_data = MagicMock()
        self.mock_container.conf_data.blockdx_bin_path = {
            "Linux": "BLOCK-DX-1.0.0",
            "Darwin": "Block DX.app/Contents/MacOS"
        }
        self.mock_container.conf_data.blockdx_bin_name = {
            "Linux": "block-dx",
            "Darwin": ["Block DX.app", "Contents", "MacOS", "Block DX"]
        }
        self.mock_container.conf_data.blockdx_default_paths = {
            "Linux": "/home/user/.blockdx",
            "Darwin": "/Users/user/Library/Application Support/Block DX"
        }
        self.mock_container.conf_data.blockdx_releases_urls = {
            ("Linux", "x86_64"): "https://github.com/BlocknetDX/block-dx/releases/download/v1.9.0/block-dx-v1.9.0-linux-x64.zip",
            ("Darwin", "x86_64"): "https://github.com/BlocknetDX/block-dx/releases/download/v1.9.0/block-dx-v1.9.0-mac-x64.dmg"
        }
        self.mock_container.conf_data.blockdx_base_conf = {
            "rpcuser": "defaultuser",
            "rpcpassword": "defaultpassword",
            "FullLog": "true"
        }
        self.mock_container.conf_data.blockdx_selectedWallets_blocknet = "BLOCK"

        # Create common mocks
        self._setup_common_mocks()

        # Create handler instance with injected container
        self.handler = BlockDXHandler(container=self.mock_container)
        self.handler.dmg_mount_path = os.path.join(
            self.mock_container.aio_folder,
            self.mock_container.blockdx_volume_name
        )

    def _setup_common_mocks(self):
        """Set up commonly used mocks for all tests."""
        # External dependencies
        self.patcher_os_path_exists = patch('os.path.exists', return_value=True)
        self.patcher_os_makedirs = patch('os.makedirs')
        self.patcher_os_chmod = patch('os.chmod')
        self.patcher_os_path_join = patch('os.path.join', side_effect=os.path.join)
        self.patcher_os_path_normpath = patch('os.path.normpath', side_effect=os.path.normpath)
        self.patcher_os_path_expanduser = patch('os.path.expanduser', side_effect=lambda x: x)
        self.patcher_os_path_expandvars = patch('os.path.expandvars', side_effect=lambda x: x)
        self.patcher_open = patch('builtins.open', mock_open(read_data=''))
        # Don't patch get_blockdx_data_folder - we'll patch get_container instead
        self.patcher_os_path_getsize = patch('os.path.getsize', return_value=100)
        self.patcher_os_name = patch('os.name', new="posix")
        self.patcher_sys_platform = patch('sys.platform')
        self.patcher_requests_get = patch('requests.get')
        self.patcher_json_load = patch('json.load')
        self.patcher_psutil_process = patch('psutil.Process')
        self.patcher_os_ismount = patch('os.path.ismount', return_value=True)

        # Patch get_container for get_blockdx_data_folder function
        self.patcher_get_container = patch(
            'utilities.bin_handlers.blockdx_handler.get_container',
            return_value=self.mock_container
        )
        
        # BaseBinUtil methods
        self.patcher_base_binutil_subprocess_Popen = patch(
            'utilities.bin_handlers.base_binutil.subprocess.Popen'
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
        self.mock_os_path_exists = self.patcher_os_path_exists.start()
        self.mock_os_makedirs = self.patcher_os_makedirs.start()
        self.mock_os_chmod = self.patcher_os_chmod.start()
        self.mock_os_path_join = self.patcher_os_path_join.start()
        self.mock_os_path_normpath = self.patcher_os_path_normpath.start()
        self.mock_os_path_expanduser = self.patcher_os_path_expanduser.start()
        self.mock_os_path_expandvars = self.patcher_os_path_expandvars.start()
        self.mock_open = self.patcher_open.start()
        # get_blockdx_data_folder is not patched, it will use the patched get_container instead
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
        
        # Start the get_container patcher
        self.mock_get_container = self.patcher_get_container.start()

    def tearDown(self):
        """Clean up after each test."""
        # Stop all patches
        patchers = [
            self.patcher_os_path_exists, self.patcher_os_makedirs, self.patcher_os_chmod,
            self.patcher_os_path_join, self.patcher_os_path_normpath,
            self.patcher_os_path_expanduser, self.patcher_os_path_expandvars,
            self.patcher_open, 
            self.patcher_os_path_getsize, self.patcher_os_name, self.patcher_sys_platform,
            self.patcher_requests_get, self.patcher_json_load, self.patcher_psutil_process,
            self.patcher_os_ismount, self.patcher_get_container, self.patcher_base_binutil_subprocess_Popen,
            self.patcher_base_binutil_graceful_terminate,
            self.patcher_base_binutil_download_file, self.patcher_base_binutil_terminate_processes,
            self.patcher_base_binutil_handle_dmg, self.patcher_base_binutil_sys
        ]
        for patcher in patchers:
            try:
                patcher.stop()
            except:
                pass

    def _change_system(self, system: str, machine: str = "x86_64"):
        """Helper to change system configuration."""
        self.mock_container.system = system
        self.mock_container.machine = machine
        self.handler.container = self.mock_container

    def _set_darwin_config(self):
        """Configure for Darwin/macOS."""
        self._change_system("Darwin")
        self.mock_container.blockdx_volume_name = "Block DX"
        self.mock_container.blockdx_release_url = "http://mock.com/blockdx.dmg"
        self.mock_container.aio_folder = "/mock/aio_folder"
        self.mock_container.conf_data.blockdx_bin_name = {
            "Darwin": "Block DX"
        }

    def _set_linux_config(self):
        """Configure for Linux."""
        self._change_system("Linux")
        self.mock_container.blockdx_curpath = "BLOCK-DX-1.0.0"
        self.mock_container.blockdx_bin = "block-dx"
        self.mock_container.aio_folder = "/mock/aio_folder"

    def _set_windows_config(self):
        """Configure for Windows."""
        self._change_system("Windows", "AMD64")
        self.mock_container.blockdx_curpath = "BLOCK-DX-1.0.0"
        self.mock_container.blockdx_bin = "blockdx.exe"
        self.mock_container.aio_folder = "C:\\mock\\aio_folder"

    def _set_process_running(self, is_running: bool):
        """Set whether the process is running."""
        if is_running:
            self.mock_psutil_process.return_value = MagicMock(pid=1234)
            self.handler.blockdx_process = self.mock_psutil_process.return_value
        else:
            self.handler.blockdx_process = None

    def _mock_psutil_process_iter(self, names):
        """Mock psutil.process_iter to return processes with specific names."""
        mock_proc = MagicMock()
        mock_proc.info = {'name': names[0]}
        mock_proc.pid = 1234
        self.mock_psutil_process.return_value = mock_proc

    # ==================== Test Cases ====================

    def test_close_blockdx_no_process(self):
        """Test close_blockdx when no process is running."""
        self.handler.blockdx_process = None
        self.handler.close_blockdx()

        # Should not call graceful_terminate
        self.mock_base_binutil_graceful_terminate.assert_not_called()

    def test_close_blockdx_pids(self):
        """Test close_blockdx with PIDs."""
        self.handler.blockdx_pids = [1234, 5678]
        self.handler.close_blockdx()

        # Should call terminate_processes
        self.mock_base_binutil_terminate_processes.assert_called_once_with([1234, 5678], "BlockDX")

    def test_close_blockdx_with_process(self):
        """Test close_blockdx with process."""
        self.handler.blockdx_process = MagicMock()
        self.handler.close_blockdx()

        # Should call graceful_terminate
        self.mock_base_binutil_graceful_terminate.assert_called_once()

    def test_compare_and_update_local_conf_existing_file_no_changes(self):
        """Test compare_and_update_local_conf with existing file and no changes."""
        self.mock_os_path_exists.return_value = True
        existing_config = {"user": "user", "password": "pass", "xbridgeConfPath": "/path", "selectedWallets": ["BLOCK"], "FullLog": "true"}
        self.mock_json_load.return_value = existing_config
        self.mock_os_path_join.side_effect = lambda *args: "/".join(args)

        self.handler.compare_and_update_local_conf("/path", "user", "pass")

        # Should not write file since no changes (parse happens but no write)
        # Verify open was only called for reading (mode 'r'), not writing (mode 'w')
        call_args_list = self.mock_open.call_args_list
        write_calls = [call for call in call_args_list if call[0] and 'w' in str(call[0])]
        self.assertEqual(len(write_calls), 0)

    def test_compare_and_update_local_conf_existing_file_with_changes(self):
        """Test compare_and_update_local_conf with existing file and changes needed."""
        self.mock_os_path_exists.return_value = True
        existing_config = {"user": "olduser", "password": "oldpass", "xbridgeConfPath": "/oldpath", "selectedWallets": ["BLOCK"], "FullLog": "true"}
        self.mock_json_load.return_value = existing_config
        self.mock_os_path_join.side_effect = lambda *args: "/".join(args)

        self.handler.compare_and_update_local_conf("/newpath", "newuser", "newpass")

        # Should write new config - verify open was called with 'w' mode
        call_args_list = self.mock_open.call_args_list
        write_calls = [call for call in call_args_list if call[0] and 'w' in str(call[0])]
        self.assertGreater(len(write_calls), 0)

    def test_compare_and_update_local_conf_no_existing_file(self):
        """Test compare_and_update_local_conf when no existing file exists."""
        self.mock_os_path_exists.return_value = False
        self.mock_container.conf_data.blockdx_base_conf = {"rpcuser": "defaultuser", "rpcpassword": "defaultpassword", "FullLog": "true"}
        self.mock_os_path_join.side_effect = lambda *args: "/".join(args)

        self.handler.compare_and_update_local_conf("/path", "user", "pass")

        # Should write base config - verify open was called with 'w' mode
        call_args_list = self.mock_open.call_args_list
        write_calls = [call for call in call_args_list if call[0] and 'w' in str(call[0])]
        self.assertGreater(len(write_calls), 0)

    def test_compare_and_update_local_conf_non_list_selected_wallets(self):
        """Test compare_and_update_local_conf with non-list selected wallets."""
        self.mock_os_path_exists.return_value = True
        self.mock_container.conf_data.blockdx_selectedWallets_blocknet = "BLOCK"
        existing_config = {"user": "user", "password": "pass", "xbridgeConfPath": "/path", "FullLog": "true"}
        self.mock_json_load.return_value = existing_config
        self.mock_os_path_join.side_effect = lambda *args: "/".join(args)

        self.handler.compare_and_update_local_conf("/path", "user", "pass")

        # Should handle string as list with one item
        call_args_list = self.mock_open.call_args_list
        write_calls = [call for call in call_args_list if call[0] and 'w' in str(call[0])]
        self.assertGreater(len(write_calls), 0)

    def test_download_blockdx_bin_darwin_dmg(self):
        """Test download_blockdx_bin on Darwin with DMG file."""
        self._set_darwin_config()
        self.mock_container.blockdx_release_url = "http://test.com/blockdx.dmg"

        self.handler.download_binary = MagicMock(return_value=True)
        self.handler.download_blockdx_bin()

        # Should call download_binary with correct parameters
        self.handler.download_binary.assert_called_once()

    def test_download_blockdx_bin_download_failed(self):
        """Test download_blockdx_bin when download fails."""
        self.handler.download_binary = MagicMock(return_value=False)

        result = self.handler.download_blockdx_bin()

        # Should return False on failure
        self.assertFalse(result)

    def test_download_blockdx_bin_linux_zip(self):
        """Test download_blockdx_bin on Linux with ZIP file."""
        self._set_linux_config()
        self.mock_container.blockdx_release_url = "http://test.com/blockdx.zip"

        self.handler.download_binary = MagicMock(return_value=True)
        self.handler.download_blockdx_bin()

        # Should call download_binary
        self.handler.download_binary.assert_called_once()

    def test_download_blockdx_bin_unsupported_os(self):
        """Test download_blockdx_bin with unsupported OS."""
        self._change_system("UnsupportedOS")
        self.mock_container.blockdx_release_url = None

        with self.assertRaises(ValueError):
            self.handler.download_blockdx_bin()

    def test_get_blockdx_data_folder_darwin(self):
        """Test get_blockdx_data_folder on Darwin."""
        self._set_darwin_config()
        self.mock_container.conf_data.blockdx_default_paths = {
            "Darwin": "/Users/user/Library/Application Support/Block DX"
        }

        with patch('utilities.bin_handlers.blockdx_handler.get_container', return_value=self.mock_container):
            from utilities.bin_handlers.blockdx_handler import get_blockdx_data_folder
            folder = get_blockdx_data_folder()

            # Should return Darwin path
            self.assertEqual(folder, "/Users/user/Library/Application Support/Block DX")

    def test_get_blockdx_data_folder_linux(self):
        """Test get_blockdx_data_folder on Linux."""
        self._set_linux_config()
        self.mock_container.conf_data.blockdx_default_paths = {
            "Linux": "/home/user/.blockdx"
        }

        with patch('utilities.bin_handlers.blockdx_handler.get_container', return_value=self.mock_container):
            from utilities.bin_handlers.blockdx_handler import get_blockdx_data_folder
            folder = get_blockdx_data_folder()

            # Should return Linux path
            self.assertEqual(folder, "/home/user/.blockdx")

    def test_get_blockdx_data_folder_unsupported(self):
        """Test get_blockdx_data_folder with unsupported OS."""
        self._change_system("UnsupportedOS")

        with patch('utilities.bin_handlers.blockdx_handler.get_container', return_value=self.mock_container):
            from utilities.bin_handlers.blockdx_handler import get_blockdx_data_folder
            with self.assertRaises(ValueError):
                get_blockdx_data_folder()

    def test_init(self):
        """Test BlockDXHandler initialization."""
        handler = BlockDXHandler(container=self.mock_container)

        # Verify container is set correctly
        self.assertEqual(handler.container, self.mock_container)
        self.assertEqual(handler.app_name, "Blockdx")
        self.assertIsNotNone(handler.executable_path)

    def test_parse_blockdx_conf_creates_folder(self):
        """Test parse_blockdx_conf when data folder doesn't exist."""
        self.mock_container.conf_data.blockdx_default_paths = {
            "Linux": "/mock/blockdx_data_folder"
        }
        self.mock_os_path_exists.return_value = False

        self.handler.parse_blockdx_conf()

        # Should create folder
        self.mock_os_makedirs.assert_called_once()

    def test_parse_blockdx_conf_json_error(self):
        """Test parse_blockdx_conf with JSON parsing error."""
        self.mock_container.conf_data.blockdx_default_paths = {
            "Linux": "/mock/blockdx_data_folder"
        }
        self.mock_os_path_exists.return_value = True
        self.mock_json_load.side_effect = json.JSONDecodeError("Error", "", 0)

        self.handler.parse_blockdx_conf()

        # Should handle JSON error gracefully
        pass

    def test_start_blockdx_binary_not_found(self):
        """Test start_blockdx when binary is not found and download fails."""
        self.mock_os_path_exists.return_value = False
        self.mock_base_binutil_download_file.return_value = False
        self.handler.executable_path = "/mock/aio_folder/BLOCK-DX-1.0.0/block-dx"
        self.handler.start_blockdx()

        # Should call download but not start process
        self.mock_base_binutil_download_file.assert_called_once()
        self.mock_base_binutil_subprocess_Popen.assert_not_called()
        self.assertIsNone(self.handler.blockdx_process)

    def test_start_blockdx_darwin(self):
        """Test start_blockdx on Darwin."""
        self._set_darwin_config()
        self.handler.executable_path = "/mock/aio_folder/blockdx.dmg"

        self.mock_base_binutil_subprocess_Popen.return_value = MagicMock(pid=1234)
        self.handler.start_blockdx()

        # Should start process
        self.mock_base_binutil_subprocess_Popen.assert_called_once()

    def test_start_blockdx_exception_handling(self):
        """Test start_blockdx exception handling."""
        self.handler.executable_path = "/mock/path"
        self.mock_base_binutil_subprocess_Popen.side_effect = Exception("Failed to start")

        with self.assertRaises(Exception) as ctx:
            self.handler.start_blockdx()
        self.assertEqual(str(ctx.exception), "Failed to start")

    def test_start_blockdx_linux(self):
        """Test start_blockdx on Linux."""
        self._set_linux_config()
        self.handler.executable_path = "/mock/aio_folder/BLOCK-DX-1.0.0/block-dx"

        self.mock_base_binutil_subprocess_Popen.return_value = MagicMock(pid=1234)
        self.handler.start_blockdx()

        # Should start process
        self.mock_base_binutil_subprocess_Popen.assert_called_once()

    def test_unmount_dmg(self):
        """Test unmount_dmg on macOS."""
        self._set_darwin_config()
        self.handler.dmg_mount_path = "/Volumes/Block DX"

        self.handler.unmount_dmg()

        # Should call handle_dmg
        self.mock_base_binutil_handle_dmg.assert_called_once_with("unmount")

    def test_unmount_dmg_exception_handling(self):
        """Test unmount_dmg with exception."""
        self._set_darwin_config()
        self.handler.dmg_mount_path = "/Volumes/Block DX"
        self.mock_base_binutil_terminate_processes.side_effect = Exception("Failed")

        # Should not raise exception
        self.handler.unmount_dmg()

    def test_unmount_dmg_no_process_found(self):
        """Test unmount_dmg when no process is found."""
        self._set_darwin_config()
        self.handler.dmg_mount_path = "/Volumes/Block DX"
        self.mock_base_binutil_terminate_processes.return_value = None

        self.handler.unmount_dmg()

        # Should handle gracefully
        pass

    def test_unmount_dmg_not_darwin(self):
        """Test unmount_dmg on non-Darwin system."""
        self._set_linux_config()
        self.handler.dmg_mount_path = None

        self.handler.unmount_dmg()

        # Should not call terminate_processes
        self.mock_base_binutil_terminate_processes.assert_not_called()


if __name__ == "__main__":
    unittest.main()
