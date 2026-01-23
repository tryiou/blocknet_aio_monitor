"""
Test suite for XliteReverseProxyHandler following DRY/SOC/KISS principles.
"""

import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch, mock_open

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.bin_handlers.xlite_reverse_proxy_handler import XliteReverseProxyHandler


class TestXliteReverseProxyHandler(unittest.TestCase):
    """Test suite for XliteReverseProxyHandler class."""

    def setUp(self):
        """Set up common mocks and patches for all tests."""
        self.patches = []
        self._setup_global_variables()
        self._apply_common_patches()
        self.handler = XliteReverseProxyHandler()

    def _setup_global_variables(self):
        """Set up global_variables mock."""
        self.mock_global_variables = MagicMock()
        self.mock_global_variables.system = 'Linux'
        self.mock_global_variables.machine = 'x86_64'
        self.mock_global_variables.aio_folder = '/mock/aio_folder'
        self.mock_global_variables.xlite_reverse_proxy_release_url = (
            'https://github.com/blocknetdx/xlite-reverse-proxy/releases/download/v1.0.0/xlite-reverse-proxy-v1.0.0-linux-x64.tar.gz'
        )
        self.mock_global_variables.xlite_reverse_proxy_bin = 'xlite-reverse-proxy'

    def _apply_common_patches(self):
        """Apply common patches needed for handler initialization."""
        self.patches.append(
            patch('utilities.bin_handlers.xlite_reverse_proxy_handler.global_variables', self.mock_global_variables))
        self.patches.append(
            patch('utilities.bin_handlers.xlite_reverse_proxy_handler.os.path.exists', return_value=True))
        self.patches.append(patch('utilities.bin_handlers.xlite_reverse_proxy_handler.os.makedirs'))
        self.patches.append(patch('utilities.bin_handlers.xlite_reverse_proxy_handler.socket.socket'))
        self.patches.append(patch('utilities.bin_handlers.xlite_reverse_proxy_handler.subprocess.Popen'))
        self.patches.append(patch('utilities.bin_handlers.xlite_reverse_proxy_handler.requests.get'))
        self.patches.append(patch('re.search'))  # Patch re module directly

        # Start all patches
        for p in self.patches:
            p.start()

    def tearDown(self):
        """Clean up patches after each test."""
        for p in self.patches:
            p.stop()

    # ============================================================================
    # Initialization Tests
    # ============================================================================

    def test_init(self):
        """Test handler initialization sets up expected attributes."""
        self.assertEqual(self.handler.app_name, "XliteReverseProxy")
        self.assertEqual(self.handler.PORT, 11111)
        self.assertEqual(self.handler.release_url, self.mock_global_variables.xlite_reverse_proxy_release_url)
        self.assertEqual(self.handler.bin_name, self.mock_global_variables.xlite_reverse_proxy_bin)
        self.assertIsNotNone(self.handler.executable_path)
        self.assertIsNone(self.handler.process)
        self.assertFalse(self.handler.running_locally)

    def test_init_missing_config(self):
        """Test handler initialization when config is missing."""
        self.mock_global_variables.xlite_reverse_proxy_release_url = None
        self.mock_global_variables.xlite_reverse_proxy_bin = None

        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.logger') as mock_logger:
            handler = XliteReverseProxyHandler()
            self.assertIsNone(handler.executable_path)
            mock_logger.error.assert_called_once_with("Reverse proxy not configured for current system")

    def test_init_executable_path_extraction(self):
        """Test that executable path is correctly extracted from URL."""
        # Mock re.search to return a match object with group(1) returning "1.0.0"
        mock_match = MagicMock()
        mock_match.group.return_value = "1.0.0"

        with patch('re.search', return_value=mock_match):
            handler = XliteReverseProxyHandler()
            # The path should be constructed from aio_folder, version folder, and bin_name
            expected_path = '/mock/aio_folder/xlite-reverse-proxy-1.0.0/xlite-reverse-proxy'
            self.assertEqual(handler.executable_path, expected_path)

    # ============================================================================
    # Port Occupied Tests
    # ============================================================================

    def test_port_occupied_true(self):
        """Test port_occupied returns True when port is in use."""
        mock_socket_instance = MagicMock()
        mock_socket_instance.connect_ex.return_value = 0  # Port is occupied

        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.socket.socket') as mock_socket_class:
            mock_socket_class.return_value.__enter__.return_value = mock_socket_instance
            result = self.handler.port_occupied()
            self.assertTrue(result)
            mock_socket_instance.connect_ex.assert_called_once_with(('localhost', 11111))

    def test_port_occupied_false(self):
        """Test port_occupied returns False when port is available."""
        mock_socket_instance = MagicMock()
        mock_socket_instance.connect_ex.return_value = 1  # Port is available

        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.socket.socket') as mock_socket_class:
            mock_socket_class.return_value.__enter__.return_value = mock_socket_instance
            result = self.handler.port_occupied()
            self.assertFalse(result)
            mock_socket_instance.connect_ex.assert_called_once_with(('localhost', 11111))

    # ============================================================================
    # Start Tests
    # ============================================================================

    def test_start_success(self):
        """Test successful proxy start."""
        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.os.path.exists', return_value=False), \
                patch('utilities.bin_handlers.xlite_reverse_proxy_handler.os.makedirs'), \
                patch('utilities.bin_handlers.xlite_reverse_proxy_handler.socket.socket') as mock_socket_class, \
                patch('utilities.bin_handlers.xlite_reverse_proxy_handler.subprocess.Popen') as mock_popen, \
                patch('utilities.bin_handlers.xlite_reverse_proxy_handler.logger') as mock_logger:
            mock_socket = MagicMock()
            mock_socket.connect_ex.return_value = 1  # Port available
            mock_socket_class.return_value.__enter__.return_value = mock_socket

            mock_process = MagicMock()
            mock_process.pid = 12345
            mock_popen.return_value = mock_process

            # Mock download_standalone_binary to return True
            with patch.object(self.handler, 'download_standalone_binary', return_value=True):
                self.handler.start()

                # Verify process was started
                self.assertEqual(self.handler.process, mock_process)
                self.assertTrue(self.handler.running_locally)

                # Verify logger was called
                mock_logger.info.assert_called()
                self.assertIn("Proxy started", str(mock_logger.info.call_args))

    def test_start_port_occupied(self):
        """Test start when port is already occupied."""
        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.socket.socket') as mock_socket_class, \
                patch('utilities.bin_handlers.xlite_reverse_proxy_handler.logger') as mock_logger:
            mock_socket = MagicMock()
            mock_socket.connect_ex.return_value = 0  # Port occupied
            mock_socket_class.return_value.__enter__.return_value = mock_socket

            self.handler.start()

            # Verify process was not started
            self.assertIsNone(self.handler.process)
            self.assertFalse(self.handler.running_locally)

            # Verify logger was called
            mock_logger.info.assert_called_once_with("Port 11111 occupied (external proxy detected)")

    def test_start_missing_config(self):
        """Test start when config is missing."""
        self.mock_global_variables.xlite_reverse_proxy_release_url = None
        self.mock_global_variables.xlite_reverse_proxy_bin = None

        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.logger') as mock_logger:
            handler = XliteReverseProxyHandler()
            handler.start()

            # Verify logger was called (called twice: once in __init__, once in start)
            self.assertEqual(mock_logger.error.call_count, 2)
            mock_logger.error.assert_called_with("Proxy config missing")

    def test_start_download_fails(self):
        """Test start when download fails."""
        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.os.path.exists', return_value=False), \
                patch('utilities.bin_handlers.xlite_reverse_proxy_handler.os.makedirs'), \
                patch('utilities.bin_handlers.xlite_reverse_proxy_handler.socket.socket') as mock_socket_class, \
                patch('utilities.bin_handlers.xlite_reverse_proxy_handler.logger') as mock_logger:
            mock_socket = MagicMock()
            mock_socket.connect_ex.return_value = 1  # Port available
            mock_socket_class.return_value.__enter__.return_value = mock_socket

            # Mock download_standalone_binary to return False
            with patch.object(self.handler, 'download_standalone_binary', return_value=False):
                self.handler.start()

                # Verify process was not started
                self.assertIsNone(self.handler.process)
                self.assertFalse(self.handler.running_locally)

                # Verify logger was called
                mock_logger.error.assert_called_once_with("Proxy download failed")

    def test_start_exception_during_start(self):
        """Test start when an exception occurs during process start."""
        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.os.path.exists', return_value=False), \
                patch('utilities.bin_handlers.xlite_reverse_proxy_handler.os.makedirs'), \
                patch('utilities.bin_handlers.xlite_reverse_proxy_handler.socket.socket') as mock_socket_class, \
                patch('utilities.bin_handlers.xlite_reverse_proxy_handler.subprocess.Popen') as mock_popen, \
                patch('utilities.bin_handlers.xlite_reverse_proxy_handler.logger') as mock_logger:
            mock_socket = MagicMock()
            mock_socket.connect_ex.return_value = 1  # Port available
            mock_socket_class.return_value.__enter__.return_value = mock_socket

            mock_popen.side_effect = Exception("Test exception")

            # Mock download_standalone_binary to return True
            with patch.object(self.handler, 'download_standalone_binary', return_value=True):
                self.handler.start()

                # Verify process was not started
                self.assertIsNone(self.handler.process)
                self.assertFalse(self.handler.running_locally)

                # Verify logger was called
                mock_logger.error.assert_called_once()
                self.assertIn("Proxy start failed", str(mock_logger.error.call_args))

    # ============================================================================
    # Stop Tests
    # ============================================================================

    def test_stop_success(self):
        """Test successful proxy stop."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process is running
        mock_process.wait.return_value = None  # Process exits successfully
        self.handler.process = mock_process
        self.handler.running_locally = True

        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.logger') as mock_logger:
            self.handler.stop()

            # Verify process was terminated
            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once_with(timeout=5)

            # Verify handler state was reset
            self.assertIsNone(self.handler.process)
            self.assertFalse(self.handler.running_locally)

            # Verify logger was called
            mock_logger.info.assert_called_with("Proxy terminated gracefully")

    def test_stop_timeout(self):
        """Test stop when process doesn't terminate within timeout."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process is running
        # First wait times out, second wait succeeds
        mock_process.wait.side_effect = [subprocess.TimeoutExpired("Process", 3), None]
        self.handler.process = mock_process
        self.handler.running_locally = True

        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.logger') as mock_logger:
            with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.os.killpg'):
                with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.os.getpgid', return_value=12345):
                    self.handler.stop()

            # Verify process was terminated and killed
            mock_process.terminate.assert_called_once()
            mock_process.kill.assert_called_once()

            # Verify handler state was reset
            self.assertIsNone(self.handler.process)
            self.assertFalse(self.handler.running_locally)

            # Verify logger was called
            mock_logger.warning.assert_called_once_with("Proxy didn't terminate gracefully, forcing kill")
            # Check that info was called with the expected messages
            info_calls = [str(call) for call in mock_logger.info.call_args_list]
            self.assertTrue(any("Terminating proxy (PID: 12345)" in call for call in info_calls))
            self.assertTrue(any("Proxy killed forcefully" in call for call in info_calls))

    def test_stop_exception(self):
        """Test stop when an exception occurs."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Process is running
        mock_process.terminate.side_effect = Exception("Test exception")
        self.handler.process = mock_process
        self.handler.running_locally = True

        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.logger') as mock_logger:
            with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.os.killpg'):
                with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.os.getpgid', return_value=12345):
                    self.handler.stop()

            # Verify logger was called with error
            mock_logger.error.assert_called_once()
            self.assertIn("Proxy stop error", str(mock_logger.error.call_args))

            # Verify handler state was still reset
            self.assertIsNone(self.handler.process)
            self.assertFalse(self.handler.running_locally)

    def test_stop_not_running_locally(self):
        """Test stop when proxy is not running locally."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 0  # Process already exited
        self.handler.process = mock_process
        self.handler.running_locally = False

        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.logger') as mock_logger:
            self.handler.stop()

            # Verify process was not terminated
            mock_process.terminate.assert_not_called()

            # Verify logger was not called
            mock_logger.info.assert_not_called()
            mock_logger.error.assert_not_called()

    def test_stop_no_process(self):
        """Test stop when there is no process."""
        self.handler.process = None
        self.handler.running_locally = True

        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.logger') as mock_logger:
            self.handler.stop()

            # Verify logger was not called
            mock_logger.info.assert_not_called()
            mock_logger.error.assert_not_called()

    def test_stop_already_exited(self):
        """Test stop when process has already exited."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 0  # Process already exited
        self.handler.process = mock_process
        self.handler.running_locally = True

        with patch('utilities.bin_handlers.xlite_reverse_proxy_handler.logger') as mock_logger:
            self.handler.stop()

            # Verify process was not terminated (already dead)
            mock_process.terminate.assert_not_called()

            # Verify handler state was reset
            self.assertIsNone(self.handler.process)
            self.assertFalse(self.handler.running_locally)

            # Verify logger was called
            mock_logger.info.assert_called_once_with("Proxy already stopped")


if __name__ == '__main__':
    unittest.main()
