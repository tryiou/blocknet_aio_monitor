import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch, mock_open

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.bin_handlers.xlite_handler import XliteHandler
from utilities.app_container import AppContainer


class TestXliteHandler(unittest.TestCase):
    """Test suite for XliteHandler class."""

    def setUp(self):
        """Set up common mocks and patches for all tests."""
        self.patches = []
        self._setup_app_container()
        self._setup_conf_data()
        self._apply_common_patches()
        self.handler = XliteHandler(self.mock_container)

    def _setup_app_container(self):
        """Set up AppContainer mock."""
        self.mock_container = MagicMock()
        self.mock_container.system = 'Linux'
        self.mock_container.machine = 'x86_64'
        self.mock_container.aio_folder = '/mock/aio_folder'
        self.mock_container.xlite_volume_name = 'XliteVolume'
        self.mock_container.xlite_release_url = 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.dmg'

    def _setup_conf_data(self):
        """Set up conf_data mock."""
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
            'Linux', 'x86_64'): 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-linux.tar.gz',
            (
            'Windows', 'AMD64'): 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-win-x64.zip',
            ('Darwin', 'x86_64'): 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.dmg'
        }
        self.mock_conf_data.vc_redist_win_url = 'http://mock.com/vcredist.exe'
        self.mock_container.conf_data = self.mock_conf_data
        # Set xlite_curpath and xlite_bin for the container
        self.mock_container.xlite_curpath = 'XLite-1.0.7-linux'
        self.mock_container.xlite_bin = 'xlite'

    def _apply_common_patches(self):
        """Apply common patches needed for handler initialization."""
        self.patches.append(patch('utilities.app_container.get_container', return_value=self.mock_container))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.os.path.exists', return_value=True))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.os.makedirs'))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.os.chmod'))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.subprocess.Popen'))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.os.listdir', return_value=[]))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.open', mock_open(read_data='{}')))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.json.load', return_value={}))
        self.patches.append(patch('utilities.bin_handlers.xlite_handler.threading.Thread'))

        # Start all patches
        for p in self.patches:
            p.start()

    def tearDown(self):
        """Clean up patches after each test."""
        for p in self.patches:
            p.stop()

    def _create_handler_with_os(self, system, machine=None):
        """Helper to create handler with specific OS configuration."""
        self.mock_container.system = system
        if machine:
            self.mock_container.machine = machine
        
        # Update the xlite_release_url based on the system
        if system == "Linux":
            self.mock_container.xlite_release_url = 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-linux.tar.gz'
            self.mock_container.xlite_curpath = 'XLite-1.0.7-linux'
            self.mock_container.xlite_bin = 'xlite'
        elif system == "Windows":
            self.mock_container.xlite_release_url = 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-win-x64.zip'
            self.mock_container.xlite_curpath = 'XLite-1.0.7-win-x64'
            self.mock_container.xlite_bin = 'XLite.exe'
        elif system == "Darwin":
            self.mock_container.xlite_release_url = 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.dmg'
            self.mock_container.xlite_curpath = 'XLite-1.0.7-mac.dmg'
            self.mock_container.xlite_bin = ['XLite.app', 'Contents', 'MacOS', 'XLite']
        
        return XliteHandler(self.mock_container)

    # ============================================================================
    # Initialization Tests
    # ============================================================================

    def test_init(self):
        """Test handler initialization sets up expected attributes."""
        self.assertEqual(self.handler.xlite_pids, [])
        self.assertEqual(self.handler.xlite_daemon_pids, [])

    # ============================================================================
    # Download Tests
    # ============================================================================

    def test_download_xlite_bin_linux_tar_gz(self):
        """Test downloading XLite binary for Linux (tar.gz format)."""
        with patch('utilities.bin_handlers.base_binutil.BaseBinUtil.download_binary') as mock_download:
            handler = self._create_handler_with_os("Linux")
            handler.download_xlite_bin()

            expected_url = 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-linux.tar.gz'
            expected_executable = '/mock/aio_folder/XLite-1.0.7-linux/xlite'
            mock_download.assert_called_once_with(
                expected_url,
                'tmp_xl_bin',
                expected_executable,
                '/mock/aio_folder'
            )

    def test_download_xlite_bin_windows_zip(self):
        """Test downloading XLite binary for Windows (zip format)."""
        with patch('utilities.bin_handlers.base_binutil.BaseBinUtil.download_binary') as mock_download:
            handler = self._create_handler_with_os("Windows", "AMD64")
            handler.download_xlite_bin()

            expected_url = 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-win-x64.zip'
            expected_executable = '/mock/aio_folder/XLite-1.0.7-win-x64/XLite.exe'
            mock_download.assert_called_once_with(
                expected_url,
                'tmp_xl_bin',
                expected_executable,
                '/mock/aio_folder'
            )

    def test_download_xlite_bin_darwin_dmg(self):
        """Test downloading XLite binary for Darwin (dmg format)."""
        with patch('utilities.bin_handlers.base_binutil.BaseBinUtil.download_binary') as mock_download:
            handler = self._create_handler_with_os("Darwin")
            handler.download_xlite_bin()

            expected_url = 'https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.dmg'
            expected_executable = '/mock/aio_folder/XLite-1.0.7-mac.dmg'
            mock_download.assert_called_once_with(
                expected_url,
                'tmp_xl_bin',
                expected_executable,
                '/mock/aio_folder'
            )

    def test_download_xlite_bin_unsupported_os(self):
        """Test download raises ValueError for unsupported OS."""
        self.mock_container.system = 'UnsupportedOS'
        self.mock_container.machine = 'x86_64'
        # Ensure no release URL is configured for this unsupported OS
        self.mock_conf_data.xlite_releases_urls.pop(('UnsupportedOS', 'x86_64'), None)
        self.mock_container.xlite_release_url = None

        handler = XliteHandler(self.mock_container)

        with self.assertRaises(ValueError) as context:
            handler.download_xlite_bin()

        self.assertIn("Unsupported OS or architecture", str(context.exception))

    # ============================================================================
    # Configuration Parsing Tests
    # ============================================================================

    def test_parse_xlite_conf_file_exists_valid_json(self):
        """Test parsing XLite config when file exists with valid JSON."""
        mock_data = {"key": "value"}
        with patch('os.path.exists', return_value=True), \
                patch('builtins.open', mock_open(read_data=json.dumps(mock_data))), \
                patch('json.load', return_value=mock_data):
            handler = self._create_handler_with_os("Linux")
            self.assertEqual(handler.xlite_conf_local, mock_data)

    def test_parse_xlite_conf_file_not_exists(self):
        """Test parsing XLite config when file doesn't exist."""
        with patch('os.path.exists', return_value=False):
            handler = self._create_handler_with_os("Linux")
            self.assertEqual(handler.xlite_conf_local, {})

    def test_parse_xlite_conf_invalid_json(self):
        """Test parsing XLite config with invalid JSON."""
        with patch('os.path.exists', return_value=True), \
                patch('builtins.open', mock_open(read_data='invalid json')), \
                patch('json.load', side_effect=json.JSONDecodeError("Invalid", "", 0)):
            handler = self._create_handler_with_os("Linux")
            self.assertEqual(handler.xlite_conf_local, {})

    def test_parse_xlite_daemon_conf_file_exists_valid_json(self):
        """Test parsing daemon config when file exists with valid JSON."""
        mock_data = {"key": "value"}
        with patch('os.path.exists', side_effect=lambda path: 'settings' in str(path)), \
                patch('os.listdir', return_value=["coin-test.json"]), \
                patch('builtins.open', mock_open(read_data=json.dumps(mock_data))), \
                patch('json.load', return_value=mock_data):
            handler = self._create_handler_with_os("Linux")
            self.assertEqual(handler.xlite_daemon_confs_local, {"test": mock_data})

    def test_parse_xlite_daemon_conf_file_not_exists(self):
        """Test parsing daemon config when folder doesn't exist."""
        with patch('os.path.exists', return_value=False):
            handler = self._create_handler_with_os("Linux")
            self.assertEqual(handler.xlite_daemon_confs_local, {})

    def test_parse_xlite_daemon_conf_invalid_json(self):
        """Test parsing daemon config with invalid JSON."""
        with patch('os.path.exists', side_effect=lambda path: 'settings' in str(path)), \
                patch('os.listdir', return_value=["coin-test.json"]), \
                patch('builtins.open', mock_open(read_data='invalid json')), \
                patch('json.load', side_effect=json.JSONDecodeError("Invalid", "", 0)):
            handler = self._create_handler_with_os("Linux")
            self.assertEqual(handler.xlite_daemon_confs_local, {"test": "ERROR PARSING"})

    def test_parse_xlite_daemon_conf_empty_folder(self):
        """Test parsing daemon config when folder is empty."""
        with patch('os.path.exists', side_effect=lambda path: 'settings' in str(path)), \
                patch('os.listdir', return_value=[]):
            handler = self._create_handler_with_os("Linux")
            self.assertEqual(handler.xlite_daemon_confs_local, {})

    # ============================================================================
    # Daemon Configuration Sequence Tests
    # ============================================================================

    def test_check_xlite_daemon_confs_sequence(self):
        """Test checking daemon config sequence with valid data."""
        mock_data = {
            "rpcPort": 12345,
            "rpcUsername": "user",
            "rpcPassword": "pass"
        }
        with patch('os.path.exists', side_effect=lambda path: 'settings' in str(path)), \
                patch('os.listdir', return_value=["coin-test.json"]), \
                patch('builtins.open', mock_open(read_data=json.dumps(mock_data))), \
                patch('json.load', return_value=mock_data), \
                patch('utilities.bin_handlers.xlite_handler.RPCClient') as mock_rpc:
            handler = self._create_handler_with_os("Linux")
            handler.check_xlite_daemon_confs_sequence(silent=True)

            mock_rpc.assert_called_once_with(
                rpc_user="user",
                rpc_password="pass",
                rpc_port=12345
            )
            self.assertIn("test", handler.coins_rpc)

    def test_check_xlite_daemon_confs_sequence_empty(self):
        """Test checking daemon config sequence with no configs."""
        with patch('os.path.exists', return_value=False):
            handler = self._create_handler_with_os("Linux")
            handler.check_xlite_daemon_confs_sequence(silent=True)
            self.assertEqual(handler.coins_rpc, {})

    # ============================================================================
    # Daemon Configuration Loop Tests
    # ============================================================================

    def test_check_xlite_daemon_confs(self):
        """Test daemon config checking loop."""
        mock_data = {
            "rpcPort": 12345,
            "rpcUsername": "user",
            "rpcPassword": "pass"
        }
        with patch('os.path.exists', side_effect=lambda path: 'settings' in str(path)), \
                patch('os.listdir', return_value=["coin-test.json"]), \
                patch('builtins.open', mock_open(read_data=json.dumps(mock_data))), \
                patch('json.load', return_value=mock_data), \
                patch('utilities.bin_handlers.xlite_handler.RPCClient') as mock_rpc, \
                patch('time.sleep', side_effect=KeyboardInterrupt):

            handler = self._create_handler_with_os("Linux")
            handler.running = True
            handler.valid_coins_rpc = False
            try:
                handler.check_xlite_daemon_confs()
            except KeyboardInterrupt:
                pass

            mock_rpc.assert_called_once()

    def test_check_xlite_daemon_confs_running(self):
        """Test daemon config checking loop with running flag."""
        mock_data = {
            "rpcPort": 12345,
            "rpcUsername": "user",
            "rpcPassword": "pass"
        }
        with patch('os.path.exists', side_effect=lambda path: 'settings' in str(path)), \
                patch('os.listdir', return_value=["coin-test.json"]), \
                patch('builtins.open', mock_open(read_data=json.dumps(mock_data))), \
                patch('json.load', return_value=mock_data), \
                patch('utilities.bin_handlers.xlite_handler.RPCClient') as mock_rpc, \
                patch('time.sleep', side_effect=KeyboardInterrupt):
            handler = self._create_handler_with_os("Linux")
            handler.running = True
            handler.valid_coins_rpc = True  # Loop condition met, should exit immediately
            handler.check_xlite_daemon_confs()

            mock_rpc.assert_not_called()

    # ============================================================================
    # Valid Coins RPC Tests
    # ============================================================================

    def test_check_valid_xlite_coins_rpc_valid(self):
        """Test checking valid coins RPC with valid data."""
        mock_rpc_server = MagicMock()
        mock_rpc_server.send_rpc_request.return_value = {"result": "success"}

        with patch('time.sleep', side_effect=KeyboardInterrupt):
            handler = self._create_handler_with_os("Linux")
            handler.coins_rpc = {"test": mock_rpc_server}
            handler.xlite_daemon_confs_local = {"test": {"rpcEnabled": True}}
            handler.running = True
            try:
                handler.check_valid_xlite_coins_rpc(runonce=True)
            except KeyboardInterrupt:
                pass

            mock_rpc_server.send_rpc_request.assert_called_once_with("getinfo")
            self.assertTrue(handler.valid_coins_rpc)

    def test_check_valid_xlite_coins_rpc_master_ignored(self):
        """Test that master and TBLOCK coins are ignored."""
        mock_rpc_server = MagicMock()
        mock_rpc_server.send_rpc_request.return_value = {"result": "success"}

        with patch('time.sleep', side_effect=KeyboardInterrupt):
            handler = self._create_handler_with_os("Linux")
            handler.coins_rpc = {"master": mock_rpc_server, "TBLOCK": mock_rpc_server}
            handler.xlite_daemon_confs_local = {
                "master": {"rpcEnabled": True},
                "TBLOCK": {"rpcEnabled": True}
            }
            handler.running = True
            try:
                handler.check_valid_xlite_coins_rpc(runonce=True)
            except KeyboardInterrupt:
                pass

            mock_rpc_server.send_rpc_request.assert_not_called()
            # When all coins are ignored (master and TBLOCK), valid_coins_rpc should be False
            self.assertFalse(handler.valid_coins_rpc)

    def test_check_valid_xlite_coins_rpc_disabled(self):
        """Test checking coins RPC with disabled RPC."""
        mock_rpc_server = MagicMock()

        with patch('time.sleep', side_effect=KeyboardInterrupt):
            handler = self._create_handler_with_os("Linux")
            handler.coins_rpc = {"test": mock_rpc_server}
            handler.xlite_daemon_confs_local = {"test": {"rpcEnabled": False}}
            handler.running = True
            try:
                handler.check_valid_xlite_coins_rpc(runonce=True)
            except KeyboardInterrupt:
                pass

            mock_rpc_server.send_rpc_request.assert_not_called()
            self.assertFalse(handler.valid_coins_rpc)

    def test_check_valid_xlite_coins_rpc_no_coins(self):
        """Test checking coins RPC with no coins configured."""
        with patch('time.sleep', side_effect=KeyboardInterrupt):
            handler = self._create_handler_with_os("Linux")
            handler.coins_rpc = {}
            handler.running = True
            try:
                handler.check_valid_xlite_coins_rpc(runonce=True)
            except KeyboardInterrupt:
                pass

            self.assertFalse(handler.valid_coins_rpc)

    def test_check_valid_xlite_coins_rpc_invalid_response(self):
        """Test checking coins RPC with invalid response."""
        mock_rpc_server = MagicMock()
        mock_rpc_server.send_rpc_request.return_value = None

        with patch('time.sleep', side_effect=KeyboardInterrupt):
            handler = self._create_handler_with_os("Linux")
            handler.coins_rpc = {"test": mock_rpc_server}
            handler.xlite_daemon_confs_local = {"test": {"rpcEnabled": True}}
            handler.running = True
            try:
                handler.check_valid_xlite_coins_rpc(runonce=True)
            except KeyboardInterrupt:
                pass

            mock_rpc_server.send_rpc_request.assert_called_once_with("getinfo")
            self.assertFalse(handler.valid_coins_rpc)

    # ============================================================================
    # Start/Stop Tests
    # ============================================================================

    def test_start_xlite_linux(self):
        """Test starting XLite on Linux."""
        self.mock_container.system = "Linux"
        with patch('os.path.exists', return_value=True), \
                patch.object(self.handler, 'start_process') as mock_start:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_start.return_value = mock_process

            self.handler.start_xlite(env_vars=["ENV_VAR=value"])

            expected_cmd = ['/mock/aio_folder/XLite-1.0.7-linux/xlite']
            mock_start.assert_called_once()
            args, kwargs = mock_start.call_args
            self.assertEqual(args[0], expected_cmd)

    def test_start_xlite_windows(self):
        """Test starting XLite on Windows."""
        self.mock_container.system = 'Windows'
        with patch('os.path.exists', return_value=True), \
                patch('utilities.bin_handlers.xlite_handler.winreg', create=True), \
                patch('utilities.bin_handlers.xlite_handler.check_vc_redist_installed') as mock_check_vc, \
                patch.object(XliteHandler, 'start_process') as mock_start:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_start.return_value = mock_process

            handler = self._create_handler_with_os("Windows")
            handler.start_xlite()

            expected_cmd = ['/mock/aio_folder/XLite-1.0.7-win-x64/XLite.exe', '--in-process-gpu']
            mock_start.assert_called_once()
            args, kwargs = mock_start.call_args
            self.assertEqual(args[0], expected_cmd)

    def test_start_xlite_darwin(self):
        """Test starting XLite on Darwin."""
        self.mock_container.system = 'Darwin'
        with patch('os.path.exists', return_value=True), \
                patch.object(XliteHandler, 'handle_dmg') as mock_handle_dmg, \
                patch.object(XliteHandler, 'start_process') as mock_start:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_start.return_value = mock_process

            handler = self._create_handler_with_os("Darwin")
            handler.dmg_mount_path = '/Volumes/XliteVolume'
            
            # Set executable_path for Darwin (it's set differently than other OS)
            handler.executable_path = '/mock/aio_folder/XLite-1.0.7-mac.dmg'

            handler.start_xlite()

            mock_handle_dmg.assert_called_once_with("mount")
            mock_start.assert_called_once()

    def test_start_xlite_download_fallback(self):
        """Test starting XLite triggers download when executable not found."""
        # Get the original executable_path before patching
        original_executable_path = self.handler.executable_path
        
        with patch('utilities.bin_handlers.xlite_handler.os.path.exists') as mock_exists, \
                patch.object(self.handler, 'download_xlite_bin') as mock_download, \
                patch.object(self.handler, 'start_process') as mock_start:
            # First call returns False (executable not found)
            # After download, subsequent calls return True
            mock_exists.side_effect = lambda path: path != original_executable_path or mock_exists.call_count > 1
            
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_start.return_value = mock_process
            
            # Set executable_path after download to simulate successful download
            def set_executable_path():
                self.handler.executable_path = original_executable_path
            mock_download.side_effect = set_executable_path

            self.handler.start_xlite()

            mock_download.assert_called_once()
            mock_start.assert_called_once()

    def test_start_xlite_malformed_env_vars(self):
        """Test starting XLite with malformed environment variables."""
        with patch('os.path.exists', return_value=True), \
                patch.object(self.handler, 'start_process') as mock_start:
            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_start.return_value = mock_process

            self.handler.start_xlite(env_vars=["INVALID_VAR", "VALID_VAR=value"])

            mock_start.assert_called_once()
            args, kwargs = mock_start.call_args
            self.assertEqual(kwargs.get('env_vars', {}), {'VALID_VAR': 'value'})

    def test_start_xlite_exception_handling(self):
        """Test exception handling in start_xlite."""
        with patch('os.path.exists', return_value=True), \
                patch.object(self.handler, 'start_process', side_effect=Exception("Test error")), \
                patch('utilities.bin_handlers.xlite_handler.logger.error') as mock_error:
            with self.assertRaises(Exception) as ctx:
                self.handler.start_xlite()
            self.assertEqual(str(ctx.exception), "Test error")
            mock_error.assert_called()

    def test_close_xlite_with_process(self):
        """Test closing XLite when process exists."""
        mock_process = MagicMock()
        mock_process.pid = 123
        self.handler.xlite_process = mock_process

        with patch.object(self.handler, 'graceful_terminate') as mock_graceful, \
                patch.object(self.handler, 'terminate_processes') as mock_terminate:
            self.handler.close_xlite()

            mock_graceful.assert_called_once_with(timeout=10)
            mock_terminate.assert_called()

    def test_close_xlite_no_process(self):
        """Test closing XLite when no process exists."""
        self.handler.xlite_process = None

        with patch.object(self.handler, 'terminate_processes') as mock_terminate:
            self.handler.close_xlite()
            mock_terminate.assert_called()

    # ============================================================================
    # DMG Tests
    # ============================================================================

    def test_unmount_dmg(self):
        """Test unmounting DMG on Darwin."""
        self.mock_container.system = "Darwin"
        with patch.object(self.handler, 'handle_dmg') as mock_handle_dmg:
            self.handler.unmount_dmg()
            mock_handle_dmg.assert_called_once_with("unmount")

    def test_unmount_dmg_not_darwin(self):
        """Test unmounting DMG on non-Darwin systems."""
        self.mock_container.system = "Linux"
        with patch.object(self.handler, 'handle_dmg') as mock_handle_dmg:
            self.handler.unmount_dmg()
            mock_handle_dmg.assert_not_called()


if __name__ == '__main__':
    unittest.main()
