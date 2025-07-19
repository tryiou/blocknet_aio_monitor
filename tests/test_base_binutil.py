import os
import tempfile
import unittest
import zipfile
from unittest.mock import patch, MagicMock, mock_open

import requests

from utilities.bin_handlers.base_binutil import BaseBinUtil


class TestBaseBinUtil(unittest.TestCase):
    """Test cases for BaseBinUtil core functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.base_binutil = BaseBinUtil("test_app")
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init(self):
        """Test BaseBinUtil initialization."""
        self.assertEqual(self.base_binutil.app_name, "test_app")
        self.assertIsNone(self.base_binutil.executable_path)
        self.assertIsNone(self.base_binutil.dmg_mount_path)
        self.assertIsNone(self.base_binutil.binary_percent_download)
        self.assertFalse(self.base_binutil.downloading_bin)
        self.assertEqual(self.base_binutil.system, os.name)
        self.assertIsNone(self.base_binutil.process)

    def test_download_file_zip(self):
        """Test downloading and extracting ZIP files."""
        with patch('requests.get') as mock_get, \
                patch('os.path.getsize') as mock_getsize, \
                patch('os.remove') as mock_remove, \
                patch('zipfile.ZipFile') as mock_zipfile:
            # Mock response
            mock_response = MagicMock()
            mock_response.headers = {'Content-Length': '1000'}
            mock_response.iter_content.return_value = [b'test data']
            mock_get.return_value = mock_response

            mock_getsize.return_value = 1000

            # Mock zip extraction
            mock_zip = MagicMock()
            mock_zipfile.return_value.__enter__.return_value = mock_zip

            self.base_binutil.download_file(
                "http://example.com/test.zip",
                os.path.join(self.temp_dir, "test.zip"),
                os.path.join(self.temp_dir, "test.exe"),
                self.temp_dir,
                "nt",
                "progress_attr",
                self.base_binutil
            )

            mock_zip.extractall.assert_called_once_with(self.temp_dir)
            mock_remove.assert_called_once()

    def test_download_file_tar_gz(self):
        """Test downloading and extracting TAR.GZ files."""
        with patch('requests.get') as mock_get, \
                patch('os.path.getsize') as mock_getsize, \
                patch('os.remove') as mock_remove, \
                patch('tarfile.open') as mock_tarfile:
            # Mock response
            mock_response = MagicMock()
            mock_response.headers = {'Content-Length': '1000'}
            mock_response.iter_content.return_value = [b'test data']
            mock_get.return_value = mock_response

            mock_getsize.return_value = 1000

            # Mock tar extraction
            mock_tar = MagicMock()
            mock_tarfile.return_value.__enter__.return_value = mock_tar

            self.base_binutil.download_file(
                "http://example.com/test.tar.gz",
                os.path.join(self.temp_dir, "test.tar.gz"),
                os.path.join(self.temp_dir, "test.exe"),
                self.temp_dir,
                "posix",
                "progress_attr",
                self.base_binutil
            )

            mock_tar.extractall.assert_called_once_with(self.temp_dir)
            mock_remove.assert_called_once()

    def test_download_file_dmg_darwin(self):
        """Test downloading DMG files on Darwin."""
        with patch('requests.get') as mock_get, \
                patch('os.path.getsize') as mock_getsize, \
                patch('os.rename') as mock_rename, \
                patch('utilities.global_variables.system', 'Darwin'):
            # Mock response
            mock_response = MagicMock()
            mock_response.headers = {'Content-Length': '1000'}
            mock_response.iter_content.return_value = [b'test data']
            mock_get.return_value = mock_response

            mock_getsize.return_value = 1000

            self.base_binutil.download_file(
                "http://example.com/test.dmg",
                os.path.join(self.temp_dir, "test.dmg"),
                os.path.join(self.temp_dir, "final.dmg"),
                self.temp_dir,
                "posix",
                "progress_attr",
                self.base_binutil
            )

            mock_rename.assert_called_once()

    def test_download_file_size_mismatch(self):
        """Test handling of download size mismatch."""
        with patch('requests.get') as mock_get, \
                patch('os.path.getsize') as mock_getsize, \
                patch('os.remove') as mock_remove:
            # Mock response
            mock_response = MagicMock()
            mock_response.headers = {'Content-Length': '1000'}
            mock_response.iter_content.return_value = [b'test data']
            mock_get.return_value = mock_response

            # Simulate size mismatch
            mock_getsize.return_value = 500

            with self.assertRaises(ValueError) as context:
                self.base_binutil.download_file(
                    "http://example.com/test.zip",
                    os.path.join(self.temp_dir, "test.zip"),
                    os.path.join(self.temp_dir, "test.exe"),
                    self.temp_dir,
                    "nt",
                    "progress_attr",
                    self.base_binutil
                )

            self.assertEqual(str(context.exception), "Download size mismatch")
            mock_remove.assert_called_once()

    def test_download_file_network_error(self):
        """Test handling of network errors during download."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")

            with self.assertRaises(requests.RequestException):
                self.base_binutil.download_file(
                    "http://example.com/test.zip",
                    os.path.join(self.temp_dir, "test.zip"),
                    os.path.join(self.temp_dir, "test.exe"),
                    self.temp_dir,
                    "nt",
                    "progress_attr",
                    self.base_binutil
                )

    def test_start_process(self):
        """Test starting a process."""
        with patch('subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_popen.return_value = mock_process

            result = self.base_binutil.start_process(["test", "command"], cwd="/test")

            mock_popen.assert_called_once()
            self.assertEqual(result, mock_process)
            self.assertEqual(self.base_binutil.process, mock_process)

    def test_start_process_with_env_vars(self):
        """Test starting a process with environment variables."""
        with patch('subprocess.Popen') as mock_popen, \
                patch('os.environ.copy') as mock_env_copy:
            mock_process = MagicMock()
            mock_popen.return_value = mock_process
            mock_env_copy.return_value = {"EXISTING": "value"}

            env_vars = {"NEW": "value"}
            self.base_binutil.start_process(["test"], env_vars=env_vars)

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            self.assertIn('env', call_args.kwargs)
            self.assertEqual(call_args.kwargs['env'], {"EXISTING": "value", "NEW": "value"})

    def test_graceful_terminate_success(self):
        """Test successful graceful termination."""
        with patch('subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            mock_process.wait.return_value = None
            self.base_binutil.process = mock_process

            self.base_binutil.graceful_terminate()

            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once_with(timeout=10)
            self.assertIsNone(self.base_binutil.process)

    def test_graceful_terminate_timeout(self):
        """Test graceful termination with timeout fallback to force kill."""
        import subprocess
        with patch('subprocess.Popen') as mock_popen, \
                patch.object(self.base_binutil, 'force_kill') as mock_force_kill:
            mock_process = MagicMock()
            mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=10)
            self.base_binutil.process = mock_process

            self.base_binutil.graceful_terminate()

            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once_with(timeout=10)
            mock_force_kill.assert_called_once()

    def test_force_kill(self):
        """Test force killing a process."""
        with patch('subprocess.Popen') as mock_popen:
            mock_process = MagicMock()
            self.base_binutil.process = mock_process

            self.base_binutil.force_kill()

            mock_process.kill.assert_called_once()
            self.assertIsNone(self.base_binutil.process)

    def test_force_kill_error_handling(self):
        """Test error handling in force kill."""
        with patch('subprocess.Popen') as mock_popen, \
                patch('utilities.bin_handlers.base_binutil.logger.error') as mock_log_error:
            mock_process = MagicMock()
            mock_process.kill.side_effect = Exception("Kill error")
            self.base_binutil.process = mock_process

            self.base_binutil.force_kill()

            mock_process.kill.assert_called_once()
            mock_log_error.assert_called_once()

    def test_terminate_processes_empty_pids(self):
        """Test terminate_processes with empty PID list."""
        with patch('utilities.bin_handlers.base_binutil.logger.warning') as mock_log_warning:
            self.base_binutil.terminate_processes([], "test_app")
            mock_log_warning.assert_called_once_with("No PIDs to terminate for test_app")

    def test_terminate_processes_success(self):
        """Test successful process termination."""
        with patch('psutil.Process') as mock_process_class, \
                patch('utilities.bin_handlers.base_binutil.logger.info') as mock_log_info:
            mock_process = MagicMock()
            mock_process_class.return_value = mock_process

            self.base_binutil.terminate_processes([1234], "test_app")

            mock_process_class.assert_called_once_with(1234)
            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once_with(timeout=10)
            mock_log_info.assert_called_once()

    def test_terminate_processes_no_such_process(self):
        """Test handling of non-existent processes."""
        import psutil
        with patch('psutil.Process') as mock_process_class, \
                patch('utilities.bin_handlers.base_binutil.logger.warning') as mock_log_warning:
            mock_process_class.side_effect = psutil.NoSuchProcess(pid=1234)

            self.base_binutil.terminate_processes([1234], "test_app")

            mock_log_warning.assert_called_once()

    def test_handle_dmg_wrong_os(self):
        """Test handle_dmg with wrong OS."""
        with patch('utilities.global_variables.system', 'Linux'), \
                patch('utilities.bin_handlers.base_binutil.logger.warning') as mock_log_warning:
            self.base_binutil.handle_dmg("mount")
            mock_log_warning.assert_called_once_with("Call handle_dmg with wrong OS, Linux ?")

    def test_handle_dmg_already_mounted(self):
        """Test handle_dmg when already mounted."""
        with patch('utilities.global_variables.system', 'Darwin'), \
                patch('os.path.ismount') as mock_ismount, \
                patch('utilities.bin_handlers.base_binutil.logger.warning') as mock_log_warning:
            mock_ismount.return_value = True

            self.base_binutil.dmg_mount_path = "/Volumes/test"
            self.base_binutil.handle_dmg("mount")

            mock_log_warning.assert_called_once_with("/Volumes/test is already mounted")

    def test_handle_dmg_mount_success(self):
        """Test successful DMG mount on Darwin."""
        with patch('utilities.global_variables.system', 'Darwin'), \
                patch('os.path.ismount') as mock_ismount, \
                patch('subprocess.run') as mock_run, \
                patch('utilities.bin_handlers.base_binutil.logger.info') as mock_log_info:
            mock_ismount.return_value = False
            self.base_binutil.dmg_mount_path = "/Volumes/test"

            self.base_binutil.handle_dmg("mount")

            mock_run.assert_called_once_with(["hdiutil", "attach", self.base_binutil.executable_path], check=True)
            mock_log_info.assert_called_once_with(
                f"Mounted DMG {self.base_binutil.executable_path} to {self.base_binutil.dmg_mount_path}")

    def test_handle_dmg_unmount_success(self):
        """Test successful DMG unmount on Darwin."""
        with patch('utilities.global_variables.system', 'Darwin'), \
                patch('os.path.ismount') as mock_ismount, \
                patch('subprocess.run') as mock_run, \
                patch('utilities.bin_handlers.base_binutil.logger.info') as mock_log_info:
            mock_ismount.return_value = True
            self.base_binutil.dmg_mount_path = "/Volumes/test"

            self.base_binutil.handle_dmg("unmount")

            mock_run.assert_called_once_with(["hdiutil", "detach", self.base_binutil.dmg_mount_path], check=True)
            mock_log_info.assert_called_once_with(f"Unmounted DMG from {self.base_binutil.dmg_mount_path}")

    def test_handle_dmg_unmount_not_mounted(self):
        """Test unmount when DMG is not mounted."""
        with patch('utilities.global_variables.system', 'Darwin'), \
                patch('os.path.ismount') as mock_ismount, \
                patch('utilities.bin_handlers.base_binutil.logger.warning') as mock_log_warning:
            mock_ismount.return_value = False
            self.base_binutil.dmg_mount_path = "/Volumes/test"

            self.base_binutil.handle_dmg("unmount")

            mock_log_warning.assert_called_once_with("/Volumes/test is not mounted")

    def test_download_binary_sets_flag(self):
        """Test download_binary sets downloading flag correctly."""
        with patch.object(self.base_binutil, 'download_file') as mock_download:
            mock_download.return_value = None

            self.base_binutil.download_binary(
                "http://example.com/test.zip",
                "test.zip",
                "test.exe",
                "/test/path"
            )

            self.assertFalse(self.base_binutil.downloading_bin)

    def test_download_file_timeout(self):
        """Test handling of timeout during download."""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

            with self.assertRaises(requests.exceptions.Timeout):
                self.base_binutil.download_file(
                    "http://example.com/test.zip",
                    os.path.join(self.temp_dir, "test.zip"),
                    os.path.join(self.temp_dir, "test.exe"),
                    self.temp_dir,
                    "nt",
                    "progress_attr",
                    self.base_binutil
                )

    def test_download_file_http_error(self):
        """Test handling of HTTP error responses."""
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
            mock_get.return_value = mock_response

            with self.assertRaises(requests.exceptions.HTTPError):
                self.base_binutil.download_file(
                    "http://example.com/test.zip",
                    os.path.join(self.temp_dir, "test.zip"),
                    os.path.join(self.temp_dir, "test.exe"),
                    self.temp_dir,
                    "nt",
                    "progress_attr",
                    self.base_binutil
                )

    def test_download_file_permission_error(self):
        """Test handling of permission errors during file write."""
        with patch('requests.get') as mock_get, \
                patch('builtins.open', mock_open()) as mock_file, \
                patch('utilities.bin_handlers.base_binutil.logger.error') as mock_log_error:
            mock_response = MagicMock()
            mock_response.headers = {'Content-Length': '1000'}
            mock_response.iter_content.return_value = [b'test data']
            mock_get.return_value = mock_response

            mock_file.side_effect = PermissionError("Permission denied")

            with self.assertRaises(PermissionError):
                self.base_binutil.download_file(
                    "http://example.com/test.zip",
                    os.path.join(self.temp_dir, "test.zip"),
                    os.path.join(self.temp_dir, "test.exe"),
                    self.temp_dir,
                    "nt",
                    "progress_attr",
                    self.base_binutil
                )
            mock_log_error.assert_called_once_with("Permission error writing file: Permission denied")

    def test_graceful_terminate_no_process(self):
        """Test graceful_terminate when no process exists."""
        with patch('utilities.bin_handlers.base_binutil.logger.info') as mock_log_info:
            self.base_binutil.process = None
            self.base_binutil.graceful_terminate()
            mock_log_info.assert_called_once_with("No running process to terminate")

    def test_terminate_processes_timeout_kill(self):
        """Test process termination with timeout fallback to kill."""
        import psutil
        with patch('psutil.Process') as mock_process_class, \
                patch('utilities.bin_handlers.base_binutil.logger.warning') as mock_log_warning:
            mock_process = MagicMock()
            mock_process_class.return_value = mock_process
            # Create TimeoutExpired exception with required parameters
            mock_process.wait.side_effect = psutil.TimeoutExpired(10)

            self.base_binutil.terminate_processes([1234], "test_app")

            mock_process.kill.assert_called_once()
            mock_log_warning.assert_called_once_with("Process test_app PID 1234: Timeout expired, killed process")

    def test_terminate_processes_multiple_pids(self):
        """Test terminating multiple PIDs."""
        with patch('psutil.Process') as mock_process_class, \
                patch('utilities.bin_handlers.base_binutil.logger.info') as mock_log_info:
            mock_process1 = MagicMock()
            mock_process2 = MagicMock()
            mock_process_class.side_effect = [mock_process1, mock_process2]

            self.base_binutil.terminate_processes([1234, 5678], "test_app")

            self.assertEqual(mock_process_class.call_count, 2)
            mock_log_info.assert_any_call("Process test_app PID 1234 terminated successfully")
            mock_log_info.assert_any_call("Process test_app PID 5678 terminated successfully")

    def test_start_process_empty_command(self):
        """Test starting a process with empty command list."""
        with self.assertRaises(ValueError) as context:
            self.base_binutil.start_process([])
        self.assertEqual(str(context.exception), "Command list cannot be empty")

    def test_download_file_zip_extract_error(self):
        """Test handling of ZIP extraction failures."""
        with patch('requests.get') as mock_get, \
                patch('os.path.getsize') as mock_getsize, \
                patch('os.remove') as mock_remove, \
                patch('zipfile.ZipFile') as mock_zipfile:
            mock_response = MagicMock()
            mock_response.headers = {'Content-Length': '1000'}
            mock_response.iter_content.return_value = [b'test data']
            mock_get.return_value = mock_response
            mock_getsize.return_value = 1000

            mock_zipfile.side_effect = zipfile.BadZipFile("Invalid zip file")

            with self.assertRaises(zipfile.BadZipFile):
                self.base_binutil.download_file(
                    "http://example.com/test.zip",
                    os.path.join(self.temp_dir, "test.zip"),
                    os.path.join(self.temp_dir, "test.exe"),
                    self.temp_dir,
                    "nt",
                    "progress_attr",
                    self.base_binutil
                )


if __name__ == '__main__':
    unittest.main()
