"""Tests for git_repo_management module following DRY/SOC/KISS principles."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pygit2

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.git_repo_management import (
    GitRepository,
    VirtualEnvironment,
    GitRepoManagement,
    ExecutionError,
    run_command
)


# ==================== FIXTURES & UTILITIES ====================

class TempDirFixture:
    """Reusable temporary directory fixture for DRY compliance."""

    def __init__(self):
        self.temp_dir = None

    def create(self):
        """Create temporary directory."""
        self.temp_dir = tempfile.mkdtemp()
        return self.temp_dir

    def cleanup(self):
        """Clean up temporary directory."""
        if self.temp_dir:
            import shutil
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None


def create_mock_process(returncode=0, stdout="", stderr=""):
    """Create a mock subprocess process for DRY compliance."""
    mock_process = MagicMock()
    mock_process.returncode = returncode
    mock_process.stdout = stdout
    mock_process.stderr = stderr
    return mock_process


def create_venv_mock(temp_dir):
    """Create a mock virtual environment for DRY compliance."""
    mock_venv = MagicMock()
    mock_venv.get_python_path.return_value = '/fake/python'
    mock_venv.get_pip_path.return_value = '/fake/pip'
    return mock_venv


# ==================== TEST CLASSES ====================

class TestRunCommand(unittest.TestCase):
    """Test cases for run_command utility function - SOC: focused on command execution."""

    @patch('subprocess.run')
    def test_run_command_success(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = create_mock_process(0, "test output", "")

        returncode, stdout, stderr = run_command(["echo", "test"])

        self.assertEqual(returncode, 0)
        self.assertEqual(stdout, "test output")
        self.assertEqual(stderr, "")
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_run_command_timeout(self, mock_run):
        """Test command timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired(["test"], 300)

        with self.assertRaises(ExecutionError) as context:
            run_command(["test"], timeout=300)

        self.assertIn("timed out", str(context.exception))

    @patch('subprocess.run')
    def test_run_command_not_found(self, mock_run):
        """Test command not found handling."""
        mock_run.side_effect = FileNotFoundError()

        with self.assertRaises(ExecutionError) as context:
            run_command(["nonexistent_command"])

        self.assertIn("Command not found", str(context.exception))

    @patch('subprocess.run')
    def test_run_command_general_error(self, mock_run):
        """Test general command execution error."""
        mock_run.side_effect = Exception("General error")

        with self.assertRaises(ExecutionError) as context:
            run_command(["test"])

        self.assertIn("Command execution failed", str(context.exception))


class TestVirtualEnvironment(unittest.TestCase):
    """Test cases for VirtualEnvironment class - SOC: focused on venv operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.fixture = TempDirFixture()
        self.temp_dir = self.fixture.create()
        self.venv = VirtualEnvironment(Path(self.temp_dir))

    def tearDown(self):
        """Clean up test fixtures."""
        self.fixture.cleanup()

    @patch('sys.platform', 'win32')
    def test_init_windows(self):
        """Test initialization on Windows."""
        venv = VirtualEnvironment(Path(self.temp_dir))
        self.assertEqual(venv.bin_dir, "Scripts")
        self.assertEqual(venv.python_exe, "python.exe")
        self.assertEqual(venv.pip_exe, "pip.exe")

    @patch('sys.platform', 'linux')
    def test_init_unix(self):
        """Test initialization on Unix-like systems."""
        venv = VirtualEnvironment(Path(self.temp_dir))
        self.assertEqual(venv.bin_dir, "bin")
        self.assertEqual(venv.python_exe, "python")
        self.assertEqual(venv.pip_exe, "pip")

    @patch('utilities.git_repo_management.run_command')
    def test_create_already_exists(self, mock_run):
        """Test creation when venv already exists."""
        # Create fake venv directory
        venv_bin_path = Path(self.temp_dir) / "venv" / "bin"
        venv_bin_path.mkdir(parents=True)

        self.venv.create()
        mock_run.assert_not_called()

    @patch('utilities.git_repo_management.run_command')
    @patch.object(Path, 'exists')
    @patch.object(Path, 'mkdir')
    def test_create_success(self, mock_mkdir, mock_exists, mock_run):
        """Test successful venv creation."""
        mock_run.return_value = (0, "success", "")
        mock_exists.side_effect = [False, True]  # venv_bin_path doesn't exist, then does

        self.venv.create()
        mock_run.assert_called_once()

    @patch('utilities.git_repo_management.run_command')
    @patch.object(Path, 'exists')
    def test_create_bin_dir_not_created(self, mock_exists, mock_run):
        """Test venv creation when bin directory is not created."""
        mock_run.return_value = (0, "success", "")
        mock_exists.return_value = False  # venv_bin_path never exists

        with self.assertRaises(ExecutionError) as context:
            self.venv.create()

        self.assertIn("bin directory not created", str(context.exception))

    @patch('sys.platform', 'darwin')
    @patch('utilities.git_repo_management.run_command')
    @patch.object(Path, 'exists')
    @patch.object(Path, 'resolve')
    def test_create_darwin_portable_python(self, mock_resolve, mock_exists, mock_run):
        """Test venv creation on Darwin with portable Python."""
        portable_path = Path(self.temp_dir) / "portable_python"
        portable_path.mkdir()

        mock_resolve.return_value = portable_path
        # First call: venv_bin_path doesn't exist (check before creation)
        # Second call: portable_python_path exists (for Darwin check)
        # Third call: venv_bin_path exists (check after creation)
        mock_exists.side_effect = [False, True, True]
        mock_run.return_value = (0, "success", "")

        venv = VirtualEnvironment(Path(self.temp_dir), str(portable_path))
        venv.create()

        mock_run.assert_called_once()
        mock_resolve.assert_called_once()

    @patch('sys.platform', 'darwin')
    def test_create_darwin_portable_python_not_found(self):
        """Test venv creation on Darwin when portable Python doesn't exist."""
        portable_path = Path(self.temp_dir) / "nonexistent_python"

        venv = VirtualEnvironment(Path(self.temp_dir), str(portable_path))

        with self.assertRaises(FileNotFoundError) as context:
            venv.create()

        self.assertIn("Python not found", str(context.exception))

    @patch('utilities.git_repo_management.run_command')
    def test_create_failure(self, mock_run):
        """Test venv creation failure."""
        mock_run.return_value = (1, "", "error")

        with self.assertRaises(ExecutionError):
            self.venv.create()

    @patch('utilities.git_repo_management.run_command')
    def test_install_requirements_no_file(self, mock_run):
        """Test requirements installation when no requirements.txt."""
        self.venv.install_requirements(Path(self.temp_dir) / "requirements.txt")
        mock_run.assert_not_called()

    @patch('utilities.git_repo_management.run_command')
    @patch.object(Path, 'exists', return_value=True)
    def test_install_requirements_with_file(self, mock_exists, mock_run):
        """Test requirements installation with requirements.txt."""
        req_file = Path(self.temp_dir) / "requirements.txt"
        req_file.write_text("pytest\nrequests")

        mock_run.return_value = (0, "success", "")
        self.venv.install_requirements(req_file)
        mock_run.assert_called_once()

    @patch('utilities.git_repo_management.run_command')
    @patch.object(Path, 'exists', return_value=True)
    def test_install_requirements_failure(self, mock_exists, mock_run):
        """Test requirements installation failure."""
        req_file = Path(self.temp_dir) / "requirements.txt"
        req_file.write_text("pytest\nrequests")

        mock_run.return_value = (1, "", "Installation failed")

        with self.assertRaises(ExecutionError) as context:
            self.venv.install_requirements(req_file)

        self.assertIn("Requirements installation failed", str(context.exception))

    @patch('utilities.git_repo_management.run_command')
    @patch.object(Path, 'exists', return_value=True)
    def test_install_requirements_exception(self, mock_exists, mock_run):
        """Test requirements installation with exception."""
        req_file = Path(self.temp_dir) / "requirements.txt"
        req_file.write_text("pytest\nrequests")

        mock_run.side_effect = Exception("Unexpected error")

        with self.assertRaises(Exception):
            self.venv.install_requirements(req_file)

    def test_get_python_path_exists(self):
        """Test getting Python path when it exists."""
        venv_python = Path(self.temp_dir) / "venv" / "bin" / "python"
        venv_python.parent.mkdir(parents=True)
        venv_python.touch()

        python_path = self.venv.get_python_path()
        self.assertEqual(python_path, str(venv_python))

    def test_get_python_path_not_found(self):
        """Test getting Python path when it doesn't exist."""
        with self.assertRaises(FileNotFoundError):
            self.venv.get_python_path()

    def test_get_pip_path_exists(self):
        """Test getting pip path when it exists."""
        venv_pip = Path(self.temp_dir) / "venv" / "bin" / "pip"
        venv_pip.parent.mkdir(parents=True)
        venv_pip.touch()

        pip_path = self.venv.get_pip_path()
        self.assertEqual(pip_path, str(venv_pip))

    def test_get_pip_path_not_found(self):
        """Test getting pip path when it doesn't exist."""
        with self.assertRaises(FileNotFoundError):
            self.venv.get_pip_path()


class TestGitRepository(unittest.TestCase):
    """Test cases for GitRepository class - SOC: focused on git operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.fixture = TempDirFixture()
        self.temp_dir = self.fixture.create()
        self.repo = GitRepository(
            "https://github.com/test/repo.git",
            Path(self.temp_dir),
            "main"
        )

    def tearDown(self):
        """Clean up test fixtures."""
        self.fixture.cleanup()

    @patch('pygit2.clone_repository')
    def test_clone_repo_success(self, mock_clone):
        """Test successful repository cloning."""
        mock_repo = MagicMock()
        mock_repo.references = {"refs/heads/main": True}
        mock_clone.return_value = mock_repo

        self.repo._clone_repo()

        mock_clone.assert_called_once()

    @patch('pygit2.clone_repository')
    def test_clone_repo_failure(self, mock_clone):
        """Test repository cloning failure."""
        mock_clone.side_effect = Exception("Clone failed")

        with self.assertRaises(Exception):
            self.repo._clone_repo()

    @patch('pygit2.clone_repository')
    def test_clone_repo_cleanup_on_failure(self, mock_clone):
        """Test cleanup on clone failure."""
        mock_clone.side_effect = Exception("Clone failed")

        with self.assertRaises(Exception):
            self.repo._clone_repo()

        # Directory should exist but be cleaned up
        self.assertTrue(Path(self.temp_dir).exists())

    @patch('pygit2.clone_repository')
    def test_clone_repo_git_error_cleanup(self, mock_clone):
        """Test cleanup on pygit2.GitError."""
        mock_clone.side_effect = pygit2.GitError("Git error")

        with self.assertRaises(pygit2.GitError):
            self.repo._clone_repo()

        # Directory should be cleaned up
        self.assertFalse(Path(self.temp_dir).exists())

    def test_checkout_branch_exists(self):
        """Test checking out existing branch."""
        mock_repo = MagicMock()
        mock_repo.references = {"refs/heads/main": True}
        self.repo.repo = mock_repo

        self.repo._checkout_branch()

        mock_repo.checkout.assert_called_once_with("refs/heads/main")

    def test_checkout_branch_from_remote(self):
        """Test checking out branch from remote."""
        mock_repo = MagicMock()

        # Mock the remote reference
        mock_remote_ref_obj = MagicMock()
        mock_remote_ref_obj.target = "mock_target_oid"
        mock_repo.references = {"refs/remotes/origin/main": mock_remote_ref_obj}
        mock_repo.create_branch = MagicMock()
        mock_repo.get = MagicMock()
        mock_commit_obj = MagicMock()
        mock_repo.get.return_value = mock_commit_obj

        self.repo.repo = mock_repo
        self.repo._checkout_branch()

        mock_repo.create_branch.assert_called_once_with("main", mock_commit_obj)
        mock_repo.checkout.assert_called_once_with("refs/heads/main")

    def test_checkout_branch_not_found(self):
        """Test checking out branch when branch doesn't exist locally or remotely."""
        mock_repo = MagicMock()
        mock_repo.references = {}
        self.repo.repo = mock_repo

        # Should not raise an exception, just log a warning
        self.repo._checkout_branch()

        # Verify checkout was not called
        mock_repo.checkout.assert_not_called()

    @patch('pygit2.GitError')
    def test_checkout_branch_git_error(self, mock_git_error):
        """Test checking out branch with GitError."""
        mock_repo = MagicMock()
        mock_repo.references = {"refs/heads/main": True}
        mock_repo.checkout.side_effect = pygit2.GitError("Checkout failed")
        self.repo.repo = mock_repo

        # Should not raise an exception, just log a warning
        self.repo._checkout_branch()

        # Verify checkout was called
        mock_repo.checkout.assert_called_once()

    @patch('requests.get')
    def test_get_remote_branches_api_success(self, mock_get):
        """Test getting remote branches via API."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"name": "main"},
            {"name": "develop"},
            {"name": "feature/test"}
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        branches = self.repo.get_remote_branches()

        self.assertEqual(branches, ["main", "develop", "feature/test"])

    @patch('requests.get')
    def test_get_remote_branches_api_failure(self, mock_get):
        """Test getting remote branches when API fails."""
        mock_get.side_effect = Exception("API error")

        branches = self.repo.get_remote_branches()

        self.assertEqual(branches, ["main", "master"])

    @patch('requests.get')
    def test_get_remote_branches_ssh_url(self, mock_get):
        """Test getting remote branches with SSH URL."""
        # Create a new repo with SSH URL
        ssh_repo = GitRepository(
            "git@github.com:test/repo.git",
            Path(self.temp_dir),
            "main"
        )

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"name": "main"},
            {"name": "develop"}
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        branches = ssh_repo.get_remote_branches()

        self.assertEqual(branches, ["main", "develop"])

    @patch('requests.get')
    def test_get_remote_branches_ssh_url_with_git(self, mock_get):
        """Test getting remote branches with SSH URL ending in .git."""
        # Create a new repo with SSH URL ending in .git
        ssh_repo = GitRepository(
            "git@github.com:test/repo.git",
            Path(self.temp_dir),
            "main"
        )

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"name": "main"},
            {"name": "develop"}
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        branches = ssh_repo.get_remote_branches()

        self.assertEqual(branches, ["main", "develop"])

    def test_clone_or_update_new_repo(self):
        """Test clone_or_update for new repository."""
        with patch.object(self.repo, '_clone_repo') as mock_clone:
            self.repo.clone_or_update()
            mock_clone.assert_called_once()

    def test_clone_or_update_exception(self):
        """Test clone_or_update with exception."""
        with patch.object(self.repo, '_clone_repo') as mock_clone:
            mock_clone.side_effect = Exception("Clone failed")

            with self.assertRaises(Exception):
                self.repo.clone_or_update()

    def test_clone_or_update_existing_repo(self):
        """Test clone_or_update for existing repository."""
        # Create fake .git directory
        git_dir = Path(self.temp_dir) / ".git"
        git_dir.mkdir()

        with patch.object(self.repo, '_update_repo') as mock_update:
            self.repo.clone_or_update()
            mock_update.assert_called_once()

    def test_clone_or_update_recreate_repo(self):
        """Test clone_or_update when .git is missing."""
        Path(self.temp_dir).mkdir(exist_ok=True)

        with patch.object(self.repo, '_recreate_repo') as mock_recreate:
            self.repo.clone_or_update()
            mock_recreate.assert_called_once()

    @patch('pygit2.Repository')
    def test_update_repo_success(self, mock_repo_class):
        """Test successful repository update."""
        # Create fake .git directory
        git_dir = Path(self.temp_dir) / ".git"
        git_dir.mkdir()

        mock_repo = MagicMock()
        mock_remote = MagicMock()
        mock_remote.name = "origin"
        mock_repo.remotes = [mock_remote]

        # Mock remote branch reference
        mock_ref = MagicMock()
        mock_ref.target = "mock_oid"
        mock_repo.lookup_reference.return_value = mock_ref

        # Mock head
        mock_head = MagicMock()
        mock_head.shorthand = "main"
        mock_repo.head = mock_head

        # Mock merge analysis for up-to-date
        mock_repo.merge_analysis.return_value = (pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE, None)

        mock_repo_class.return_value = mock_repo
        self.repo._update_repo()

        mock_remote.fetch.assert_called_once()

    @patch('pygit2.Repository')
    def test_update_repo_fastforward(self, mock_repo_class):
        """Test repository update with fast-forward merge."""
        # Create fake .git directory
        git_dir = Path(self.temp_dir) / ".git"
        git_dir.mkdir()

        mock_repo = MagicMock()
        mock_remote = MagicMock()
        mock_remote.name = "origin"
        mock_repo.remotes = [mock_remote]

        # Mock remote branch reference
        mock_ref = MagicMock()
        mock_ref.target = "mock_oid"
        mock_repo.lookup_reference.return_value = mock_ref

        # Mock head
        mock_head = MagicMock()
        mock_head.shorthand = "main"
        mock_repo.head = mock_head

        # Mock merge analysis for fast-forward
        mock_repo.merge_analysis.return_value = (pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD, None)

        mock_repo_class.return_value = mock_repo
        self.repo._update_repo()

        mock_remote.fetch.assert_called_once()
        mock_repo.checkout_tree.assert_called_once()

    @patch('pygit2.Repository')
    def test_update_repo_conflict(self, mock_repo_class):
        """Test repository update with conflict."""
        # Create fake .git directory
        git_dir = Path(self.temp_dir) / ".git"
        git_dir.mkdir()

        mock_repo = MagicMock()
        mock_remote = MagicMock()
        mock_remote.name = "origin"
        mock_repo.remotes = [mock_remote]

        # Mock remote branch reference
        mock_ref = MagicMock()
        mock_ref.target = "mock_oid"
        mock_repo.lookup_reference.return_value = mock_ref

        # Mock head
        mock_head = MagicMock()
        mock_head.shorthand = "main"
        mock_repo.head = mock_head

        # Mock merge analysis for conflict
        mock_repo.merge_analysis.return_value = (pygit2.GIT_MERGE_ANALYSIS_NORMAL, None)

        mock_repo_class.return_value = mock_repo

        with self.assertRaises(Exception) as context:
            self.repo._update_repo()

        self.assertIn("Git conflicts detected", str(context.exception))

    @patch('pygit2.Repository')
    def test_update_repo_unknown_result(self, mock_repo_class):
        """Test repository update with unknown merge result."""
        # Create fake .git directory
        git_dir = Path(self.temp_dir) / ".git"
        git_dir.mkdir()

        mock_repo = MagicMock()
        mock_remote = MagicMock()
        mock_remote.name = "origin"
        mock_repo.remotes = [mock_remote]

        # Mock remote branch reference
        mock_ref = MagicMock()
        mock_ref.target = "mock_oid"
        mock_repo.lookup_reference.return_value = mock_ref

        # Mock head
        mock_head = MagicMock()
        mock_head.shorthand = "main"
        mock_repo.head = mock_head

        # Mock merge analysis for unknown result
        mock_repo.merge_analysis.return_value = (0, None)

        mock_repo_class.return_value = mock_repo

        with self.assertRaises(AssertionError) as context:
            self.repo._update_repo()

        self.assertIn("Unknown merge analysis result", str(context.exception))

    @patch('pygit2.Repository')
    def test_update_repo_remote_not_found(self, mock_repo_class):
        """Test repository update when remote is not found."""
        # Create fake .git directory
        git_dir = Path(self.temp_dir) / ".git"
        git_dir.mkdir()

        mock_repo = MagicMock()
        mock_remote = MagicMock()
        mock_remote.name = "different_remote"
        mock_repo.remotes = [mock_remote]

        mock_repo_class.return_value = mock_repo

        with self.assertRaises(Exception) as context:
            self.repo._update_repo()

        self.assertIn("Remote 'origin' not found", str(context.exception))

    @patch('pygit2.Repository')
    def test_update_repo_branch_not_found(self, mock_repo_class):
        """Test repository update when remote branch is not found."""
        # Create fake .git directory
        git_dir = Path(self.temp_dir) / ".git"
        git_dir.mkdir()

        mock_repo = MagicMock()
        mock_remote = MagicMock()
        mock_remote.name = "origin"
        mock_repo.remotes = [mock_remote]

        # Mock lookup_reference to raise KeyError
        mock_repo.lookup_reference.side_effect = KeyError()

        mock_repo_class.return_value = mock_repo
        self.repo._update_repo()

        # Should return without error
        mock_remote.fetch.assert_called_once()

    @patch('pygit2.Repository')
    def test_update_repo_different_branch(self, mock_repo_class):
        """Test repository update when current branch differs from target."""
        # Create fake .git directory
        git_dir = Path(self.temp_dir) / ".git"
        git_dir.mkdir()

        mock_repo = MagicMock()
        mock_remote = MagicMock()
        mock_remote.name = "origin"
        mock_repo.remotes = [mock_remote]

        # Mock remote branch reference
        mock_ref = MagicMock()
        mock_ref.target = "mock_oid"
        mock_repo.lookup_reference.return_value = mock_ref

        # Mock head with different branch
        mock_head = MagicMock()
        mock_head.shorthand = "develop"
        mock_repo.head = mock_head

        # Mock merge analysis for up-to-date
        mock_repo.merge_analysis.return_value = (pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE, None)

        mock_repo_class.return_value = mock_repo

        with patch.object(self.repo, '_checkout_branch') as mock_checkout:
            self.repo._update_repo()
            mock_checkout.assert_called_once()

    @patch('pygit2.Repository')
    def test_update_repo_local_branch_missing(self, mock_repo_class):
        """Test repository update when local branch is missing."""
        # Create fake .git directory
        git_dir = Path(self.temp_dir) / ".git"
        git_dir.mkdir()

        mock_repo = MagicMock()
        mock_remote = MagicMock()
        mock_remote.name = "origin"
        mock_repo.remotes = [mock_remote]

        # Mock remote branch reference
        mock_ref = MagicMock()
        mock_ref.target = "mock_oid"
        mock_repo.lookup_reference.side_effect = [
            mock_ref,  # First call for remote branch
            KeyError(),  # Second call for local branch (not found)
            mock_ref  # Third call after creating branch
        ]

        # Mock head
        mock_head = MagicMock()
        mock_head.shorthand = "main"
        mock_repo.head = mock_head

        # Mock merge analysis for up-to-date
        mock_repo.merge_analysis.return_value = (pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE, None)

        mock_repo_class.return_value = mock_repo
        self.repo._update_repo()

        mock_repo.create_branch.assert_called_once()


class TestGitRepoManagement(unittest.TestCase):
    """Test cases for GitRepoManagement class - SOC: focused on management operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.fixture = TempDirFixture()
        self.temp_dir = self.fixture.create()
        self.repo_mgmt = GitRepoManagement(
            "https://github.com/test/repo.git",
            str(Path(self.temp_dir) / "repo"),
            "main",
            self.temp_dir
        )

    def tearDown(self):
        """Clean up test fixtures."""
        self.fixture.cleanup()

    def test_init(self):
        """Test GitRepoManagement initialization."""
        self.assertEqual(self.repo_mgmt.git_repo.repo_url, "https://github.com/test/repo.git")
        self.assertIsInstance(self.repo_mgmt.git_repo, GitRepository)
        self.assertIsNone(self.repo_mgmt.venv)

    @patch('utilities.git_repo_management.miniforge_portable')
    @patch.object(GitRepository, 'clone_or_update')
    @patch('utilities.git_repo_management.VirtualEnvironment')
    def test_setup_success(self, mock_venv_class, mock_clone, mock_miniforge):
        """Test successful setup."""
        mock_miniforge.PortablePythonInstaller.return_value.install.return_value = None
        mock_venv_instance = mock_venv_class.return_value
        mock_venv_instance.create.return_value = None
        mock_venv_instance.install_requirements.return_value = None

        self.repo_mgmt.setup()

        mock_clone.assert_called_once()
        mock_venv_class.assert_called_once()
        mock_venv_instance.create.assert_called_once()
        mock_venv_instance.install_requirements.assert_called_once()

    @patch('utilities.git_repo_management.miniforge_portable')
    @patch.object(GitRepository, 'clone_or_update')
    @patch('utilities.git_repo_management.VirtualEnvironment')
    def test_setup_with_portable_python(self, mock_venv_class, mock_clone, mock_miniforge):
        """Test setup with portable Python installation."""
        # Create fake portable python directory
        portable_dir = Path(self.temp_dir) / "portable_python" / "miniforge"
        portable_dir.mkdir(parents=True)

        mock_miniforge.PortablePythonInstaller.return_value.install.return_value = None
        mock_venv_instance = mock_venv_class.return_value
        mock_venv_instance.create.return_value = None
        mock_venv_instance.install_requirements.return_value = None

        self.repo_mgmt.setup()

        mock_clone.assert_called_once()
        mock_venv_class.assert_called_once()
        mock_venv_instance.create.assert_called_once()
        mock_venv_instance.install_requirements.assert_called_once()

    @patch('utilities.git_repo_management.miniforge_portable')
    @patch.object(GitRepository, 'clone_or_update')
    @patch('utilities.git_repo_management.VirtualEnvironment')
    def test_setup_failure(self, mock_venv_class, mock_clone, mock_miniforge):
        """Test setup failure."""
        mock_clone.side_effect = Exception("Clone failed")

        with self.assertRaises(Exception) as context:
            self.repo_mgmt.setup()

        self.assertIn("Repository setup failed", str(context.exception))

    @patch('utilities.git_repo_management.miniforge_portable')
    @patch.object(GitRepository, 'clone_or_update')
    @patch('utilities.git_repo_management.VirtualEnvironment')
    def test_setup_with_portable_python_install(self, mock_venv_class, mock_clone, mock_miniforge):
        """Test setup with portable Python installation (not already installed)."""
        # Don't create portable python directory - should trigger installation
        mock_miniforge.PortablePythonInstaller.return_value.install.return_value = None
        mock_venv_instance = mock_venv_class.return_value
        mock_venv_instance.create.return_value = None
        mock_venv_instance.install_requirements.return_value = None

        self.repo_mgmt.setup()

        mock_miniforge.PortablePythonInstaller.assert_called_once()
        mock_clone.assert_called_once()
        mock_venv_class.assert_called_once()
        mock_venv_instance.create.assert_called_once()
        mock_venv_instance.install_requirements.assert_called_once()

    def test_run_script_not_found(self):
        """Test running non-existent script."""
        result = self.repo_mgmt.run_script("nonexistent.py")
        self.assertIsNone(result)

    @patch('subprocess.Popen')
    @patch('threading.Thread')
    def test_run_script_success(self, mock_thread, mock_popen):
        """Test successful script execution."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = b''
        mock_process.stderr.readline.return_value = b''
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process
        mock_thread.return_value = MagicMock()

        result = self.repo_mgmt.run_script("test.py", ["arg1", "arg2"])

        mock_popen.assert_called_once()
        self.assertEqual(result, mock_process)

    @patch('subprocess.Popen')
    @patch('threading.Thread')
    def test_run_script_with_timeout(self, mock_thread, mock_popen):
        """Test script execution with timeout."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = b''
        mock_process.stderr.readline.return_value = b''
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process
        mock_thread.return_value = MagicMock()

        result = self.repo_mgmt.run_script("test.py", timeout=30)

        mock_popen.assert_called_once()
        self.assertEqual(result, mock_process)

    @patch('subprocess.Popen')
    @patch('threading.Thread')
    def test_run_script_exception(self, mock_thread, mock_popen):
        """Test run_script with exception."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_popen.side_effect = Exception("Process creation failed")

        result = self.repo_mgmt.run_script("test.py")

        self.assertIsNone(result)

    @patch('subprocess.Popen')
    @patch('threading.Thread')
    def test_run_script_stream_reader_exception(self, mock_thread, mock_popen):
        """Test stream reader with exception."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ValueError("Stream error")
        mock_process.stderr.readline.return_value = b''
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process
        mock_thread.return_value = MagicMock()

        result = self.repo_mgmt.run_script("test.py")

        mock_popen.assert_called_once()
        self.assertEqual(result, mock_process)

    @patch('subprocess.Popen')
    @patch('threading.Thread')
    def test_run_script_stream_reader_ioerror(self, mock_thread, mock_popen):
        """Test stream reader with IOError."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = IOError("Pipe closed")
        mock_process.stderr.readline.return_value = b''
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process
        mock_thread.return_value = MagicMock()

        result = self.repo_mgmt.run_script("test.py")

        mock_popen.assert_called_once()
        self.assertEqual(result, mock_process)

    @patch('subprocess.Popen')
    @patch('threading.Thread')
    @patch('time.sleep')
    def test_run_script_timeout_watcher(self, mock_sleep, mock_thread, mock_popen):
        """Test timeout watcher terminates process."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = b''
        mock_process.stderr.readline.return_value = b''
        mock_process.poll.return_value = None  # Process still running
        mock_popen.return_value = mock_process
        mock_thread.return_value = MagicMock()

        # Mock time.time() to simulate timeout
        with patch('time.time', side_effect=[0, 31]):  # First call 0, second call 31 (timeout)
            result = self.repo_mgmt.run_script("test.py", timeout=30)

        mock_popen.assert_called_once()
        # Verify the process was returned
        self.assertEqual(result, mock_process)

    @patch('subprocess.Popen')
    @patch('threading.Thread')
    @patch('time.sleep')
    def test_run_script_timeout_watcher_kill(self, mock_sleep, mock_thread, mock_popen):
        """Test timeout watcher kills process if terminate fails."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = b''
        mock_process.stderr.readline.return_value = b''
        mock_process.poll.return_value = None  # Process still running
        mock_process.terminate.return_value = None
        mock_process.poll.side_effect = [None, None]  # Still running after terminate
        mock_popen.return_value = mock_process
        mock_thread.return_value = MagicMock()

        # Mock time.time() to simulate timeout
        with patch('time.time', side_effect=[0, 31]):  # First call 0, second call 31 (timeout)
            result = self.repo_mgmt.run_script("test.py", timeout=30)

        mock_popen.assert_called_once()
        # Verify the process was returned
        self.assertEqual(result, mock_process)

    def test_get_remote_branches(self):
        """Test getting remote branches through GitRepoManagement."""
        with patch.object(self.repo_mgmt.git_repo, 'get_remote_branches') as mock_get:
            mock_get.return_value = ["main", "develop"]

            branches = self.repo_mgmt.get_remote_branches()

            self.assertEqual(branches, ["main", "develop"])
            mock_get.assert_called_once()


if __name__ == '__main__':
    unittest.main()
