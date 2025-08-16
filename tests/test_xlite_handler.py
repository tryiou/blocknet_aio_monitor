import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch, mock_open

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.bin_handlers.xlite_handler import XliteHandler, XliteRPCClient


class TestXliteHandler(unittest.TestCase):
    def setUp(self):
        # Create a minimal mock setup that doesn't interfere with threading
        self.patches = []

        # Mock global_variables
        self.mock_global_variables = MagicMock()
        self.mock_global_variables.system = 'Linux'
        self.mock_global_variables.machine = 'x86_64'
        self.mock_global_variables.aio_folder = '/mock/aio_folder'
        self.mock_global_variables.xlite_volume_name = 'XliteVolume'
        self.mock_global_variables.xlite_url = 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.dmg'

        # Mock conf_data
        self.mock_conf_data = MagicMock()
        self.mock_conf_data.xlite_bin_path = {
            'Linux': 'XLite-1.0.7-linux',
            'Windows': 'XLite-1.0.7-win-x64',
            'Darwin': 'XLite-1.0.7-mac'
        }
        self.mock_conf_data.xlite_bin_name = {
            'Linux': 'xlite',
            'Windows': 'XLite.exe',
            'Darwin': ['XLite.app', 'Contents', 'MacOS', 'XLite']
        }
        self.mock_conf_data.xlite_launch_options = {
            'Linux': [],
            'Windows': ['--in-process-gpu'],
            'Darwin': []
        }
        self.mock_conf_data.xlite_default_paths = {
            'Linux': '/home/user/.xlite',
            'Windows': '/home/user/AppData/Xlite',
            'Darwin': '/home/user/Library/Application Support/Xlite'
        }
        self.mock_conf_data.xlite_daemon_default_paths = {
            'Linux': '/home/user/.xlite-daemon',
            'Windows': '/home/user/AppData/Xlite-daemon',
            'Darwin': '/home/user/Library/Application Support/Xlite-daemon'
        }
        self.mock_conf_data.xlite_releases_urls = {
            (
                'Linux',
                'x86_64'): 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-linux.tar.gz',
            (
                'Windows',
                'AMD64'): 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-win-x64.zip',
            ('Darwin', 'x86_64'): 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.dmg'
        }
        self.mock_conf_data.vc_redist_win_url = 'http://mock.com/vcredist.exe'
        self.mock_global_variables.conf_data = self.mock_conf_data

        # Apply patches
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.global_variables', self.mock_global_variables))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.os.path.exists', return_value=True))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.os.makedirs'))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.os.chmod'))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.subprocess.Popen'))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.os.listdir', return_value=[]))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.open', mock_open(read_data='{}')))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.json.load', return_value={}))

        # Start all patches
        for p in self.patches:
            p.start()

        # Mock threading to prevent actual thread creation
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.threading.Thread'))
        self.patches[-1].start()

        # Create handler instance
        self.handler = XliteHandler()

    def tearDown(self):
        # Stop all patches
        for p in self.patches:
            p.stop()

    def test_init(self):
        self.assertEqual(self.handler.xlite_pids, [])
        self.assertEqual(self.handler.xlite_daemon_pids, [])

    def test_download_xlite_bin_linux_tar_gz(self):
        with patch('utilities.bin_handlers.base_binutil.BaseBinUtil.download_binary') as mock_download:
            self.mock_global_variables.system = "Linux"
            handler = XliteHandler()  # Recreate handler with Linux system
            handler.download_xlite_bin()

            expected_url = 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-linux.tar.gz'
            expected_executable = '/mock/aio_folder/XLite-1.0.7-linux/xlite'
            mock_download.assert_called_once_with(
                expected_url,
                'tmp_xl_bin',
                expected_executable,
                '/mock/aio_folder'
            )

    def test_download_xlite_bin_darwin_dmg(self):
        with patch('utilities.bin_handlers.base_binutil.BaseBinUtil.download_binary') as mock_download:
            self.mock_global_variables.system = "Darwin"
            handler = XliteHandler()  # Recreate handler with Darwin system
            handler.download_xlite_bin()

            expected_url = 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.dmg'
            expected_executable = '/mock/aio_folder/XLite-1.0.7-mac.dmg'
            mock_download.assert_called_once_with(
                expected_url,
                'tmp_xl_bin',
                expected_executable,
                '/mock/aio_folder'
            )

    def test_parse_xlite_conf_file_exists_valid_json(self):
        mock_data = {"key": "value"}
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
                with patch('json.load', return_value=mock_data):
                    handler = XliteHandler()
                    self.assertEqual(handler.xlite_conf_local, mock_data)

    def test_parse_xlite_conf_file_not_exists(self):
        with patch('os.path.exists', return_value=False):
            handler = XliteHandler()
            self.assertEqual(handler.xlite_conf_local, {})

    def test_parse_xlite_conf_invalid_json(self):
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='invalid json')):
                with patch('json.load', side_effect=json.JSONDecodeError("Invalid", "", 0)):
                    handler = XliteHandler()
                    self.assertEqual(handler.xlite_conf_local, {})

    def test_parse_xlite_daemon_conf_file_exists_valid_json(self):
        mock_data = {"key": "value"}
        with patch('os.path.exists', side_effect=lambda path: 'settings' in str(path)):
            with patch('os.listdir', return_value=["coin-test.json"]):
                with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))):
                    with patch('json.load', return_value=mock_data):
                        handler = XliteHandler()
                        self.assertEqual(handler.xlite_daemon_confs_local, {"test": mock_data})

    def test_parse_xlite_daemon_conf_file_not_exists(self):
        with patch('os.path.exists', return_value=False):
            handler = XliteHandler()
            self.assertEqual(handler.xlite_daemon_confs_local, {})

    def test_parse_xlite_daemon_conf_invalid_json(self):
        with patch('os.path.exists', side_effect=lambda path: 'settings' in str(path)):
            with patch('os.listdir', return_value=["coin-test.json"]):
                with patch('builtins.open', mock_open(read_data='invalid json')):
                    with patch('json.load', side_effect=json.JSONDecodeError("Invalid", "", 0)):
                        handler = XliteHandler()
                        self.assertEqual(handler.xlite_daemon_confs_local, {"test": "ERROR PARSING"})

    def test_start_xlite_linux(self):
        self.mock_global_variables.system = "Linux"
        with patch('os.path.exists', return_value=True):
            with patch.object(self.handler, 'start_process') as mock_start:
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_start.return_value = mock_process

                self.handler.start_xlite(env_vars=["ENV_VAR=value"])

                expected_cmd = ['/mock/aio_folder/XLite-1.0.7-linux/xlite']
                mock_start.assert_called_once()
                args, kwargs = mock_start.call_args
                self.assertEqual(args[0], expected_cmd)

    def test_start_xlite_darwin(self):
        with patch('utilities.bin_handlers.xlite_handler.global_variables.system', 'Darwin'):
            with patch('os.path.exists', return_value=True):
                with patch('utilities.bin_handlers.xlite_handler.XliteHandler.handle_dmg') as mock_handle_dmg:
                    with patch('utilities.bin_handlers.xlite_handler.XliteHandler.start_process') as mock_start:
                        mock_process = MagicMock()
                        mock_process.pid = 12345
                        mock_start.return_value = mock_process

                        # Create handler with Darwin system
                        handler = XliteHandler()
                        handler.dmg_mount_path = '/Volumes/XliteVolume'

                        handler.start_xlite()

                        mock_handle_dmg.assert_called_once_with("mount")
                        mock_start.assert_called_once()

    def test_close_xlite_with_process(self):
        mock_process = MagicMock()
        mock_process.pid = 123
        self.handler.xlite_process = mock_process

        with patch.object(self.handler, 'graceful_terminate') as mock_graceful:
            with patch.object(self.handler, 'terminate_processes') as mock_terminate:
                self.handler.close_xlite()

                mock_graceful.assert_called_once_with(timeout=10)
                mock_terminate.assert_called()

    def test_close_xlite_no_process(self):
        self.handler.xlite_process = None

        with patch.object(self.handler, 'terminate_processes') as mock_terminate:
            self.handler.close_xlite()
            mock_terminate.assert_called()

    def test_unmount_dmg(self):
        self.mock_global_variables.system = "Darwin"
        with patch.object(self.handler, 'handle_dmg') as mock_handle_dmg:
            self.handler.unmount_dmg()
            mock_handle_dmg.assert_called_once_with("unmount")

    def test_unmount_dmg_not_darwin(self):
        self.mock_global_variables.system = "Linux"
        with patch.object(self.handler, 'handle_dmg') as mock_handle_dmg:
            self.handler.unmount_dmg()
            mock_handle_dmg.assert_not_called()

    def test_download_xlite_bin_windows_zip(self):
        with patch('utilities.bin_handlers.base_binutil.BaseBinUtil.download_binary') as mock_download:
            self.mock_global_variables.system = "Windows"
            self.mock_global_variables.machine = "AMD64"
            handler = XliteHandler()  # Recreate handler with Windows system
            handler.download_xlite_bin()

            expected_url = 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-win-x64.zip'
            expected_executable = '/mock/aio_folder/XLite-1.0.7-win-x64/XLite.exe'
            mock_download.assert_called_once_with(
                expected_url,
                'tmp_xl_bin',
                expected_executable,
                '/mock/aio_folder'
            )

    def test_xlite_rpc_client_success(self):
        with patch('utilities.bin_handlers.xlite_handler.requests.post') as mock_post:
            # Mock successful RPC response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": {"balance": 100}}
            mock_post.return_value = mock_response

            client = XliteRPCClient("testuser", "testpass", 8080)
            result = client.send_rpc_request("getbalance")

            self.assertEqual(result, {"balance": 100})
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            self.assertEqual(call_args[1]['json']['method'], "getbalance")
            self.assertEqual(call_args[1]['auth'], ("testuser", "testpass"))

    def test_xlite_rpc_client_failure(self):
        with patch('utilities.bin_handlers.xlite_handler.requests.post') as mock_post:
            # Mock failed RPC response (non-200 status)
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_post.return_value = mock_response

            client = XliteRPCClient("testuser", "testpass", 8080)
            result = client.send_rpc_request("getbalance")

            self.assertIsNone(result)

    def test_start_xlite_windows(self):
        """Test Windows start with proper mocking of conditional functions."""
        with patch('utilities.bin_handlers.xlite_handler.global_variables.system', 'Windows'):
            with patch('os.path.exists', return_value=True):
                with patch.object(self.handler.__class__, 'start_process') as mock_start:
                    mock_process = MagicMock()
                    mock_process.pid = 12345
                    mock_start.return_value = mock_process

                    # Mock the Windows-specific function that may not exist
                    with patch('utilities.bin_handlers.xlite_handler.check_vc_redist_installed', create=True,
                               return_value=True):
                        handler = XliteHandler()
                        handler.start_xlite()

                        expected_cmd = ['/mock/aio_folder/XLite-1.0.7-win-x64/XLite.exe', '--in-process-gpu']
                        mock_start.assert_called_once()
                        args, kwargs = mock_start.call_args
                        self.assertEqual(args[0], expected_cmd)

    def test_start_xlite_download_fallback(self):
        with patch('os.path.exists', return_value=False):
            with patch.object(self.handler, 'download_xlite_bin') as mock_download:
                with patch.object(self.handler, 'start_process') as mock_start:
                    mock_process = MagicMock()
                    mock_process.pid = 12345
                    mock_start.return_value = mock_process

                    self.handler.start_xlite()

                    mock_download.assert_called_once()
                    mock_start.assert_called_once()

    def test_start_xlite_malformed_env_vars(self):
        with patch('os.path.exists', return_value=True):
            with patch.object(self.handler, 'start_process') as mock_start:
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_start.return_value = mock_process

                self.handler.start_xlite(env_vars=["INVALID_VAR", "VALID_VAR=value"])

                mock_start.assert_called_once()
                args, kwargs = mock_start.call_args
                self.assertEqual(kwargs.get('env_vars', {}), {'VALID_VAR': 'value'})

    def test_parse_xlite_daemon_conf_empty_folder(self):
        with patch('os.path.exists', side_effect=lambda path: 'settings' in str(path)):
            with patch('os.listdir', return_value=[]):
                handler = XliteHandler()
                self.assertEqual(handler.xlite_daemon_confs_local, {})

    def test_download_xlite_bin_unsupported_os(self):
        """Test download with unsupported OS raises ValueError."""
        with patch('utilities.bin_handlers.xlite_handler.global_variables.system', 'UnsupportedOS'):
            with patch('utilities.bin_handlers.xlite_handler.global_variables.machine', 'x86_64'):
                # Mock all necessary configuration dictionaries
                mock_conf_data = self.mock_global_variables.conf_data

                # Add UnsupportedOS to all necessary dictionaries
                mock_conf_data.xlite_bin_path['UnsupportedOS'] = 'XLite-1.0.7-unsupported'
                mock_conf_data.xlite_bin_name['UnsupportedOS'] = 'xlite'
                mock_conf_data.xlite_default_paths['UnsupportedOS'] = '/home/user/.xlite-unsupported'
                mock_conf_data.xlite_daemon_default_paths['UnsupportedOS'] = '/home/user/.xlite-daemon-unsupported'
                # Note: xlite_releases_urls intentionally doesn't include ('UnsupportedOS', 'x86_64')

                handler = XliteHandler()

                # This should raise ValueError from download_xlite_bin
                with self.assertRaises(ValueError) as context:
                    handler.download_xlite_bin()

                self.assertIn("Unsupported OS or architecture", str(context.exception))


if __name__ == '__main__':
    unittest.main()
