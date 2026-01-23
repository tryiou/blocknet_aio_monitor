"""Tests for utilities/miniforge_portable.py"""
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, call
import pytest
import requests
from utilities.miniforge_portable import PortablePythonInstaller


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def target_dir():
    """Fixture providing a test target directory"""
    return Path("/test/target")


@pytest.fixture
def mock_download_response():
    """Fixture providing a mocked download response"""
    mock_response = Mock()
    mock_response.iter_content.return_value = [b"chunk1", b"chunk2"]
    return mock_response


@pytest.fixture
def mock_stat_result():
    """Fixture providing a mocked stat result"""
    mock_stat_result = Mock()
    mock_stat_result.st_mode = 0o644
    return mock_stat_result


# ============================================================================
# TESTS
# ============================================================================


class TestPortablePythonInstaller:
    """Test PortablePythonInstaller class"""

    # -------------------------------------------------------------------------
    # INITIALIZATION TESTS
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("system,arch,expected_system,expected_arch", [
        ("Linux", "x86_64", "Linux", "x86_64"),
        ("Windows", "x86_64", "Windows", "x86_64"),
        ("Darwin", "arm64", "Darwin", "arm64"),
    ])
    def test_init(self, target_dir, system, arch, expected_system, expected_arch):
        """Test initialization of PortablePythonInstaller"""
        with patch('utilities.miniforge_portable.platform.system', return_value=system):
            with patch('utilities.miniforge_portable.platform.machine', return_value=arch):
                installer = PortablePythonInstaller(target_dir)

                assert installer.target_dir == target_dir.resolve()
                assert installer.system == expected_system
                assert installer.arch == expected_arch

    # -------------------------------------------------------------------------
    # INSTALLER FILENAME TESTS
    # -------------------------------------------------------------------------

    @pytest.mark.parametrize("system,arch,expected_filename", [
        ("Windows", "x86_64", "Miniforge3-25.3.0-3-Windows-x86_64.exe"),
        ("Linux", "x86_64", "Miniforge3-25.3.0-3-Linux-x86_64.sh"),
        ("Linux", "aarch64", "Miniforge3-25.3.0-3-Linux-aarch64.sh"),
        ("Darwin", "arm64", "Miniforge3-25.3.0-3-MacOSX-arm64.sh"),
        ("Darwin", "x86_64", "Miniforge3-25.3.0-3-MacOSX-x86_64.sh"),
    ])
    def test_get_installer_filename(self, target_dir, system, arch, expected_filename):
        """Test installer filename generation for various platforms"""
        with patch('utilities.miniforge_portable.platform.system', return_value=system):
            with patch('utilities.miniforge_portable.platform.machine', return_value=arch):
                installer = PortablePythonInstaller(target_dir)
                filename = installer.get_installer_filename()

                assert filename == expected_filename

    def test_get_installer_filename_unsupported_os(self, target_dir):
        """Test installer filename for unsupported OS"""
        with patch('utilities.miniforge_portable.platform.system', return_value='FreeBSD'):
            with patch('utilities.miniforge_portable.platform.machine', return_value='x86_64'):
                installer = PortablePythonInstaller(target_dir)

                with pytest.raises(RuntimeError, match="Unsupported OS: FreeBSD"):
                    installer.get_installer_filename()

    # -------------------------------------------------------------------------
    # DOWNLOAD TESTS
    # -------------------------------------------------------------------------

    @patch('utilities.miniforge_portable.requests.get')
    def test_download_success(self, mock_get, target_dir, mock_download_response):
        """Test successful download"""
        with patch('utilities.miniforge_portable.platform.system', return_value='Linux'):
            with patch('utilities.miniforge_portable.platform.machine', return_value='x86_64'):
                installer = PortablePythonInstaller(target_dir)
                mock_get.return_value = mock_download_response

                dest = Path("/test/download/installer.sh")

                with patch('builtins.open', create=True):
                    installer.download("http://example.com/installer.sh", dest)

                mock_get.assert_called_once_with("http://example.com/installer.sh", stream=True)
                mock_download_response.raise_for_status.assert_called_once()

    @patch('utilities.miniforge_portable.requests.get')
    def test_download_with_error(self, mock_get, target_dir):
        """Test download with HTTP error"""
        with patch('utilities.miniforge_portable.platform.system', return_value='Linux'):
            with patch('utilities.miniforge_portable.platform.machine', return_value='x86_64'):
                installer = PortablePythonInstaller(target_dir)

                mock_response = Mock()
                error_msg = "404 Not Found"
                mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(error_msg)
                mock_get.return_value = mock_response

                dest = Path("/test/download/installer.sh")

                with pytest.raises(requests.exceptions.HTTPError, match=error_msg):
                    installer.download("http://example.com/installer.sh", dest)

    # -------------------------------------------------------------------------
    # INSTALL TESTS - WINDOWS
    # -------------------------------------------------------------------------

    @patch('utilities.miniforge_portable.subprocess.run')
    @patch('utilities.miniforge_portable.requests.get')
    @patch('utilities.miniforge_portable.shutil.rmtree')
    @patch('utilities.miniforge_portable.Path.mkdir')
    def test_install_windows(self, mock_mkdir, mock_rmtree, mock_get, mock_subprocess, target_dir,
                             mock_download_response):
        """Test install on Windows"""
        with patch('utilities.miniforge_portable.platform.system', return_value='Windows'):
            with patch('utilities.miniforge_portable.platform.machine', return_value='x86_64'):
                installer = PortablePythonInstaller(target_dir)
                mock_get.return_value = mock_download_response
                mock_subprocess.return_value = None

                with patch('builtins.open', create=True):
                    result = installer.install()

                # Verify mkdir was called
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

                # Verify subprocess was called with Windows-specific args
                mock_subprocess.assert_called_once()
                call_args = mock_subprocess.call_args[0][0]
                assert call_args[0].endswith(".exe")
                assert "/InstallationType=JustMe" in call_args
                assert "/AddToPath=0" in call_args
                assert "/S" in call_args
                assert "/D=" in call_args[-1]

                # Verify result
                assert result == target_dir / "miniforge" / "Scripts" / "python.exe"

    # -------------------------------------------------------------------------
    # INSTALL TESTS - LINUX
    # -------------------------------------------------------------------------

    @patch('utilities.miniforge_portable.subprocess.run')
    @patch('utilities.miniforge_portable.requests.get')
    @patch('utilities.miniforge_portable.shutil.rmtree')
    @patch('utilities.miniforge_portable.Path.mkdir')
    @patch('utilities.miniforge_portable.Path.chmod')
    @patch('utilities.miniforge_portable.Path.stat')
    def test_install_linux(self, mock_stat, mock_chmod, mock_mkdir, mock_rmtree, mock_get, mock_subprocess,
                           target_dir, mock_download_response, mock_stat_result):
        """Test install on Linux"""
        with patch('utilities.miniforge_portable.platform.system', return_value='Linux'):
            with patch('utilities.miniforge_portable.platform.machine', return_value='x86_64'):
                installer = PortablePythonInstaller(target_dir)
                mock_get.return_value = mock_download_response
                mock_subprocess.side_effect = [None, None]
                mock_stat.return_value = mock_stat_result

                with patch('builtins.open', create=True):
                    result = installer.install()

                # Verify mkdir was called
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

                # Verify chmod was called
                mock_chmod.assert_called_once()

                # Verify subprocess was called twice (installer + conda)
                assert mock_subprocess.call_count == 2

                # Verify first call (installer) has Linux-specific args
                first_call_args = mock_subprocess.call_args_list[0][0][0]
                assert first_call_args[0].endswith(".sh")
                assert "-b" in first_call_args
                assert "-p" in first_call_args

                # Verify conda install command
                conda_call = mock_subprocess.call_args_list[1]
                conda_args = conda_call[0][0]
                assert "conda" in conda_args[0]
                assert "install" in conda_args
                assert "tk=*=xft_*" in conda_args

                # Verify result
                assert result == target_dir / "miniforge" / "bin" / "python"

    # -------------------------------------------------------------------------
    # INSTALL TESTS - EDGE CASES
    # -------------------------------------------------------------------------

    @patch('utilities.miniforge_portable.subprocess.run')
    @patch('utilities.miniforge_portable.requests.get')
    @patch('utilities.miniforge_portable.shutil.rmtree')
    @patch('utilities.miniforge_portable.Path.mkdir')
    @patch('utilities.miniforge_portable.Path.chmod')
    @patch('utilities.miniforge_portable.Path.stat')
    def test_install_existing_install_dir(self, mock_stat, mock_chmod, mock_mkdir, mock_rmtree, mock_get,
                                          mock_subprocess,
                                          target_dir, mock_download_response, mock_stat_result):
        """Test install when install directory already exists"""
        with patch('utilities.miniforge_portable.platform.system', return_value='Linux'):
            with patch('utilities.miniforge_portable.platform.machine', return_value='x86_64'):
                installer = PortablePythonInstaller(target_dir)
                install_path = target_dir / "miniforge"

                with patch.object(Path, 'exists', return_value=True):
                    mock_get.return_value = mock_download_response
                    mock_subprocess.side_effect = [None, None]
                    mock_stat.return_value = mock_stat_result

                    with patch('builtins.open', create=True):
                        installer.install()

                    # Verify rmtree was called to remove existing install
                    mock_rmtree.assert_called_once_with(install_path)

    @patch('utilities.miniforge_portable.subprocess.run')
    @patch('utilities.miniforge_portable.requests.get')
    @patch('utilities.miniforge_portable.shutil.rmtree')
    @patch('utilities.miniforge_portable.Path.mkdir')
    @patch('utilities.miniforge_portable.Path.chmod')
    @patch('utilities.miniforge_portable.Path.stat')
    def test_install_subprocess_error(self, mock_stat, mock_chmod, mock_mkdir, mock_rmtree, mock_get, mock_subprocess,
                                      target_dir, mock_download_response, mock_stat_result):
        """Test install when subprocess fails"""
        with patch('utilities.miniforge_portable.platform.system', return_value='Linux'):
            with patch('utilities.miniforge_portable.platform.machine', return_value='x86_64'):
                installer = PortablePythonInstaller(target_dir)
                mock_get.return_value = mock_download_response
                mock_subprocess.side_effect = subprocess.CalledProcessError(1, "installer")
                mock_stat.return_value = mock_stat_result

                with patch('builtins.open', create=True):
                    with pytest.raises(RuntimeError, match="Installer failed"):
                        installer.install()

    @patch('utilities.miniforge_portable.subprocess.run')
    @patch('utilities.miniforge_portable.requests.get')
    @patch('utilities.miniforge_portable.shutil.rmtree')
    @patch('utilities.miniforge_portable.Path.mkdir')
    @patch('utilities.miniforge_portable.Path.chmod')
    @patch('utilities.miniforge_portable.Path.stat')
    def test_install_linux_conda_install_fails(self, mock_stat, mock_chmod, mock_mkdir, mock_rmtree, mock_get,
                                               mock_subprocess,
                                               target_dir, mock_download_response, mock_stat_result):
        """Test install on Linux when conda install fails"""
        with patch('utilities.miniforge_portable.platform.system', return_value='Linux'):
            with patch('utilities.miniforge_portable.platform.machine', return_value='x86_64'):
                installer = PortablePythonInstaller(target_dir)
                mock_get.return_value = mock_download_response
                mock_subprocess.side_effect = [None, Exception("Conda install failed")]
                mock_stat.return_value = mock_stat_result

                with patch('builtins.open', create=True):
                    with pytest.raises(Exception, match="Conda install failed"):
                        installer.install()
