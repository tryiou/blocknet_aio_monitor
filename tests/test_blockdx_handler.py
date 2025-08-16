import json
import logging
import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch, call, mock_open

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.bin_handlers.blockdx_handler import BlockDXHandler
from utilities import global_variables

logger = logging.getLogger(__name__)


class TestBlockDXHandler(unittest.TestCase):
    def setUp(self):
        # Mock global_variables
        self.mock_global_variables = MagicMock()
        self.mock_global_variables.aio_folder = "/mock/aio_folder"
        self.mock_global_variables.system = "Linux"  # Default to Linux for setUp
        self.mock_global_variables.machine = "x86_64"
        self.mock_global_variables.blockdx_volume_name = "Block DX"
        self.mock_global_variables.blockdx_url = "http://mock.com/blockdx/v1.0.0/blockdx.dmg"
        self.mock_global_variables.conf_data = MagicMock()
        # Adjusted blockdx_bin_path and blockdx_bin_name for consistent path construction
        self.mock_global_variables.conf_data.blockdx_bin_path = {"Linux": "BLOCK-DX-1.0.0",
                                                                 "Darwin": "Block DX.app/Contents/MacOS"}
        self.mock_global_variables.conf_data.blockdx_bin_name = {"Linux": "block-dx",
                                                                 "Darwin": ["Block DX.app", "Contents", "MacOS",
                                                                            "Block DX"]}  # Corrected for Darwin
        self.mock_global_variables.conf_data.blockdx_default_paths = {"Linux": "/home/user/.blockdx",
                                                                      "Darwin": "/Users/user/Library/Application Support/Block DX"}
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

        # Patch external dependencies
        self.patcher_global_variables = patch('utilities.bin_handlers.blockdx_handler.global_variables',
                                              new=self.mock_global_variables)
        self.patcher_os_path_exists = patch('os.path.exists', return_value=True)
        self.patcher_os_makedirs = patch('os.makedirs')
        self.patcher_os_chmod = patch('os.chmod')
        self.patcher_os_path_join = patch('os.path.join', side_effect=os.path.join)
        self.patcher_os_path_normpath = patch('os.path.normpath', side_effect=os.path.normpath)
        self.patcher_os_path_expanduser = patch('os.path.expanduser', side_effect=lambda x: x)
        self.patcher_os_path_expandvars = patch('os.path.expandvars', side_effect=lambda x: x)
        self.patcher_open = patch('builtins.open', mock_open(read_data=''))
        self.patcher_get_blockdx_data_folder = patch('utilities.bin_handlers.blockdx_handler.get_blockdx_data_folder',
                                                     return_value="/mock/blockdx_data_folder")
        self.patcher_os_path_getsize = patch('os.path.getsize', return_value=100)
        self.patcher_os_name = patch('os.name', new="posix")
        self.patcher_sys_platform = patch('sys.platform')  # Patch sys.platform for general use
        # Remove patching for base_binutil.sys since it's not used

        # Patch BaseBinUtil methods (now including former UtilityHelper methods)

        self.patcher_base_binutil_subprocess_Popen = patch('utilities.bin_handlers.base_binutil.subprocess.Popen')
        self.patcher_base_binutil_global_variables = patch('utilities.bin_handlers.base_binutil.global_variables',
                                                           new=self.mock_global_variables)
        self.patcher_base_binutil_graceful_terminate = patch(
            'utilities.bin_handlers.blockdx_handler.BaseBinUtil.graceful_terminate')
        self.patcher_base_binutil_download_file = patch(
            'utilities.bin_handlers.blockdx_handler.BaseBinUtil.download_file')
        self.patcher_base_binutil_terminate_processes = patch(
            'utilities.bin_handlers.blockdx_handler.BaseBinUtil.terminate_processes')
        self.patcher_base_binutil_handle_dmg = patch('utilities.bin_handlers.blockdx_handler.BaseBinUtil.handle_dmg')

        self.patcher_requests_get = patch('requests.get')
        self.patcher_json_load = patch('json.load')

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
        self.mock_sys_platform.return_value = "linux"  # Default sys.platform for general use
        self.mock_base_binutil_subprocess_Popen = self.patcher_base_binutil_subprocess_Popen.start()
        self.mock_base_binutil_global_variables = self.patcher_base_binutil_global_variables.start()
        self.mock_base_binutil_graceful_terminate = self.patcher_base_binutil_graceful_terminate.start()
        self.mock_base_binutil_graceful_terminate.side_effect = lambda **kwargs: setattr(self.handler,
                                                                                         'blockdx_process', None)
        self.mock_base_binutil_download_file = self.patcher_base_binutil_download_file.start()
        self.mock_base_binutil_download_file.return_value = True  # Default return value
        self.mock_base_binutil_terminate_processes = self.patcher_base_binutil_terminate_processes.start()
        self.mock_base_binutil_terminate_processes.return_value = None  # Add this
        self.mock_base_binutil_handle_dmg = self.patcher_base_binutil_handle_dmg.start()

        self.mock_requests_get = self.patcher_requests_get.start()
        self.mock_requests_get.return_value = MagicMock(status_code=200, headers={'Content-Length': '100'})
        self.mock_requests_get.return_value.iter_content.return_value = [b'mock_content']
        self.mock_requests_get.return_value.raise_for_status.return_value = None
        self.mock_json_load = self.patcher_json_load.start()

        self.mock_psutil_process = patch('psutil.Process').start()
        self.mock_psutil_process.return_value.pid = 789
        self.mock_os_ismount = patch('os.path.ismount', return_value=True).start()

        # Patch sys in base_binutil module
        self.patcher_base_binutil_sys = patch('utilities.bin_handlers.base_binutil.sys')
        self.mock_base_binutil_sys = self.patcher_base_binutil_sys.start()
        self.mock_base_binutil_sys.platform = "linux"

        self.handler = BlockDXHandler()
        self.handler.dmg_mount_path = os.path.join(self.mock_global_variables.aio_folder,
                                                   self.mock_global_variables.blockdx_volume_name)

        self.mock_open.reset_mock()

    def tearDown(self):
        self.patcher_global_variables.stop()
        self.patcher_os_path_exists.stop()
        self.patcher_os_makedirs.stop()
        self.patcher_os_chmod.stop()
        self.patcher_os_path_join.stop()
        self.patcher_os_path_normpath.stop()
        self.patcher_os_path_expanduser.stop()
        self.patcher_os_path_expandvars.stop()
        self.patcher_open.stop()
        self.patcher_get_blockdx_data_folder.stop()
        self.patcher_os_path_getsize.stop()
        self.patcher_os_name.stop()
        self.patcher_sys_platform.stop()

        self.patcher_base_binutil_subprocess_Popen.stop()
        self.patcher_base_binutil_global_variables.stop()
        self.patcher_base_binutil_graceful_terminate.stop()
        self.patcher_base_binutil_download_file.stop()
        self.patcher_base_binutil_terminate_processes.stop()
        self.patcher_base_binutil_handle_dmg.stop()

        self.patcher_requests_get.stop()
        self.patcher_json_load.stop()
        self.patcher_base_binutil_sys.stop()
        patch.stopall()

    def test_init(self):
        with patch('utilities.bin_handlers.blockdx_handler.get_blockdx_data_folder',
                   return_value="/mock/blockdx_data_folder") as mock_get_folder:
            with patch('builtins.open', mock_open(read_data='')) as mock_file_open:
                with patch('json.load', return_value={}) as mock_json_load:
                    handler = BlockDXHandler()
                    self.assertFalse(handler.downloading_bin)
                    self.assertIsNone(handler.blockdx_process)
                    self.assertEqual(handler.blockdx_pids, [])
                    self.assertIsNotNone(handler.blockdx_conf_local)
                    self.assertFalse(handler.is_config_sync)  # Assert initial state
                    mock_get_folder.assert_called_once()
                    mock_file_open.assert_called_once_with(os.path.join("/mock/blockdx_data_folder", "app-meta.json"),
                                                           'r')
                    mock_json_load.assert_called_once()

    def test_download_blockdx_bin_linux_zip(self):
        self.mock_global_variables.system = "Linux"
        self.mock_sys_platform.return_value = "linux"
        self.mock_base_binutil_sys.platform = "linux"  # Ensure BaseBinUtil also sees linux
        self.handler.executable_path = os.path.join(self.mock_global_variables.aio_folder,
                                                    self.mock_global_variables.conf_data.blockdx_bin_path["Linux"],
                                                    self.mock_global_variables.conf_data.blockdx_bin_name["Linux"])
        self.mock_base_binutil_download_file.return_value = True
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
        self.mock_global_variables.system = "Darwin"
        self.mock_sys_platform.return_value = "darwin"
        # Removed mock_base_binutil_sys assignment
        self.handler = BlockDXHandler()
        self.handler.dmg_mount_path = os.path.join(self.mock_global_variables.aio_folder,
                                                   self.mock_global_variables.blockdx_volume_name)
        self.mock_open.reset_mock()
        self.mock_base_binutil_download_file.return_value = True

        self.handler.download_blockdx_bin()

        self.mock_base_binutil_download_file.assert_called_once_with(
            self.mock_global_variables.conf_data.blockdx_releases_urls[("Darwin", "x86_64")],
            os.path.join(self.mock_global_variables.aio_folder, "tmp_dx_bin"),
            self.handler.executable_path,
            self.mock_global_variables.aio_folder,
            'posix',
            "binary_percent_download",
            self.handler
        )
        self.mock_os_chmod.assert_not_called()

    def test_download_blockdx_bin_download_failed(self):
        self.mock_global_variables.conf_data.blockdx_releases_urls = MagicMock()
        self.mock_global_variables.conf_data.blockdx_releases_urls.get.return_value = "http://mock.com/valid_url.zip"
        self.mock_base_binutil_download_file.return_value = False

        self.handler.download_blockdx_bin()
        self.mock_base_binutil_download_file.assert_called_once()
        self.mock_os_chmod.assert_not_called()

    def test_compare_and_update_local_conf_no_existing_file(self):
        self.mock_os_path_exists.return_value = False
        self.mock_json_load.return_value = {}
        self.handler.compare_and_update_local_conf("/mock/xbridge.conf", "user", "pass")
        self.mock_open.assert_called_once_with(os.path.join("/mock/blockdx_data_folder", "app-meta.json"), 'w')

        # Get the content written to the mock file handle by joining all write calls
        written_content_str = "".join(
            [call_arg.args[0] for call_arg in self.mock_open.return_value.write.call_args_list])
        written_content = json.loads(written_content_str)

        self.assertEqual(written_content['user'], "user")
        self.assertEqual(written_content['password'], "pass")
        self.assertEqual(written_content['xbridgeConfPath'], "/mock/xbridge.conf")
        self.assertIn(self.mock_global_variables.conf_data.blockdx_selectedWallets_blocknet,
                      written_content['selectedWallets'])
        self.assertFalse(self.handler.is_config_sync)  # Changed assertion to False

    def test_compare_and_update_local_conf_existing_file_no_changes(self):
        self.mock_os_path_exists.return_value = True
        self.mock_json_load.return_value = {
            "user": "testuser",
            "password": "testpass",
            "xbridgeConfPath": "/mock/xbridge.conf",
            "FullLog": "true",
            "selectedWallets": [self.mock_global_variables.conf_data.blockdx_selectedWallets_blocknet]
        }
        self.handler = BlockDXHandler()
        self.handler.compare_and_update_local_conf("/mock/xbridge.conf", "testuser", "testpass")
        self.mock_open.assert_any_call(os.path.join("/mock/blockdx_data_folder", "app-meta.json"), 'r')
        self.assertNotIn(call(os.path.join("/mock/blockdx_data_folder", "app-meta.json"), 'w'),
                         self.mock_open.call_args_list)
        self.assertTrue(self.handler.is_config_sync)

    def test_compare_and_update_local_conf_existing_file_with_changes(self):
        self.mock_os_path_exists.return_value = True
        self.mock_json_load.return_value = {
            "user": "olduser",
            "password": "oldpass",
            "xbridgeConfPath": "/mock/xbridge.conf",
            "FullLog": "true",
            "selectedWallets": ["OLD_WALLET"]
        }
        self.handler.compare_and_update_local_conf("/mock/xbridge.conf", "newuser", "newpass")
        self.mock_open.assert_any_call(os.path.join("/mock/blockdx_data_folder", "app-meta.json"), 'r')
        self.mock_open.assert_any_call(os.path.join("/mock/blockdx_data_folder", "app-meta.json"), 'w')

        # Get the content written to the mock file handle by joining all write calls
        written_content_str = "".join(
            [call_arg.args[0] for call_arg in self.mock_open.return_value.write.call_args_list])
        written_content = json.loads(written_content_str)

        self.assertEqual(written_content['user'], "newuser")
        self.assertEqual(written_content['password'], "newpass")
        self.assertEqual(written_content['xbridgeConfPath'], "/mock/xbridge.conf")
        self.assertIn(self.mock_global_variables.conf_data.blockdx_selectedWallets_blocknet,
                      written_content['selectedWallets'])
        self.assertFalse(self.handler.is_config_sync)

    def test_start_blockdx_linux(self):
        self.mock_global_variables.system = "Linux"
        self.mock_sys_platform.return_value = "linux"
        self.mock_base_binutil_sys.platform = "linux"  # Ensure BaseBinUtil also sees linux
        self.mock_os_path_exists.return_value = True

        self.handler.start_blockdx()
        expected_cmd = [self.handler.executable_path]
        expected_cwd = os.path.join(self.mock_global_variables.aio_folder,
                                    self.mock_global_variables.conf_data.blockdx_bin_path["Linux"])
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
        self.mock_global_variables.system = "Darwin"
        self.mock_sys_platform.return_value = "darwin"
        self.mock_base_binutil_sys.platform = "darwin"  # Ensure BaseBinUtil also sees darwin
        self.handler = BlockDXHandler()
        self.handler.dmg_mount_path = os.path.join(self.mock_global_variables.aio_folder,
                                                   self.mock_global_variables.blockdx_volume_name)
        self.mock_open.reset_mock()
        self.mock_base_binutil_download_file.return_value = True

        self.mock_os_path_exists.return_value = True
        self.handler.start_blockdx()
        expected_cmd = [
            os.path.join(self.handler.dmg_mount_path, *self.mock_global_variables.conf_data.blockdx_bin_name["Darwin"])]
        expected_cwd = os.path.join(self.handler.dmg_mount_path, "Block DX.app", "Contents", "MacOS")
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
        self.assertIsNotNone(self.handler.blockdx_process)

    def test_start_blockdx_binary_not_found(self):
        self.mock_os_path_exists.return_value = False
        self.mock_base_binutil_download_file.return_value = False
        self.handler.executable_path = os.path.join(self.mock_global_variables.aio_folder, "non_existent_binary")
        self.handler.start_blockdx()
        self.mock_base_binutil_download_file.assert_called_once()
        self.mock_base_binutil_subprocess_Popen.assert_not_called()
        self.assertIsNone(self.handler.blockdx_process)

    def test_close_blockdx_with_process(self):
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
        self.handler.blockdx_process = None
        self.handler.blockdx_pids = []
        self.handler.close_blockdx()
        self.mock_base_binutil_terminate_processes.assert_called_once_with([], "BlockDX")

    def test_unmount_dmg(self):
        logger.info("\n===== START test_unmount_dmg =====")

        # Force macOS simulation                                                                                                                                                                 
        logger.info("Configuring macOS environment mocks")
        self.mock_global_variables.system = "Darwin"
        self.mock_sys_platform.return_value = "darwin"
        self.mock_base_binutil_sys.platform = "darwin"

        logger.debug(f"Mocked system: {self.mock_global_variables.system}")
        logger.debug(f"Mocked sys.platform: {self.mock_sys_platform.return_value}")
        logger.debug(f"Mocked BaseBinUtil sys.platform: {self.mock_base_binutil_sys.platform}")

        # Create handler instance with new environment                                                                                                                                           
        logger.info("Creating BlockDXHandler instance")
        handler = BlockDXHandler()
        mount_path = handler.dmg_mount_path  # Use handler's default mount path                                                                                                                  
        logger.debug(f"Handler dmg_mount_path: {mount_path}")

        # Execute test                                                                                                                                                                           
        logger.info(f"Calling unmount_dmg")
        handler.unmount_dmg()

        # Check that handle_dmg was called with expected arguments
        self.mock_base_binutil_handle_dmg.assert_called_once_with("unmount")
        logger.info("===== END test_unmount_dmg =====\n")

    def test_unmount_dmg_not_darwin(self):
        self.mock_global_variables.system = "Linux"
        self.mock_sys_platform.return_value = "linux"
        self.mock_base_binutil_sys.platform = "linux"  # Ensure BaseBinUtil also sees linux
        self.handler.unmount_dmg()
        # For non-Darwin, just ensure handle_dmg wasn't called
        if global_variables.system == "Darwin":
            self.mock_base_binutil_handle_dmg.assert_called()
        else:
            self.mock_base_binutil_handle_dmg.assert_not_called()

    def test_unmount_dmg_no_process_found(self):
        self.mock_global_variables.system = "Darwin"
        self.mock_sys_platform.return_value = "darwin"
        self.mock_base_binutil_sys.platform = "darwin"  # Ensure BaseBinUtil also sees darwin
        self.mock_os_ismount.return_value = False
        # Re-instantiate handler AFTER setting platform mocks
        self.handler = BlockDXHandler()
        self.handler.dmg_mount_path = os.path.join(self.mock_global_variables.aio_folder,
                                                   self.mock_global_variables.blockdx_volume_name)
        self.mock_open.reset_mock()

        self.handler.unmount_dmg()
        self.mock_base_binutil_handle_dmg.assert_called_with("unmount")
