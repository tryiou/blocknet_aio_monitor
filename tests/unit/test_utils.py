"""Tests for utilities/utils.py"""
import json
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
import pytest
import customtkinter as ctk
from utilities import utils, global_variables


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_button():
    """Create a mock button for button-related tests"""
    button = Mock()
    return button


@pytest.fixture
def mock_tooltip():
    """Create a mock tooltip for tooltip-related tests"""
    tooltip = Mock()
    return tooltip


@pytest.fixture
def mock_global_variables():
    """Mock global_variables with common config setup"""
    with patch('utilities.utils.global_variables') as mock_global:
        mock_global.conf_data.aio_blocknet_data_path = {"Linux": "/test/data"}
        mock_global.system = "Linux"
        yield mock_global


@pytest.fixture
def mock_file_operations():
    """Common file operation mocks for config tests"""
    with patch('os.path.expanduser') as mock_expanduser, \
            patch('os.path.expandvars') as mock_expandvars, \
            patch('os.path.exists') as mock_exists:
        mock_expanduser.return_value = "/test/data"
        mock_expandvars.return_value = "/test/data"
        yield mock_expanduser, mock_expandvars, mock_exists


@pytest.fixture
def mock_json_file():
    """Create a mock JSON file context"""

    def _mock_json_file(content='{}'):
        mock_file = Mock()
        mock_file.read.return_value = content
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        return mock_file

    return _mock_json_file


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_mock_file(read_data=""):
    """Helper to create a mock open function"""
    mock_file = Mock()
    mock_file.read.return_value = read_data
    mock_file.__enter__ = Mock(return_value=mock_file)
    mock_file.__exit__ = Mock(return_value=False)
    return Mock(return_value=mock_file)


def create_real_file_mock(file_path):
    """Helper to create a mock open that reads from a real file"""

    def mock_open_impl(*args, **kwargs):
        if 'r' in str(args) or 'r' in str(kwargs):
            return open(file_path, 'r')
        else:
            return open(file_path, 'w')

    return mock_open_impl


# ============================================================================
# TESTS
# ============================================================================

class TestConfigureTooltipText:
    """Test configure_tooltip_text function"""

    def test_configure_tooltip_text_updates_when_different(self, mock_tooltip):
        """Test tooltip update when message is different"""
        mock_tooltip.get.return_value = "old message"

        utils.configure_tooltip_text(mock_tooltip, "new message")

        mock_tooltip.get.assert_called_once()
        mock_tooltip.configure.assert_called_once_with(message="new message")

    def test_configure_tooltip_text_no_update_when_same(self, mock_tooltip):
        """Test tooltip no update when message is same"""
        mock_tooltip.get.return_value = "same message"

        utils.configure_tooltip_text(mock_tooltip, "same message")

        mock_tooltip.get.assert_called_once()
        mock_tooltip.configure.assert_not_called()


class TestTerminateAllThreads:
    """Test terminate_all_threads function"""

    @patch('utilities.utils.enumerate')
    @patch('utilities.utils.current_thread')
    def test_terminate_all_threads(self, mock_current_thread, mock_enumerate):
        """Test terminating all threads except current"""
        # Mock threads
        mock_thread1 = Mock()
        mock_thread1.name = "Thread-1"
        mock_thread2 = Mock()
        mock_thread2.name = "Thread-2"
        mock_current_thread.return_value = mock_thread1

        # Mock enumerate to return current thread and other threads
        mock_enumerate.return_value = [mock_thread1, mock_thread2]

        utils.terminate_all_threads()

        # Verify only non-current threads were terminated
        mock_thread2.join.assert_called_once_with(timeout=0.25)
        mock_thread1.join.assert_not_called()


class TestLoadCfgJson:
    """Test load_cfg_json function"""

    @patch('utilities.utils.global_variables')
    @patch('os.path.exists')
    @patch('os.path.expandvars')
    @patch('os.path.expanduser')
    def test_load_cfg_json_new_file_exists(self, mock_expanduser, mock_expandvars, mock_exists, mock_global):
        """Test loading new config file when it exists"""
        mock_global.aio_folder = "/test/aio"
        mock_expanduser.return_value = "/test/aio"
        mock_expandvars.return_value = "/test/aio"
        mock_exists.side_effect = [False, True]  # old doesn't exist, new exists

        mock_file_content = '{"test_key": "test_value"}'

        with patch('builtins.open') as mock_open:
            mock_file = Mock()
            mock_file.read.return_value = mock_file_content
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_open.return_value = mock_file

            result = utils.load_cfg_json()

            assert result == {"test_key": "test_value"}

    @patch('utilities.utils.global_variables')
    @patch('os.path.exists')
    @patch('os.path.expandvars')
    @patch('os.path.expanduser')
    def test_load_cfg_json_old_file_migration(self, mock_expanduser, mock_expandvars, mock_exists, mock_global):
        """Test migration from old config file to new"""
        mock_global.aio_folder = "/test/aio"
        mock_expanduser.return_value = "/test/aio"
        mock_expandvars.return_value = "/test/aio"
        mock_exists.side_effect = [True, True]

        mock_file_content = '{"old_key": "old_value"}'

        with patch('builtins.open') as mock_open:
            mock_file = Mock()
            mock_file.read.return_value = mock_file_content
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_open.return_value = mock_file

            with patch('os.rename') as mock_rename:
                result = utils.load_cfg_json()

            assert result == {"old_key": "old_value"}
            mock_rename.assert_called_once()

    @patch('utilities.utils.global_variables')
    @patch('os.path.exists')
    @patch('os.path.expandvars')
    @patch('os.path.expanduser')
    def test_load_cfg_json_file_not_found(self, mock_expanduser, mock_expandvars, mock_exists, mock_global):
        """Test when config file doesn't exist"""
        mock_global.aio_folder = "/test/aio"
        mock_expanduser.return_value = "/test/aio"
        mock_expandvars.return_value = "/test/aio"
        mock_exists.side_effect = [False, False]

        result = utils.load_cfg_json()

        assert result is None


class TestRemoveCfgJsonKey:
    """Test remove_cfg_json_key function"""

    @patch('utilities.utils.global_variables')
    @patch('os.path.exists')
    @patch('os.path.expandvars')
    @patch('os.path.expanduser')
    def test_remove_cfg_json_key_success(self, mock_expanduser, mock_expandvars, mock_exists, mock_global):
        """Test successful key removal"""
        mock_global.conf_data.aio_blocknet_data_path = {"Linux": "/test/data"}
        mock_global.system = "Linux"
        mock_expanduser.return_value = "/test/data"
        mock_expandvars.return_value = "/test/data"

        config_data = {"key1": "value1", "key2": "value2"}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            temp_file = f.name

        try:
            with patch('builtins.open', mock_open=create_real_file_mock(temp_file)):
                with patch('json.load', return_value=config_data):
                    with patch('json.dump') as mock_dump:
                        utils.remove_cfg_json_key("key1")

            assert mock_dump.call_count == 1
            saved_data = mock_dump.call_args[0][0]
            assert "key1" not in saved_data
            assert "key2" in saved_data
        finally:
            os.unlink(temp_file)

    @patch('utilities.utils.global_variables')
    @patch('os.path.expandvars')
    @patch('os.path.expanduser')
    def test_remove_cfg_json_key_file_not_found(self, mock_expanduser, mock_expandvars, mock_global):
        """Test when config file doesn't exist"""
        mock_global.conf_data.aio_blocknet_data_path = {"Linux": "/test/data"}
        mock_global.system = "Linux"
        mock_expanduser.return_value = "/test/data"
        mock_expandvars.return_value = "/test/data"

        with patch('builtins.open', side_effect=FileNotFoundError):
            utils.remove_cfg_json_key("key1")

    @patch('utilities.utils.global_variables')
    @patch('os.path.expandvars')
    @patch('os.path.expanduser')
    def test_remove_cfg_json_key_key_not_found(self, mock_expanduser, mock_expandvars, mock_global):
        """Test when key doesn't exist in config"""
        mock_global.conf_data.aio_blocknet_data_path = {"Linux": "/test/data"}
        mock_global.system = "Linux"
        mock_expanduser.return_value = "/test/data"
        mock_expandvars.return_value = "/test/data"

        config_data = {"key1": "value1"}

        with patch('builtins.open', mock_open=create_real_file_mock("/test/data/aio_settings.json")):
            with patch('json.load', return_value=config_data):
                with patch('json.dump') as mock_dump:
                    utils.remove_cfg_json_key("nonexistent_key")

            mock_dump.assert_not_called()

    @patch('utilities.utils.global_variables')
    @patch('os.path.expandvars')
    @patch('os.path.expanduser')
    def test_remove_cfg_json_key_invalid_json(self, mock_expanduser, mock_expandvars, mock_global):
        """Test removing key from file with invalid JSON"""
        mock_global.conf_data.aio_blocknet_data_path = {"Linux": "/test/data"}
        mock_global.system = "Linux"
        mock_expanduser.return_value = "/test/data"
        mock_expandvars.return_value = "/test/data"

        with patch('builtins.open') as mock_open:
            mock_file = Mock()
            mock_file.read.return_value = 'invalid json'
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_open.return_value = mock_file

            with patch('json.load', side_effect=json.JSONDecodeError("Invalid", "", 0)):
                utils.remove_cfg_json_key("key1")

            mock_file.write.assert_not_called()


class TestSaveCfgJson:
    """Test save_cfg_json function"""

    @patch('utilities.utils.global_variables')
    @patch('os.path.expandvars')
    @patch('os.path.expanduser')
    def test_save_cfg_json_new_file(self, mock_expanduser, mock_expandvars, mock_global):
        """Test saving to new config file"""
        mock_global.conf_data.aio_blocknet_data_path = {"Linux": "/test/data"}
        mock_global.system = "Linux"
        mock_expanduser.return_value = "/test/data"
        mock_expandvars.return_value = "/test/data"

        with patch('builtins.open') as mock_open:
            mock_file = Mock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_open.return_value = mock_file

            with patch('json.load', side_effect=FileNotFoundError):
                with patch('json.dump') as mock_dump:
                    utils.save_cfg_json("test_key", "test_value")

            assert mock_dump.call_count == 1
            saved_data = mock_dump.call_args[0][0]
            assert saved_data == {"test_key": "test_value"}

    @patch('utilities.utils.global_variables')
    @patch('os.path.expandvars')
    @patch('os.path.expanduser')
    def test_save_cfg_json_existing_file(self, mock_expanduser, mock_expandvars, mock_global):
        """Test saving to existing config file"""
        mock_global.conf_data.aio_blocknet_data_path = {"Linux": "/test/data"}
        mock_global.system = "Linux"
        mock_expanduser.return_value = "/test/data"
        mock_expandvars.return_value = "/test/data"

        existing_data = {"old_key": "old_value"}

        with patch('builtins.open', mock_open=create_real_file_mock("/test/data/aio_settings.json")):
            with patch('json.load', return_value=existing_data):
                with patch('json.dump') as mock_dump:
                    utils.save_cfg_json("new_key", "new_value")

            assert mock_dump.call_count == 1
            saved_data = mock_dump.call_args[0][0]
            assert saved_data == {"old_key": "old_value", "new_key": "new_value"}

    @patch('utilities.utils.global_variables')
    @patch('os.path.expandvars')
    @patch('os.path.expanduser')
    def test_save_cfg_json_invalid_json(self, mock_expanduser, mock_expandvars, mock_global):
        """Test saving when existing file has invalid JSON"""
        mock_global.conf_data.aio_blocknet_data_path = {"Linux": "/test/data"}
        mock_global.system = "Linux"
        mock_expanduser.return_value = "/test/data"
        mock_expandvars.return_value = "/test/data"

        with patch('builtins.open') as mock_open:
            mock_file = Mock()
            mock_file.read.return_value = 'invalid json'
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_open.return_value = mock_file

            with patch('json.load', side_effect=json.JSONDecodeError("Invalid", "", 0)):
                with patch('json.dump') as mock_dump:
                    utils.save_cfg_json("test_key", "test_value")

            assert mock_dump.call_count == 1
            saved_data = mock_dump.call_args[0][0]
            assert saved_data == {"test_key": "test_value"}


class TestEncryptDecryptPassword:
    """Test encrypt_password and decrypt_password functions"""

    def test_generate_key(self):
        """Test that generate_key returns a valid key"""
        key = utils.generate_key()
        assert key is not None
        assert isinstance(key, bytes)
        assert len(key) > 0

    def test_encrypt_password(self):
        """Test encrypt_password function"""
        password = "test_password"
        key = utils.generate_key()

        encrypted = utils.encrypt_password(password, key)

        assert encrypted != password
        assert isinstance(encrypted, str)
        assert len(encrypted) > 0

    def test_decrypt_password(self):
        """Test decrypt_password function"""
        password = "test_password"
        key = utils.generate_key()
        encrypted = utils.encrypt_password(password, key)

        decrypted = utils.decrypt_password(encrypted, key)

        assert decrypted == password

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption work correctly"""
        password = "test_password_123"

        key = utils.generate_key()
        assert key is not None

        encrypted = utils.encrypt_password(password, key)
        assert encrypted != password
        assert isinstance(encrypted, str)

        decrypted = utils.decrypt_password(encrypted, key)
        assert decrypted == password

    def test_encrypt_password_different_each_time(self):
        """Test that same password encrypts differently each time"""
        password = "test_password"

        key1 = utils.generate_key()
        encrypted1 = utils.encrypt_password(password, key1)

        key2 = utils.generate_key()
        encrypted2 = utils.encrypt_password(password, key2)

        assert encrypted1 != encrypted2


class TestEnableDisableButton:
    """Test enable_button and disable_button functions"""

    def test_enable_button_when_disabled(self, mock_button):
        """Test enabling a disabled button"""
        mock_button.cget.return_value = ctk.DISABLED

        utils.enable_button(mock_button)

        mock_button.configure.assert_called_once_with(state=ctk.NORMAL)

    def test_enable_button_when_already_enabled(self, mock_button):
        """Test enabling an already enabled button"""
        mock_button.cget.return_value = ctk.NORMAL

        utils.enable_button(mock_button)

        mock_button.configure.assert_not_called()

    def test_enable_button_with_image(self, mock_button):
        """Test enabling button with image"""
        mock_button.cget.return_value = ctk.DISABLED
        img = Mock()

        utils.enable_button(mock_button, img=img)

        assert mock_button.configure.call_count == 2
        mock_button.configure.assert_any_call(state=ctk.NORMAL)
        mock_button.configure.assert_any_call(image=img)

    def test_disable_button_when_enabled(self, mock_button):
        """Test disabling an enabled button"""
        mock_button.cget.return_value = ctk.NORMAL

        utils.disable_button(mock_button)

        mock_button.configure.assert_called_once_with(state=ctk.DISABLED)

    def test_disable_button_when_already_disabled(self, mock_button):
        """Test disabling an already disabled button"""
        mock_button.cget.return_value = ctk.DISABLED

        utils.disable_button(mock_button)

        mock_button.configure.assert_not_called()

    def test_disable_button_with_image(self, mock_button):
        """Test disabling button with image"""
        mock_button.cget.return_value = ctk.NORMAL
        img = Mock()

        utils.disable_button(mock_button, img=img)

        assert mock_button.configure.call_count == 2
        mock_button.configure.assert_any_call(state=ctk.DISABLED)
        mock_button.configure.assert_any_call(image=img)


class TestProcessesCheck:
    """Test processes_check and handle_process functions"""

    @patch('utilities.utils.psutil')
    @patch('utilities.utils.global_variables')
    def test_processes_check_all_processes_found(self, mock_global, mock_psutil):
        """Test when all target processes are found"""
        mock_global.blocknet_bin = "blocknet"
        mock_global.blockdx_bin = "blockdx"
        mock_global.xlite_bin = "xlite"
        mock_global.xlite_daemon_bin = "xlite_daemon"
        mock_global.system = "Linux"

        # Mock process iteration
        mock_proc1 = Mock()
        mock_proc1.info = {"pid": 100, "name": "blocknet", "status": "running"}

        mock_proc2 = Mock()
        mock_proc2.info = {"pid": 200, "name": "blockdx", "status": "running"}

        mock_proc3 = Mock()
        mock_proc3.info = {"pid": 300, "name": "xlite", "status": "running"}

        mock_proc4 = Mock()
        mock_proc4.info = {"pid": 400, "name": "xlite_daemon", "status": "running"}

        mock_psutil.process_iter.return_value = [mock_proc1, mock_proc2, mock_proc3, mock_proc4]

        blocknet_pids, blockdx_pids, xlite_pids, xlite_daemon_pids = utils.processes_check()

        assert blocknet_pids == [100]
        assert blockdx_pids == [200]
        assert xlite_pids == [300]
        assert xlite_daemon_pids == [400]

    @patch('utilities.utils.psutil')
    @patch('utilities.utils.global_variables')
    def test_processes_check_zombie_process(self, mock_global, mock_psutil):
        """Test handling of zombie processes"""
        mock_global.blocknet_bin = "blocknet"
        mock_global.blockdx_bin = "blockdx"
        mock_global.xlite_bin = "xlite"
        mock_global.xlite_daemon_bin = "xlite_daemon"
        mock_global.system = "Linux"

        # Mock zombie process
        mock_proc = Mock()
        mock_proc.info = {"pid": 100, "name": "blocknet", "status": "zombie"}

        mock_psutil.process_iter.return_value = [mock_proc]
        mock_psutil.Process.return_value = mock_proc

        blocknet_pids, blockdx_pids, xlite_pids, xlite_daemon_pids = utils.processes_check()

        # Zombie process should not be added to list
        assert blocknet_pids == []
        mock_proc.wait.assert_called_once()

    @patch('utilities.utils.psutil')
    @patch('utilities.utils.global_variables')
    def test_processes_check_no_processes_found(self, mock_global, mock_psutil):
        """Test when no target processes are found"""
        mock_global.blocknet_bin = "blocknet"
        mock_global.blockdx_bin = "blockdx"
        mock_global.xlite_bin = "xlite"
        mock_global.xlite_daemon_bin = "xlite_daemon"
        mock_global.system = "Linux"

        # Mock process iteration with different process names
        mock_proc1 = Mock()
        mock_proc1.info = {"pid": 100, "name": "other_process", "status": "running"}

        mock_psutil.process_iter.return_value = [mock_proc1]

        blocknet_pids, blockdx_pids, xlite_pids, xlite_daemon_pids = utils.processes_check()

        assert blocknet_pids == []
        assert blockdx_pids == []
        assert xlite_pids == []
        assert xlite_daemon_pids == []


class TestHandleProcess:
    """Test handle_process helper function"""

    def test_handle_process_matching_name(self):
        """Test when process name matches target"""
        result = utils.handle_process(100, "blocknet", "running", "blocknet")
        assert result == 100

    def test_handle_process_zombie_status(self):
        """Test when process is zombie"""
        mock_proc = Mock()

        with patch('utilities.utils.psutil.Process', return_value=mock_proc):
            result = utils.handle_process(100, "blocknet", "zombie", "blocknet")

        assert result is None
        mock_proc.wait.assert_called_once()

    def test_handle_process_non_matching_name(self):
        """Test when process name doesn't match target"""
        result = utils.handle_process(100, "other_process", "running", "blocknet")
        assert result is None
