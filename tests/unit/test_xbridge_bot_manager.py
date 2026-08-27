"""Tests for XBridgeBotManager following DRY/SOC/KISS principles."""
import os
import sys
import tempfile
import unittest
from subprocess import TimeoutExpired
from unittest.mock import MagicMock, Mock, call, patch

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gui.xbridge_bot_manager import XBridgeBotManager


class TestXBridgeBotManager(unittest.TestCase):
    """Test cases for XBridgeBotManager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.bot_manager = XBridgeBotManager()
        # Mock repo_management to prevent actual Git operations
        self.bot_manager.repo_management = MagicMock()
        # Mock target_dir_path to simulate existing repo
        self.bot_manager.target_dir_path = MagicMock()
        self.bot_manager.target_dir_path.exists.return_value = True
        self.bot_manager.target_dir_path.__truediv__.return_value.is_dir.return_value = True

    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'bot_manager'):
            self.bot_manager.process = None
            if self.bot_manager.installer_thread and self.bot_manager.installer_thread.is_alive():
                self.bot_manager.installer_thread.join(timeout=1)

    # =========================================================================
    # INITIALIZATION TESTS
    # =========================================================================

    def test_init_default(self):
        """Test initialization with default branch."""
        self.assertEqual(self.bot_manager.current_branch, "main")
        self.assertEqual(self.bot_manager.author, "tryiou")
        self.assertEqual(self.bot_manager.repo_name, "xbridge_trading_bots")
        self.assertFalse(self.bot_manager.started)
        self.assertIsNone(self.bot_manager.installer_thread)
        self.assertIsNone(self.bot_manager.process)

    def test_init_custom_branch(self):
        """Test initialization with custom branch (no persisted value)."""
        with patch.object(XBridgeBotManager, '_load_saved_branch', return_value=None):
            bot_manager = XBridgeBotManager("develop")
            self.assertEqual(bot_manager.current_branch, "develop")
            self.assertIsNone(bot_manager.installer_thread)
            self.assertIsNone(bot_manager.process)

    # =========================================================================
    # REPOSITORY EXISTENCE TESTS
    # =========================================================================

    def test_repo_exists_true(self):
        """Test repo_exists returns True when directory exists."""
        self.bot_manager.target_dir_path.exists.return_value = True
        self.bot_manager.target_dir_path.__truediv__.return_value.is_dir.return_value = True
        self.assertTrue(self.bot_manager.repo_exists())

    def test_repo_exists_false(self):
        """Test repo_exists returns False when directory doesn't exist."""
        self.bot_manager.target_dir_path.exists.return_value = False
        self.assertFalse(self.bot_manager.repo_exists())

    # =========================================================================
    # BRANCH MANAGEMENT TESTS
    # =========================================================================

    def test_get_available_branches_success(self):
        """Test successful branch retrieval."""
        with patch.object(self.bot_manager.repo_management, 'get_remote_branches') as mock_get_branches:
            mock_get_branches.return_value = ["main", "develop", "feature/test"]
            branches = self.bot_manager.get_available_branches()
            self.assertEqual(branches, ["main", "develop", "feature/test"])

    def test_get_available_branches_with_error(self):
        """Test branch retrieval with error returns None."""
        with patch.object(self.bot_manager.repo_management, 'get_remote_branches') as mock_get_branches:
            mock_get_branches.side_effect = Exception("Network error")
            branches = self.bot_manager.get_available_branches()
            self.assertIsNone(branches)

    # =========================================================================
    # INSTALL/UPDATE TESTS
    # =========================================================================

    def test_install_or_update_no_branch(self):
        """Test install/update with empty branch."""
        with patch('gui.xbridge_bot_manager.logger.error') as mock_log_error:
            self.bot_manager.install_or_update("")
            mock_log_error.assert_called_once_with("Invalid branch name: empty string")

    def test_install_or_update_invalid_branch(self):
        """Test install/update with None branch."""
        with patch('gui.xbridge_bot_manager.logger.error') as mock_log_error:
            self.bot_manager.install_or_update(None)
            mock_log_error.assert_called_once_with("Invalid branch name: empty string")

    def test_install_or_update_already_running(self):
        """Test install/update when installer thread is already alive."""
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        self.bot_manager.installer_thread = mock_thread

        with patch('gui.xbridge_bot_manager.logger.warning') as mock_log_warning:
            self.bot_manager.install_or_update("main")
            mock_log_warning.assert_called_once_with("Install/update already in progress - skipping")

    @patch('threading.Thread')
    def test_install_or_update_success(self, mock_thread):
        """Test successful install/update starts a thread."""
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        self.bot_manager.install_or_update("main")

        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    # =========================================================================
    # DO_INSTALL_UPDATE TESTS
    # =========================================================================

    def test_do_install_update_success(self):
        """Test successful install/update execution."""
        with patch('gui.xbridge_bot_manager.GitRepoManagement') as mock_git_repo, \
                patch('gui.xbridge_bot_manager.logger.info') as mock_log_info:
            # Mock target_dir_path to not exist initially
            self.bot_manager.target_dir_path.exists.return_value = False

            # Mock GitRepoManagement constructor
            mock_repo_instance = MagicMock()
            mock_git_repo.return_value = mock_repo_instance

            # Call the actual method
            self.bot_manager._do_install_update("develop")

            # Verify target_dir_path.mkdir was called
            self.bot_manager.target_dir_path.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            # Verify repo_management.setup was called
            mock_repo_instance.setup.assert_called_once()
            # Verify current_branch was updated
            self.assertEqual(self.bot_manager.current_branch, "develop")

    def test_do_install_update_target_dir_exists(self):
        """Test install/update when target directory already exists."""
        with patch('gui.xbridge_bot_manager.GitRepoManagement') as mock_git_repo, \
                patch('gui.xbridge_bot_manager.logger.info') as mock_log_info:
            # Mock target_dir_path to exist
            self.bot_manager.target_dir_path.exists.return_value = True

            # Mock GitRepoManagement constructor
            mock_repo_instance = MagicMock()
            mock_git_repo.return_value = mock_repo_instance

            # Call the actual method
            self.bot_manager._do_install_update("main")

            # Verify directory creation was NOT attempted
            self.bot_manager.target_dir_path.mkdir.assert_not_called()
            # Verify repo_management.setup was called
            mock_repo_instance.setup.assert_called_once()

    def test_do_install_update_with_config_conflict(self):
        """Test install/update handles BranchSwitchBlockedError."""
        from utilities.git_repo_management import BranchSwitchBlockedError
        with patch('gui.xbridge_bot_manager.GitRepoManagement') as mock_git_repo, \
                patch('gui.xbridge_bot_manager.logger.error') as mock_log_error:
            mock_repo_instance = MagicMock()
            mock_git_repo.return_value = mock_repo_instance
            mock_repo_instance.setup.side_effect = BranchSwitchBlockedError("blocked")
            self.bot_manager._do_install_update("main")
            mock_log_error.assert_called()

    def test_do_install_update_with_other_error(self):
        """Test install/update handles non-config errors."""
        with patch('gui.xbridge_bot_manager.GitRepoManagement') as mock_git_repo, \
                patch('gui.xbridge_bot_manager.logger.error') as mock_log_error:
            # Mock GitRepoManagement constructor
            mock_repo_instance = MagicMock()
            mock_git_repo.return_value = mock_repo_instance
            # Simulate generic error
            mock_repo_instance.setup.side_effect = Exception("Some other error")

            # Call the actual method
            self.bot_manager._do_install_update("main")

            # Verify error was logged
            mock_log_error.assert_called_once()
            # Verify installer_thread was reset
            self.assertIsNone(self.bot_manager.installer_thread)

    def test_do_install_update_with_deferred_start(self):
        """Test install/update triggers deferred execution after success."""
        with patch('gui.xbridge_bot_manager.GitRepoManagement') as mock_git_repo, \
                patch.object(self.bot_manager, '_start_execution') as mock_start_execution, \
                patch('gui.xbridge_bot_manager.logger.debug') as mock_log_debug:
            # Mock GitRepoManagement constructor
            mock_repo_instance = MagicMock()
            mock_git_repo.return_value = mock_repo_instance
            # Set deferred start flag
            self.bot_manager.deferred_start = True

            # Call the actual method
            self.bot_manager._do_install_update("main")

            # Verify deferred start was triggered
            mock_start_execution.assert_called_once()
            # Verify deferred flag was reset
            self.assertFalse(self.bot_manager.deferred_start)

    def test_do_install_update_deferred_start_on_failure(self):
        """Test deferred start is reset on installation failure."""
        with patch('gui.xbridge_bot_manager.GitRepoManagement') as mock_git_repo, \
                patch('gui.xbridge_bot_manager.logger.error') as mock_log_error:
            # Mock GitRepoManagement constructor
            mock_repo_instance = MagicMock()
            mock_git_repo.return_value = mock_repo_instance
            # Set deferred start flag
            self.bot_manager.deferred_start = True
            # Simulate error
            mock_repo_instance.setup.side_effect = Exception("Error")

            # Call the actual method
            self.bot_manager._do_install_update("main")

            # Verify deferred flag was reset
            self.assertFalse(self.bot_manager.deferred_start)

    # =========================================================================
    # CONFIG FOLDER RENAME REMOVED - replaced by BranchSwitchBlockedError handling
    # =========================================================================

    def test_handle_config_folder_rename(self):
        """handle_config_folder_rename was removed."""
        self.assertFalse(hasattr(self.bot_manager, 'handle_config_folder_rename'))

    def test_handle_config_folder_rename_no_config(self):
        self.assertFalse(hasattr(self.bot_manager, 'handle_config_folder_rename'))

    def test_handle_config_folder_rename_with_error(self):
        self.assertFalse(hasattr(self.bot_manager, 'handle_config_folder_rename'))

    # =========================================================================
    # DELETE LOCAL REPO TESTS
    # =========================================================================

    def test_delete_local_repo_exists(self):
        """Test deleting repository when it exists."""
        with patch('os.path.exists') as mock_exists, \
                patch('shutil.rmtree') as mock_rmtree, \
                patch('gui.xbridge_bot_manager.logger.info') as mock_log_info:
            mock_exists.return_value = True
            self.bot_manager.delete_local_repo()

            mock_log_info.assert_called()
            mock_rmtree.assert_called_once()
            self.assertIsNone(self.bot_manager.repo_management)
            self.assertEqual(self.bot_manager.current_branch, "main")

    def test_delete_local_repo_no_repo(self):
        """Test deleting repository when it doesn't exist."""
        with patch.object(self.bot_manager, 'repo_exists') as mock_exists, \
                patch('gui.xbridge_bot_manager.logger.warning') as mock_log_warning:
            mock_exists.return_value = False
            self.bot_manager.delete_local_repo()
            mock_log_warning.assert_called_once_with("No repository found to delete")

    def test_delete_local_repo_with_error(self):
        """Test deleting repository with error."""
        with patch('os.path.exists') as mock_exists, \
                patch('shutil.rmtree') as mock_rmtree, \
                patch('gui.xbridge_bot_manager.logger.error') as mock_log_error:
            mock_exists.return_value = True
            mock_rmtree.side_effect = Exception("Permission denied")
            self.bot_manager.delete_local_repo()

            mock_log_error.assert_called_once()

    # =========================================================================
    # TOGGLE EXECUTION TESTS
    # =========================================================================

    def test_toggle_execution_no_repo(self):
        """Test toggle execution when repo doesn't exist."""
        with patch.object(self.bot_manager, 'repo_exists') as mock_exists, \
                patch.object(self.bot_manager, 'install_or_update') as mock_install:
            mock_exists.return_value = False
            self.bot_manager.toggle_execution("main")

            mock_install.assert_called_once_with("main")

    def test_toggle_execution_no_venv(self):
        """Test toggle execution when repo setup incomplete."""
        with patch.object(self.bot_manager, 'repo_exists') as mock_exists, \
                patch.object(self.bot_manager, 'install_or_update') as mock_install:
            mock_exists.return_value = True
            self.bot_manager.repo_management = None  # Repo setup not done
            self.bot_manager.toggle_execution("main")

            mock_install.assert_called_once_with("main")

    def test_toggle_execution_start(self):
        """Test toggle execution to start bots."""
        with patch.object(self.bot_manager, 'repo_exists') as mock_exists, \
                patch.object(self.bot_manager, '_start_execution') as mock_start, \
                patch.object(self.bot_manager, '_stop_execution') as mock_stop:
            mock_exists.return_value = True
            self.bot_manager.repo_management.venv = "/fake/venv"
            self.bot_manager.process = None

            # Set the side effect to update the started flag when mock_start is called
            def start_execution():
                self.bot_manager.started = True

            mock_start.side_effect = start_execution

            self.bot_manager.toggle_execution("main")

            mock_start.assert_called_once()
            self.assertTrue(self.bot_manager.started)

    def test_toggle_execution_stop(self):
        """Test toggle execution to stop bots."""
        with patch.object(self.bot_manager, 'repo_exists') as mock_exists, \
                patch.object(self.bot_manager, '_start_execution') as mock_start, \
                patch.object(self.bot_manager, '_stop_execution') as mock_stop:
            mock_exists.return_value = True
            self.bot_manager.repo_management.venv = "/fake/venv"
            mock_process = MagicMock()
            mock_process.poll.return_value = None
            self.bot_manager.process = mock_process

            self.bot_manager.toggle_execution("main")

            mock_stop.assert_called_once()
            self.assertFalse(self.bot_manager.started)

    def test_toggle_execution_branch_mismatch(self):
        """Test toggle execution with branch mismatch triggers install."""
        with patch.object(self.bot_manager, 'repo_exists') as mock_exists, \
                patch.object(self.bot_manager, 'install_or_update') as mock_install:
            mock_exists.return_value = True
            self.bot_manager.current_branch = "main"
            self.bot_manager.repo_management.venv = "/fake/venv"

            self.bot_manager.toggle_execution("develop")

            mock_install.assert_called_once_with("develop")

    def test_toggle_execution_installer_thread_alive(self):
        """Test toggle_execution when installer thread is alive."""
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True
        self.bot_manager.installer_thread = mock_thread

        with patch('gui.xbridge_bot_manager.logger.info') as mock_log_info:
            self.bot_manager.toggle_execution("main")
            mock_log_info.assert_called_with("Deferring execution until installation completes")
            self.assertTrue(self.bot_manager.deferred_start)

    # =========================================================================
    # START EXECUTION TESTS
    # =========================================================================

    def test_start_execution_no_repo_management(self):
        """Test _start_execution when repo_management is None."""
        self.bot_manager.repo_management = None

        with patch('gui.xbridge_bot_manager.logger.error') as mock_log_error:
            self.bot_manager._start_execution()
            mock_log_error.assert_called_once_with("Cannot start execution - repo management not initialized")

    def test_start_execution_already_running(self):
        """Test _start_execution when bots are already running."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        self.bot_manager.process = mock_process

        with patch('gui.xbridge_bot_manager.logger.info') as mock_log_info:
            self.bot_manager._start_execution()
            mock_log_info.assert_called_with("Bots already running")

    def test_start_execution_no_process_returned(self):
        """Test _start_execution when no process is returned."""
        with patch.object(self.bot_manager.repo_management, 'run_script') as mock_run_script, \
                patch('gui.xbridge_bot_manager.logger.error') as mock_log_error:
            mock_run_script.return_value = None
            self.bot_manager._start_execution()
            mock_log_error.assert_called_once_with("Failed to start bots - no process returned")

    def test_start_execution_success(self):
        """Test _start_execution successfully starts bots."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        with patch.object(self.bot_manager.repo_management, 'run_script') as mock_run_script, \
                patch('gui.xbridge_bot_manager.logger.info') as mock_log_info:
            mock_run_script.return_value = mock_process
            self.bot_manager._start_execution()

            mock_run_script.assert_called_once_with("main_gui.py")
            self.assertEqual(self.bot_manager.process, mock_process)
            self.assertTrue(self.bot_manager.started)

    # =========================================================================
    # STOP EXECUTION TESTS
    # =========================================================================

    def test_stop_bots_success(self):
        """Test stopping bots successfully."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.wait.return_value = 0
        self.bot_manager.process = mock_process

        self.bot_manager._stop_execution()

        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=10)
        self.assertIsNone(self.bot_manager.process)
        self.assertFalse(self.bot_manager.started)

    def test_stop_bots_no_process(self):
        """Test stopping bots when no process exists."""
        self.bot_manager.process = None

        # Should not raise any exception
        self.bot_manager._stop_execution()

    def test_stop_bots_with_kill(self):
        """Test stopping bots with kill after timeout."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = TimeoutExpired("timeout", 10)
        self.bot_manager.process = mock_process

        with patch('gui.xbridge_bot_manager.logger.warning') as mock_log_warning:
            self.bot_manager._stop_execution()
            mock_log_warning.assert_called_once_with("Process not terminating, forcing kill")
            mock_process.kill.assert_called_once()


if __name__ == '__main__':
    unittest.main()
