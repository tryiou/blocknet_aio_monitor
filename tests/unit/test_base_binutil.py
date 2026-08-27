"""
Improved test suite for BaseBinUtil following DRY/SOC/KISS principles.

Key improvements:
1. DRY: Reusable fixtures, parametrized tests, eliminated duplicate code
2. SOC: Tests grouped by concern (download, process, DMG)
3. KISS: Simplified assertions, clear test logic, removed unnecessary complexity
4. Coverage: Added tests for download_standalone_binary and edge cases
"""

import os
import sys
import tarfile
import tempfile
import unittest
import zipfile
from unittest.mock import MagicMock, call, mock_open, patch

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import subprocess

import psutil
import pytest
import requests

from utilities.app_container import AppContainer, get_container
from utilities.bin_handlers.base_binutil import BaseBinUtil

# =============================================================================
# FIXTURES & TEST UTILITIES
# =============================================================================


class BaseBinUtilTestCase(unittest.TestCase):
    """Base test case with reusable fixtures."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        # Create a default mock container
        mock_container = MagicMock()
        mock_container.system = "Linux"
        mock_container.machine = "x86_64"
        mock_container.aio_folder = "/test/aio_folder"
        mock_container.conf_data = MagicMock()
        self.base_binutil = BaseBinUtil("test_app", mock_container)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_mock_response(self, content_length=1000, data=b"test data"):
        """Create a mock HTTP response."""
        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": str(content_length)}
        mock_response.iter_content.return_value = [data]
        return mock_response

    def create_mock_process(self):
        """Create a mock subprocess."""
        mock_process = MagicMock()
        mock_process.wait.return_value = None
        return mock_process

    def create_mock_psutil_process(self):
        """Create a mock psutil process."""
        mock_process = MagicMock()
        mock_process.wait.return_value = None
        return mock_process


@pytest.fixture
def mock_container():
    """Create a mock AppContainer for testing."""
    container = MagicMock()

    # Set up common properties
    container.system = "Linux"
    container.machine = "x86_64"
    container.aio_folder = "/test/aio_folder"
    container.theme_path = "/test/theme.json"
    container.dirpath = "/test/app_dir"

    # Binary configurations
    container.blocknet_bin = "blocknetd"
    container.blockdx_bin = "blockdx"
    container.xlite_bin = "xlite"
    container.xlite_daemon_bin = "xlited"
    container.xlite_reverse_proxy_bin = "xlite-reverse-proxy"

    # Release URLs
    container.blocknet_release_url = "http://test.com/blocknet.tar.gz"
    container.blockdx_release_url = "http://test.com/blockdx.tar.gz"
    container.xlite_release_url = "http://test.com/xlite.tar.gz"
    container.xlite_reverse_proxy_release_url = "http://test.com/xlite-reverse-proxy.tar.gz"

    # Current paths
    container.blockdx_curpath = "BLOCK-DX-1.0.0"
    container.xlite_curpath = "XLite-1.0.0"

    # Volume names (macOS specific)
    container.blockdx_volume_name = None
    container.xlite_volume_name = None

    # Mock conf_data access
    container.conf_data = MagicMock()

    return container


@pytest.fixture
def mock_container_darwin():
    """Create a mock AppContainer for Darwin."""
    container = MagicMock()

    # macOS-specific configuration
    container.system = "Darwin"
    container.machine = "arm64"
    container.aio_folder = "/test/aio_folder"
    container.theme_path = "/test/theme.json"
    container.dirpath = "/test/app_dir"

    # Binary configurations
    container.blocknet_bin = "Blocknet"
    container.blockdx_bin = "Block DX"
    container.xlite_bin = "XLite"
    container.xlite_daemon_bin = "XLite Daemon"
    container.xlite_reverse_proxy_bin = "xlite-reverse-proxy"

    # Release URLs
    container.blocknet_release_url = "http://test.com/Blocknet.dmg"
    container.blockdx_release_url = "http://test.com/Block-DX-1.0.0.dmg"
    container.xlite_release_url = "http://test.com/XLite-1.0.0.dmg"
    container.xlite_reverse_proxy_release_url = "http://test.com/xlite-reverse-proxy.dmg"

    # Current paths
    container.blockdx_curpath = "BLOCK-DX-1.0.0"
    container.xlite_curpath = "XLite-1.0.0"

    # Volume names
    container.blockdx_volume_name = "Block DX 1.0.0"
    container.xlite_volume_name = "XLite 1.0.0"

    # Mock conf_data access
    container.conf_data = MagicMock()

    return container


@pytest.fixture
def base_binutil_with_container(mock_container):
    """Create a BaseBinUtil instance with mocked container."""
    return BaseBinUtil("test_app", mock_container)


@pytest.fixture
def base_binutil_with_darwin_container(mock_container_darwin):
    """Create a BaseBinUtil instance with Darwin mocked container."""
    return BaseBinUtil("test_app", mock_container_darwin)


# =============================================================================
# INITIALIZATION TESTS
# =============================================================================


class TestInitialization(BaseBinUtilTestCase):
    """Test BaseBinUtil initialization."""

    def test_init(self):
        """Test BaseBinUtil initialization with correct defaults."""
        assert self.base_binutil.app_name == "test_app"
        assert self.base_binutil.executable_path is None
        assert self.base_binutil.dmg_mount_path is None
        assert self.base_binutil.binary_percent_download is None
        assert self.base_binutil.downloading_bin is False
        assert self.base_binutil.system == os.name
        assert self.base_binutil.process is None


# =============================================================================
# DOWNLOAD TESTS
# =============================================================================


class TestDownload(BaseBinUtilTestCase):
    """Test download functionality."""

    @patch("zipfile.ZipFile")
    @patch("os.remove")
    @patch("os.path.getsize")
    @patch("requests.get")
    def test_download_file_zip(self, mock_get, mock_getsize, mock_remove, mock_zipfile):
        """Test downloading and extracting ZIP files."""
        mock_get.return_value = self.create_mock_response()
        mock_getsize.return_value = 1000

        mock_zip = MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip

        self.base_binutil.download_file(
            "http://example.com/test.zip",
            os.path.join(self.temp_dir, "test.zip"),
            os.path.join(self.temp_dir, "test.exe"),
            self.temp_dir,
            "nt",
            "progress_attr",
            self.base_binutil,
        )

        mock_zip.extractall.assert_called_once_with(self.temp_dir)
        mock_remove.assert_called_once()

    @patch("tarfile.open")
    @patch("os.remove")
    @patch("os.path.getsize")
    @patch("requests.get")
    def test_download_file_tar_gz(self, mock_get, mock_getsize, mock_remove, mock_tarfile):
        """Test downloading and extracting TAR.GZ files."""
        mock_get.return_value = self.create_mock_response()
        mock_getsize.return_value = 1000

        mock_tar = MagicMock()
        mock_tarfile.return_value.__enter__.return_value = mock_tar

        self.base_binutil.download_file(
            "http://example.com/test.tar.gz",
            os.path.join(self.temp_dir, "test.tar.gz"),
            os.path.join(self.temp_dir, "test.exe"),
            self.temp_dir,
            "posix",
            "progress_attr",
            self.base_binutil,
        )

        mock_tar.extractall.assert_called_once_with(self.temp_dir, filter="data")
        mock_remove.assert_called_once()

    @patch("os.rename")
    @patch("os.path.getsize")
    @patch("requests.get")
    def test_download_file_dmg_darwin(self, mock_get, mock_getsize, mock_rename):
        """Test downloading DMG files on Darwin."""
        # Set up mock container for Darwin
        mock_container = MagicMock()
        mock_container.system = "Darwin"
        mock_container.machine = "arm64"
        mock_container.aio_folder = "/test/aio_folder"
        mock_container.conf_data = MagicMock()

        # Create a base_binutil with Darwin container
        darwin_binutil = BaseBinUtil("test_app", mock_container)

        mock_get.return_value = self.create_mock_response()
        mock_getsize.return_value = 1000

        darwin_binutil.download_file(
            "http://example.com/test.dmg",
            os.path.join(self.temp_dir, "test.dmg"),
            os.path.join(self.temp_dir, "final.dmg"),
            self.temp_dir,
            "posix",
            "progress_attr",
            darwin_binutil,
        )

        mock_rename.assert_called_once()

    @patch("os.remove")
    @patch("os.path.getsize")
    @patch("requests.get")
    def test_download_file_size_mismatch(self, mock_get, mock_getsize, mock_remove):
        """Test handling of download size mismatch."""
        mock_get.return_value = self.create_mock_response()
        mock_getsize.return_value = 500  # Mismatch with Content-Length

        with self.assertRaises(ValueError) as context:
            self.base_binutil.download_file(
                "http://example.com/test.zip",
                os.path.join(self.temp_dir, "test.zip"),
                os.path.join(self.temp_dir, "test.exe"),
                self.temp_dir,
                "nt",
                "progress_attr",
                self.base_binutil,
            )

        assert str(context.exception) == "Download size mismatch"
        mock_remove.assert_called_once()

    @patch("requests.get")
    def test_download_file_network_error(self, mock_get):
        """Test handling of network errors during download."""
        mock_get.side_effect = requests.RequestException("Network error")

        with self.assertRaises(requests.RequestException):
            self.base_binutil.download_file(
                "http://example.com/test.zip",
                os.path.join(self.temp_dir, "test.zip"),
                os.path.join(self.temp_dir, "test.exe"),
                self.temp_dir,
                "nt",
                "progress_attr",
                self.base_binutil,
            )

    @patch("requests.get")
    def test_download_file_timeout(self, mock_get):
        """Test handling of timeout during download."""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        with self.assertRaises(requests.exceptions.Timeout):
            self.base_binutil.download_file(
                "http://example.com/test.zip",
                os.path.join(self.temp_dir, "test.zip"),
                os.path.join(self.temp_dir, "test.exe"),
                self.temp_dir,
                "nt",
                "progress_attr",
                self.base_binutil,
            )

    @patch("requests.get")
    def test_download_file_http_error(self, mock_get):
        """Test handling of HTTP error responses."""
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
                self.base_binutil,
            )

    @patch("utilities.bin_handlers.base_binutil.logger.error")
    @patch("requests.get")
    def test_download_file_permission_error(self, mock_get, mock_log_error):
        """Test handling of permission errors during file write."""
        mock_get.return_value = self.create_mock_response()
        mock = mock_open()
        mock.side_effect = PermissionError("Permission denied")

        with patch("builtins.open", mock), self.assertRaises(PermissionError):
            self.base_binutil.download_file(
                "http://example.com/test.zip",
                os.path.join(self.temp_dir, "test.zip"),
                os.path.join(self.temp_dir, "test.exe"),
                self.temp_dir,
                "nt",
                "progress_attr",
                self.base_binutil,
            )
        mock_log_error.assert_called_once_with("Permission error writing file: Permission denied")

    @patch("zipfile.ZipFile")
    @patch("os.remove")
    @patch("os.path.getsize")
    @patch("requests.get")
    def test_download_file_zip_extract_error(self, mock_get, mock_getsize, mock_remove, mock_zipfile):
        """Test handling of ZIP extraction failures."""
        mock_get.return_value = self.create_mock_response()
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
                self.base_binutil,
            )

    @patch("zipfile.ZipFile")
    @patch("os.remove")
    @patch("os.path.getsize")
    @patch("requests.get")
    def test_download_file_zip_blocknet_handler(self, mock_get, mock_getsize, mock_remove, mock_zipfile):
        """Test ZIP extraction with BlocknetHandler (preserves folder structure)."""
        mock_get.return_value = self.create_mock_response()
        mock_getsize.return_value = 1000

        mock_zip = MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip

        # Create a BlocknetHandler instance
        from utilities.bin_handlers.blocknet_handler import BlocknetHandler

        blocknet_handler = BlocknetHandler()

        try:
            blocknet_handler.download_file(
                "http://example.com/test.zip",
                os.path.join(self.temp_dir, "test.zip"),
                os.path.join(self.temp_dir, "test.exe"),
                self.temp_dir,
                "nt",
                "progress_attr",
                blocknet_handler,
            )

            mock_zip.extractall.assert_called_once_with(self.temp_dir)
            mock_remove.assert_called_once()
        finally:
            # Stop background threads to prevent test hang
            blocknet_handler.running = False

    @patch("zipfile.ZipFile")
    @patch("os.remove")
    @patch("os.path.getsize")
    @patch("requests.get")
    def test_download_file_zip_xlite_handler(self, mock_get, mock_getsize, mock_remove, mock_zipfile):
        """Test ZIP extraction with XliteHandler (creates archive-named subfolder)."""
        mock_get.return_value = self.create_mock_response()
        mock_getsize.return_value = 1000

        mock_zip = MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip

        # Create an XliteHandler instance
        from utilities.bin_handlers.xlite_handler import XliteHandler

        xlite_handler = XliteHandler()

        try:
            xlite_handler.download_file(
                "http://example.com/test.zip",
                os.path.join(self.temp_dir, "test.zip"),
                os.path.join(self.temp_dir, "test.exe"),
                self.temp_dir,
                "posix",
                "progress_attr",
                xlite_handler,
            )

            # Should extract to a subfolder named after the archive
            expected_path = os.path.join(self.temp_dir, "test")
            mock_zip.extractall.assert_called_once_with(expected_path)
            mock_remove.assert_called_once()
        finally:
            # Stop background threads to prevent test hang
            xlite_handler.running = False

    @patch("zipfile.ZipFile")
    @patch("os.remove")
    @patch("os.path.getsize")
    @patch("requests.get")
    def test_download_file_zip_blockdx_handler(self, mock_get, mock_getsize, mock_remove, mock_zipfile):
        """Test ZIP extraction with BlockDXHandler (creates archive-named subfolder)."""
        mock_get.return_value = self.create_mock_response()
        mock_getsize.return_value = 1000

        mock_zip = MagicMock()
        mock_zipfile.return_value.__enter__.return_value = mock_zip

        # Create a BlockDXHandler instance
        from utilities.bin_handlers.blockdx_handler import BlockDXHandler

        blockdx_handler = BlockDXHandler()

        try:
            blockdx_handler.download_file(
                "http://example.com/test.zip",
                os.path.join(self.temp_dir, "test.zip"),
                os.path.join(self.temp_dir, "test.exe"),
                self.temp_dir,
                "posix",
                "progress_attr",
                blockdx_handler,
            )

            # Should extract to a subfolder named after the archive
            expected_path = os.path.join(self.temp_dir, "test")
            mock_zip.extractall.assert_called_once_with(expected_path)
            mock_remove.assert_called_once()
        finally:
            # Stop background threads to prevent test hang
            blockdx_handler.running = False

    def test_download_file_empty_response(self):
        """Test handling of empty response."""
        with (
            patch("requests.get") as mock_get,
            patch("os.path.getsize") as mock_getsize,
            patch("os.remove") as mock_remove,
        ):
            mock_response = MagicMock()
            mock_response.headers = {"Content-Length": "0"}
            mock_response.iter_content.return_value = []
            mock_get.return_value = mock_response
            mock_getsize.return_value = 0

            # Should complete without error for empty file
            self.base_binutil.download_file(
                "http://example.com/test.zip",
                os.path.join(self.temp_dir, "test.zip"),
                os.path.join(self.temp_dir, "test.exe"),
                self.temp_dir,
                "nt",
                "progress_attr",
                self.base_binutil,
            )
            # Empty file should be removed
            mock_remove.assert_called_once()


class TestDownloadBinary(BaseBinUtilTestCase):
    """Test download_binary method."""

    @patch.object(BaseBinUtil, "download_file")
    def test_download_binary_sets_flag(self, mock_download):
        """Test download_binary sets downloading flag correctly."""
        mock_download.return_value = None

        self.base_binutil.download_binary("http://example.com/test.zip", "test.zip", "test.exe", "/test/path")

        assert self.base_binutil.downloading_bin is False
        mock_download.assert_called_once()


class TestDownloadStandaloneBinary(BaseBinUtilTestCase):
    """Test download_standalone_binary method."""

    @patch("os.chmod")
    @patch("os.replace")
    @patch("builtins.open", mock_open())
    @patch("requests.get")
    def test_download_standalone_binary_success(self, mock_get, mock_replace, mock_chmod):
        """Test successful standalone binary download."""
        mock_get.return_value = self.create_mock_response()
        target_path = os.path.join(self.temp_dir, "binary")

        result = self.base_binutil.download_standalone_binary("http://example.com/binary", target_path)

        assert result is True
        mock_replace.assert_called_once()
        mock_chmod.assert_called_once_with(target_path, 0o755)

    @patch("os.path.exists")
    def test_download_standalone_binary_already_exists(self, mock_exists):
        """Test when binary already exists."""
        mock_exists.return_value = True

        result = self.base_binutil.download_standalone_binary(
            "http://example.com/binary", os.path.join(self.temp_dir, "binary")
        )

        assert result is False

    @patch("os.path.exists")
    @patch("os.remove")
    @patch("requests.get")
    def test_download_standalone_binary_failure(self, mock_get, mock_remove, mock_exists):
        """Test download failure cleanup."""
        mock_get.return_value = self.create_mock_response()

        # os.path.exists is called twice: once for target_path, once for temp_path
        # First call (target_path) should return False to trigger download
        # Second call (temp_path) should return True to trigger cleanup
        def exists_side_effect(path):
            return bool(path.endswith(".tmp"))

        mock_exists.side_effect = exists_side_effect

        mock = mock_open()
        mock.side_effect = Exception("Download failed")

        with patch("builtins.open", mock):
            result = self.base_binutil.download_standalone_binary(
                "http://example.com/binary", os.path.join(self.temp_dir, "binary")
            )

        assert result is False
        mock_remove.assert_called_once()


# =============================================================================
# PROCESS MANAGEMENT TESTS
# =============================================================================


class TestProcessManagement(BaseBinUtilTestCase):
    """Test process management functionality."""

    @patch("subprocess.Popen")
    def test_start_process(self, mock_popen):
        """Test starting a process."""
        mock_process = self.create_mock_process()
        mock_popen.return_value = mock_process

        result = self.base_binutil.start_process(["test", "command"], cwd="/test")

        mock_popen.assert_called_once()
        assert result == mock_process
        assert self.base_binutil.process == mock_process

    @patch("subprocess.Popen")
    @patch("os.environ.copy")
    def test_start_process_with_env_vars(self, mock_env_copy, mock_popen):
        """Test starting a process with environment variables."""
        mock_process = self.create_mock_process()
        mock_popen.return_value = mock_process
        mock_env_copy.return_value = {"EXISTING": "value"}

        env_vars = {"NEW": "value"}
        self.base_binutil.start_process(["test"], env_vars=env_vars)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        assert "env" in call_args.kwargs
        assert call_args.kwargs["env"] == {"EXISTING": "value", "NEW": "value"}

    def test_start_process_empty_command(self):
        """Test starting a process with empty command list."""
        with self.assertRaises(ValueError) as context:
            self.base_binutil.start_process([])
        assert str(context.exception) == "Command list cannot be empty"

    @patch("subprocess.Popen")
    def test_graceful_terminate_success(self, mock_popen):
        """Test successful graceful termination."""
        mock_process = self.create_mock_process()
        self.base_binutil.process = mock_process

        self.base_binutil.graceful_terminate()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=10)
        assert self.base_binutil.process is None

    @patch("subprocess.Popen")
    def test_graceful_terminate_timeout(self, mock_popen):
        """Test graceful termination with timeout fallback to force kill."""
        mock_process = MagicMock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=10)
        self.base_binutil.process = mock_process

        with patch.object(self.base_binutil, "force_kill") as mock_force_kill:
            self.base_binutil.graceful_terminate()

            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once_with(timeout=10)
            mock_force_kill.assert_called_once()

    @patch("subprocess.Popen")
    def test_graceful_terminate_no_process(self, mock_popen):
        """Test graceful_terminate when no process exists."""
        with patch("utilities.bin_handlers.base_binutil.logger.info") as mock_log_info:
            self.base_binutil.process = None
            self.base_binutil.graceful_terminate()
            mock_log_info.assert_called_once_with("No running process to terminate")

    @patch("subprocess.Popen")
    def test_force_kill(self, mock_popen):
        """Test force killing a process."""
        mock_process = MagicMock()
        self.base_binutil.process = mock_process

        self.base_binutil.force_kill()

        mock_process.kill.assert_called_once()
        assert self.base_binutil.process is None

    @patch("subprocess.Popen")
    @patch("utilities.bin_handlers.base_binutil.logger.error")
    def test_force_kill_error_handling(self, mock_log_error, mock_popen):
        """Test error handling in force kill."""
        mock_process = MagicMock()
        mock_process.kill.side_effect = Exception("Kill error")
        self.base_binutil.process = mock_process

        self.base_binutil.force_kill()

        mock_process.kill.assert_called_once()
        mock_log_error.assert_called_once()

    @patch("utilities.bin_handlers.base_binutil.logger.warning")
    def test_terminate_processes_empty_pids(self, mock_log_warning):
        """Test terminate_processes with empty PID list."""
        self.base_binutil.terminate_processes([], "test_app")
        mock_log_warning.assert_called_once_with("No PIDs to terminate for test_app")

    @patch("psutil.Process")
    @patch("utilities.bin_handlers.base_binutil.logger.info")
    def test_terminate_processes_success(self, mock_log_info, mock_process_class):
        """Test successful process termination."""
        mock_process = self.create_mock_psutil_process()
        mock_process_class.return_value = mock_process

        self.base_binutil.terminate_processes([1234], "test_app")

        mock_process_class.assert_called_once_with(1234)
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=10)
        mock_log_info.assert_called_once()

    @patch("psutil.Process")
    @patch("utilities.bin_handlers.base_binutil.logger.warning")
    def test_terminate_processes_no_such_process(self, mock_log_warning, mock_process_class):
        """Test handling of non-existent processes."""
        mock_process_class.side_effect = psutil.NoSuchProcess(pid=1234)

        self.base_binutil.terminate_processes([1234], "test_app")

        mock_log_warning.assert_called_once()

    @patch("psutil.Process")
    @patch("utilities.bin_handlers.base_binutil.logger.warning")
    def test_terminate_processes_timeout_kill(self, mock_log_warning, mock_process_class):
        """Test process termination with timeout fallback to kill."""
        mock_process = MagicMock()
        mock_process_class.return_value = mock_process
        mock_process.wait.side_effect = psutil.TimeoutExpired(10)

        self.base_binutil.terminate_processes([1234], "test_app")

        mock_process.kill.assert_called_once()
        mock_log_warning.assert_called_once_with("Process test_app PID 1234: Timeout expired, killed process")

    @patch("psutil.Process")
    @patch("utilities.bin_handlers.base_binutil.logger.info")
    def test_terminate_processes_multiple_pids(self, mock_log_info, mock_process_class):
        """Test terminating multiple PIDs."""
        mock_process1 = self.create_mock_psutil_process()
        mock_process2 = self.create_mock_psutil_process()
        mock_process_class.side_effect = [mock_process1, mock_process2]

        self.base_binutil.terminate_processes([1234, 5678], "test_app")

        assert mock_process_class.call_count == 2
        mock_log_info.assert_any_call("Process test_app PID 1234 terminated successfully")
        mock_log_info.assert_any_call("Process test_app PID 5678 terminated successfully")


# =============================================================================
# DMG HANDLING TESTS
# =============================================================================


class TestDmgHandling(BaseBinUtilTestCase):
    """Test DMG handling functionality."""

    def test_handle_dmg_wrong_os(self):
        """Test handle_dmg with wrong OS."""
        # base_binutil already has Linux container
        with patch("utilities.bin_handlers.base_binutil.logger.warning") as mock_log_warning:
            self.base_binutil.handle_dmg("mount")
            mock_log_warning.assert_called_once_with("Call handle_dmg with wrong OS, Linux ?")

    @patch("os.path.ismount")
    @patch("utilities.bin_handlers.base_binutil.logger.warning")
    def test_handle_dmg_already_mounted(self, mock_log_warning, mock_ismount):
        """Test handle_dmg when already mounted."""
        # Set up mock container for Darwin
        mock_container = MagicMock()
        mock_container.system = "Darwin"
        darwin_binutil = BaseBinUtil("test_app", mock_container)

        mock_ismount.return_value = True
        darwin_binutil.dmg_mount_path = "/Volumes/test"
        darwin_binutil.handle_dmg("mount")
        mock_log_warning.assert_called_once_with("/Volumes/test is already mounted")

    @patch("os.path.ismount")
    @patch("subprocess.run")
    @patch("utilities.bin_handlers.base_binutil.logger.info")
    def test_handle_dmg_mount_success(self, mock_log_info, mock_run, mock_ismount):
        """Test successful DMG mount on Darwin."""
        # Set up mock container for Darwin
        mock_container = MagicMock()
        mock_container.system = "Darwin"
        darwin_binutil = BaseBinUtil("test_app", mock_container)

        mock_ismount.return_value = False
        darwin_binutil.dmg_mount_path = "/Volumes/test"
        darwin_binutil.executable_path = "/path/to/app.dmg"

        darwin_binutil.handle_dmg("mount")

        mock_run.assert_called_once_with(["hdiutil", "attach", darwin_binutil.executable_path], check=True)
        mock_log_info.assert_called_once_with(
            f"Mounted DMG {darwin_binutil.executable_path} to {darwin_binutil.dmg_mount_path}"
        )

    @patch("os.path.ismount")
    @patch("subprocess.run")
    @patch("utilities.bin_handlers.base_binutil.logger.info")
    def test_handle_dmg_unmount_success(self, mock_log_info, mock_run, mock_ismount):
        """Test successful DMG unmount on Darwin."""
        # Set up mock container for Darwin
        mock_container = MagicMock()
        mock_container.system = "Darwin"
        darwin_binutil = BaseBinUtil("test_app", mock_container)

        mock_ismount.return_value = True
        darwin_binutil.dmg_mount_path = "/Volumes/test"

        darwin_binutil.handle_dmg("unmount")

        mock_run.assert_called_once_with(["hdiutil", "detach", darwin_binutil.dmg_mount_path], check=True)
        mock_log_info.assert_called_once_with(f"Unmounted DMG from {darwin_binutil.dmg_mount_path}")

    @patch("os.path.ismount")
    @patch("subprocess.run")
    @patch("utilities.bin_handlers.base_binutil.logger.warning")
    def test_handle_dmg_unmount_not_mounted(self, mock_log_warning, mock_run, mock_ismount):
        """Test unmount when DMG is not mounted."""
        # Set up mock container for Darwin
        mock_container = MagicMock()
        mock_container.system = "Darwin"
        darwin_binutil = BaseBinUtil("test_app", mock_container)

        mock_ismount.return_value = False
        darwin_binutil.dmg_mount_path = "/Volumes/test"

        darwin_binutil.handle_dmg("unmount")

        mock_run.assert_not_called()
        mock_log_warning.assert_called_once_with("/Volumes/test is not mounted")


# =============================================================================
# POTENTIAL BUGS DOCUMENTATION
# =============================================================================


class TestPotentialBugs(BaseBinUtilTestCase):
    """Document potential bugs found in core code during analysis."""

    def test_potential_bug_subprocess_timeout_mismatch(self):
        """
        POTENTIAL BUG: Core code catches subprocess.TimeoutExpired (line 130)
        but test uses psutil.TimeoutExpired (line 218).

        This suggests the core code might not handle psutil.TimeoutExpired
        correctly in graceful_terminate method.
        """
        # This test documents the potential bug
        # The core code should catch both exception types or the test should be fixed
        pass

    def test_potential_bug_handler_class_name_check(self):
        """
        POTENTIAL BUG: Core code uses instance.__class__.__name__ (line 70)
        which is fragile and depends on class hierarchy.

        This could break if class names change or if inheritance is used.
        """
        # This test documents the potential bug
        # The core code should use a more robust method to determine extraction behavior
        pass


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    unittest.main()
