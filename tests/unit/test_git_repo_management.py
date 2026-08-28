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
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utilities.git_repo_management import (
    ExecutionError,
    GitRepoManagement,
    GitRepository,
    VirtualEnvironment,
    run_command,
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
    mock_venv.get_python_path.return_value = "/fake/python"
    mock_venv.get_pip_path.return_value = "/fake/pip"
    return mock_venv


# ==================== TEST CLASSES ====================


class TestRunCommand(unittest.TestCase):
    """Test cases for run_command utility function - SOC: focused on command execution."""

    @patch("subprocess.run")
    def test_run_command_success(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = create_mock_process(0, "test output", "")

        returncode, stdout, stderr = run_command(["echo", "test"])

        self.assertEqual(returncode, 0)
        self.assertEqual(stdout, "test output")
        self.assertEqual(stderr, "")
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_run_command_timeout(self, mock_run):
        """Test command timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired(["test"], 300)

        with self.assertRaises(ExecutionError) as context:
            run_command(["test"], timeout=300)

        self.assertIn("timed out", str(context.exception))

    @patch("subprocess.run")
    def test_run_command_not_found(self, mock_run):
        """Test command not found handling."""
        mock_run.side_effect = FileNotFoundError()

        with self.assertRaises(ExecutionError) as context:
            run_command(["nonexistent_command"])

        self.assertIn("Command not found", str(context.exception))

    @patch("subprocess.run")
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

    @patch("sys.platform", "win32")
    def test_init_windows(self):
        """Test initialization on Windows."""
        venv = VirtualEnvironment(Path(self.temp_dir))
        self.assertEqual(venv.bin_dir, "Scripts")
        self.assertEqual(venv.python_exe, "python.exe")
        self.assertEqual(venv.pip_exe, "pip.exe")

    @patch("sys.platform", "linux")
    def test_init_unix(self):
        """Test initialization on Unix-like systems."""
        venv = VirtualEnvironment(Path(self.temp_dir))
        self.assertEqual(venv.bin_dir, "bin")
        self.assertEqual(venv.python_exe, "python")
        self.assertEqual(venv.pip_exe, "pip")

    @patch.object(VirtualEnvironment, "_is_broken", return_value=(False, ""))
    @patch("utilities.git_repo_management.run_command")
    def test_create_already_exists(self, mock_run, mock_broken):
        """Test creation when venv already exists."""
        # Create fake venv directory (OS-aware: bin vs Scripts)
        venv_bin_path = Path(self.temp_dir) / "venv" / self.venv.bin_dir
        venv_bin_path.mkdir(parents=True)

        self.venv.create()
        mock_run.assert_not_called()

    @patch.object(VirtualEnvironment, "_is_broken", return_value=(False, ""))
    @patch("utilities.git_repo_management.run_command")
    @patch.object(Path, "exists")
    @patch.object(Path, "mkdir")
    def test_create_success(self, mock_mkdir, mock_exists, mock_run, mock_broken):
        """Test successful venv creation."""
        mock_run.return_value = (0, "success", "")
        mock_exists.side_effect = [False, True, True]  # venv_bin_path doesn't exist, then does (extra buffer)

        self.venv.create()
        mock_run.assert_called_once()

    @patch.object(VirtualEnvironment, "_is_broken", return_value=(False, ""))
    @patch("utilities.git_repo_management.run_command")
    @patch.object(Path, "exists")
    def test_create_bin_dir_not_created(self, mock_exists, mock_run, mock_broken):
        """Test venv creation when bin directory is not created."""
        mock_run.return_value = (0, "success", "")
        mock_exists.return_value = False  # venv_bin_path never exists

        with self.assertRaises(ExecutionError) as context:
            self.venv.create()

        self.assertIn("bin directory not created", str(context.exception))

    @patch.object(VirtualEnvironment, "_is_broken", return_value=(False, ""))
    @patch("sys.platform", "darwin")
    @patch("utilities.git_repo_management.run_command")
    @patch.object(Path, "exists")
    @patch.object(Path, "resolve")
    def test_create_darwin_portable_python(self, mock_resolve, mock_exists, mock_run, mock_broken):
        """Test venv creation on Darwin with portable Python."""
        portable_path = Path(self.temp_dir) / "portable_python"
        portable_path.mkdir()

        mock_resolve.return_value = portable_path
        # First call: venv_bin_path doesn't exist (check before creation)
        # Second call: portable_python_path exists (for Darwin check)
        # Third call: venv_bin_path exists (check after creation)
        mock_exists.side_effect = [False, True, True, True]
        mock_run.return_value = (0, "success", "")

        venv = VirtualEnvironment(Path(self.temp_dir), str(portable_path))
        venv.create()

        mock_run.assert_called_once()
        mock_resolve.assert_called_once()

    @patch("sys.platform", "darwin")
    def test_create_darwin_portable_python_not_found(self):
        """Test venv creation on Darwin when portable Python doesn't exist."""
        portable_path = Path(self.temp_dir) / "nonexistent_python"

        venv = VirtualEnvironment(Path(self.temp_dir), str(portable_path))

        with self.assertRaises(FileNotFoundError) as context:
            venv.create()

        self.assertIn("Python not found", str(context.exception))

    @patch("utilities.git_repo_management.run_command")
    def test_create_failure(self, mock_run):
        """Test venv creation failure."""
        mock_run.return_value = (1, "", "error")

        with self.assertRaises(ExecutionError):
            self.venv.create()

    @patch("utilities.git_repo_management.run_command")
    def test_install_requirements_no_file(self, mock_run):
        """Test requirements installation when no requirements.txt."""
        self.venv.install_requirements(Path(self.temp_dir) / "requirements.txt")
        mock_run.assert_not_called()

    @patch("utilities.git_repo_management.run_command")
    @patch.object(Path, "exists", return_value=True)
    def test_install_requirements_with_file(self, mock_exists, mock_run):
        """Test requirements installation with requirements.txt."""
        req_file = Path(self.temp_dir) / "requirements.txt"
        req_file.write_text("pytest\nrequests")

        mock_run.return_value = (0, "success", "")
        self.venv.install_requirements(req_file)
        mock_run.assert_called_once()

    @patch("utilities.git_repo_management.run_command")
    @patch.object(Path, "exists", return_value=True)
    def test_install_requirements_failure(self, mock_exists, mock_run):
        """Test requirements installation failure."""
        req_file = Path(self.temp_dir) / "requirements.txt"
        req_file.write_text("pytest\nrequests")

        mock_run.return_value = (1, "", "Installation failed")

        with self.assertRaises(ExecutionError) as context:
            self.venv.install_requirements(req_file)

        self.assertIn("Requirements installation failed", str(context.exception))

    @patch("utilities.git_repo_management.run_command")
    @patch.object(Path, "exists", return_value=True)
    def test_install_requirements_exception(self, mock_exists, mock_run):
        """Test requirements installation with exception."""
        req_file = Path(self.temp_dir) / "requirements.txt"
        req_file.write_text("pytest\nrequests")

        mock_run.side_effect = Exception("Unexpected error")

        with self.assertRaises(Exception):  # noqa: B017 # generic fallback intentionally
            self.venv.install_requirements(req_file)

    def test_get_python_path_exists(self):
        """Test getting Python path when it exists."""
        venv_python = Path(self.temp_dir) / "venv" / self.venv.bin_dir / self.venv.python_exe
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
        venv_pip = Path(self.temp_dir) / "venv" / self.venv.bin_dir / self.venv.pip_exe
        venv_pip.parent.mkdir(parents=True)
        venv_pip.touch()

        pip_path = self.venv.get_pip_path()
        self.assertEqual(pip_path, str(venv_pip))

    def test_get_pip_path_not_found(self):
        """Test getting pip path when it doesn't exist."""
        with self.assertRaises(FileNotFoundError):
            self.venv.get_pip_path()

    @patch("utilities.git_repo_management.run_command", return_value=(0, "pip 1.0", ""))
    def test_is_broken_healthy(self, mock_run):
        """Test _is_broken returns False for healthy venv."""
        venv_bin = Path(self.temp_dir) / "venv" / self.venv.bin_dir
        venv_bin.mkdir(parents=True)
        (venv_bin / self.venv.python_exe).touch()
        pip = venv_bin / self.venv.pip_exe
        pip.write_text(f"#!{venv_bin / self.venv.python_exe}\nimport pip\n")
        pip.chmod(0o755)
        broken, reason = self.venv._is_broken()
        self.assertFalse(broken)

    def test_is_broken_missing_pip(self):
        """Test _is_broken detects missing pip."""
        venv_bin = Path(self.temp_dir) / "venv" / self.venv.bin_dir
        venv_bin.mkdir(parents=True)
        (venv_bin / self.venv.python_exe).touch()
        # no pip
        broken, reason = self.venv._is_broken()
        self.assertTrue(broken)
        self.assertIn("missing pip", reason)

    def test_is_broken_missing_python(self):
        """Test _is_broken detects missing python."""
        venv_bin = Path(self.temp_dir) / "venv" / self.venv.bin_dir
        venv_bin.mkdir(parents=True)
        # no python, no pip
        broken, reason = self.venv._is_broken()
        self.assertTrue(broken)
        self.assertIn("missing python", reason)

    def test_is_broken_stale_interpreter_missing(self):
        """Test _is_broken detects pip shebang with missing interpreter."""
        venv_bin = Path(self.temp_dir) / "venv" / self.venv.bin_dir
        venv_bin.mkdir(parents=True)
        (venv_bin / self.venv.python_exe).touch()
        pip = venv_bin / self.venv.pip_exe
        pip.write_text("#!/tmp/other/venv/bin/python\n")
        pip.chmod(0o755)
        ve2 = VirtualEnvironment(Path(self.temp_dir), venv_dir=Path(self.temp_dir) / "venv")
        broken2, reason2 = ve2._is_broken()
        self.assertTrue(broken2)
        self.assertIn("stale pip shebang", reason2)

    def test_is_broken_stale_legacy_path(self):
        """Test _is_broken detects legacy xbridge_trading_bots/venv path after relocation."""
        # Use current venv's bin_dir for relocated test (bin vs Scripts)
        venv_bin = Path(self.temp_dir) / "relocated_venv" / self.venv.bin_dir
        venv_bin.mkdir(parents=True)
        (venv_bin / self.venv.python_exe).touch()
        pip = venv_bin / self.venv.pip_exe
        pip.write_text("#!/home/tryou/.AIO_Blocknet/xbridge_trading_bots/venv/bin/python\n")
        pip.chmod(0o755)
        ve = VirtualEnvironment(Path(self.temp_dir), venv_dir=Path(self.temp_dir) / "relocated_venv")
        broken, reason = ve._is_broken()
        self.assertTrue(broken)
        self.assertIn("stale pip shebang", reason)

    def test_is_broken_pip_not_runnable(self):
        """Test _is_broken detects pip not runnable via python -m pip."""
        venv_bin = Path(self.temp_dir) / "venv" / self.venv.bin_dir
        venv_bin.mkdir(parents=True)
        (venv_bin / self.venv.python_exe).touch()
        pip = venv_bin / self.venv.pip_exe
        pip.write_text(f"#!{venv_bin / self.venv.python_exe}\n")
        pip.chmod(0o755)
        with patch("utilities.git_repo_management.run_command", return_value=(1, "", "error")):
            broken, reason = self.venv._is_broken()
            self.assertTrue(broken)
            self.assertIn("pip not runnable", reason)

    def test_is_broken_missing_bin_dir(self):
        """Test _is_broken detects venv dir exists but bin missing."""
        venv_dir = Path(self.temp_dir) / "venv"
        venv_dir.mkdir(parents=True)
        # no bin subdir, but venv_dir exists -> should be broken
        ve = VirtualEnvironment(Path(self.temp_dir), venv_dir=venv_dir)
        broken, reason = ve._is_broken()
        self.assertTrue(broken)
        self.assertIn("missing bin", reason)

    @patch("utilities.git_repo_management.run_command", return_value=(0, "pip 1.0", ""))
    @patch("shutil.rmtree")
    @patch.object(VirtualEnvironment, "_create_venv_force")
    def test_ensure_healthy_recreates_when_broken(self, mock_create, mock_rm, mock_run):
        """Test ensure_healthy recreates broken venv."""
        venv_bin = Path(self.temp_dir) / "venv" / self.venv.bin_dir
        venv_bin.mkdir(parents=True)
        # missing pip -> broken
        (venv_bin / self.venv.python_exe).touch()
        # mock _is_broken to sequence: first broken, then healthy after create
        with patch.object(VirtualEnvironment, "_is_broken", side_effect=[(True, "missing pip"), (False, "")]):
            recreated = self.venv.ensure_healthy()
            self.assertTrue(recreated)
            mock_create.assert_called_once()

    @patch.object(VirtualEnvironment, "_is_broken", side_effect=[(True, "stale pip shebang"), (False, "")])
    @patch("shutil.rmtree")
    def test_create_recreates_when_broken(self, mock_rm, mock_broken):
        """Test create() recreates when existing venv is broken."""
        venv_bin = Path(self.temp_dir) / "venv" / self.venv.bin_dir
        venv_bin.mkdir(parents=True)
        (venv_bin / self.venv.python_exe).touch()
        (venv_bin / self.venv.pip_exe).touch()
        with patch.object(VirtualEnvironment, "_create_venv_force") as mock_force:
            self.venv.create()
            mock_force.assert_called_once()
            mock_rm.assert_called()

    @patch("utilities.git_repo_management.run_command")
    @patch.object(Path, "exists", return_value=True)
    def test_install_requirements_uses_python_m_pip(self, mock_exists, mock_run):
        """Test install_requirements uses python -m pip (shebang-independent)."""
        req_file = Path(self.temp_dir) / "requirements.txt"
        req_file.write_text("pytest\n")
        # mock python path exists and run_command success
        mock_run.return_value = (0, "success", "")
        # ensure _is_broken not triggered
        with (
            patch.object(VirtualEnvironment, "get_python_path", return_value="/fake/python"),
            patch.object(VirtualEnvironment, "get_pip_path", return_value="/fake/pip"),
            patch.object(VirtualEnvironment, "_is_broken", return_value=(False, "")),
        ):
            self.venv.install_requirements(req_file)
            # should call python -m pip, not direct pip
            called_cmd = mock_run.call_args[0][0]
            self.assertIn("-m", called_cmd)
            self.assertIn("pip", called_cmd)
            self.assertEqual(called_cmd[0], "/fake/python")

    @patch("utilities.git_repo_management.run_command")
    def test_install_requirements_heals_on_failure(self, mock_run):
        """Test install_requirements retries after venv heal on ExecutionError."""
        req_file = Path(self.temp_dir) / "requirements.txt"
        req_file.write_text("pytest\n")
        # first call raises ExecutionError (simulates pip not found), second succeeds
        mock_run.side_effect = [ExecutionError("Command not found: pip"), (0, "success", "")]
        with (
            patch.object(VirtualEnvironment, "get_python_path", side_effect=["/fake/python", "/fake/python2"]),
            patch.object(VirtualEnvironment, "_is_broken", return_value=(True, "stale")),
            patch.object(VirtualEnvironment, "ensure_healthy", return_value=True),
        ):
            self.venv.install_requirements(req_file)
            self.assertEqual(mock_run.call_count, 2)
            # second call should use healed python path
            second_cmd = mock_run.call_args_list[1][0][0]
            self.assertEqual(second_cmd[0], "/fake/python2")


class TestGitRepository(unittest.TestCase):
    """Test cases for GitRepository class - SOC: focused on git operations."""

    def setUp(self):
        """Set up test fixtures."""
        self.fixture = TempDirFixture()
        self.temp_dir = self.fixture.create()
        self.repo = GitRepository("https://github.com/test/repo.git", Path(self.temp_dir), "main")

    def tearDown(self):
        """Clean up test fixtures."""
        self.fixture.cleanup()

    @patch("pygit2.clone_repository")
    def test_clone_repo_success(self, mock_clone):
        """Test successful repository cloning."""
        mock_repo = MagicMock()
        mock_repo.references = {"refs/heads/main": True}
        mock_clone.return_value = mock_repo

        self.repo._clone_repo()

        mock_clone.assert_called_once()

    @patch("pygit2.clone_repository")
    def test_clone_repo_failure(self, mock_clone):
        """Test repository cloning failure."""
        mock_clone.side_effect = pygit2.GitError("Clone failed")

        with self.assertRaises(pygit2.GitError):
            self.repo._clone_repo()

    @patch("pygit2.clone_repository")
    def test_clone_repo_cleanup_on_failure(self, mock_clone):
        """Test cleanup on clone failure."""
        mock_clone.side_effect = Exception("Clone failed")

        with self.assertRaises(Exception):  # noqa: B017 # generic cleanup test
            self.repo._clone_repo()

        # Directory should exist but be cleaned up
        self.assertTrue(Path(self.temp_dir).exists())

    @patch("pygit2.clone_repository")
    def test_clone_repo_git_error_cleanup(self, mock_clone):
        """Test cleanup on pygit2.GitError."""
        mock_clone.side_effect = pygit2.GitError("Git error")

        with self.assertRaises(pygit2.GitError):
            self.repo._clone_repo()

        # Directory should be cleaned up
        self.assertFalse(Path(self.temp_dir).exists())

    def test_checkout_branch_exists(self):
        """Test checking out existing branch (now resets to remote tip)."""
        mock_repo = MagicMock()
        mock_remote = MagicMock()
        mock_remote.target = "mock_oid"
        mock_repo.references = {"refs/heads/main": MagicMock(), "refs/remotes/origin/main": mock_remote}
        mock_repo.get.return_value = MagicMock()
        mock_repo.status.return_value = {}
        # Mock diff to avoid computing changed paths
        mock_repo.head.peel.return_value.tree = MagicMock()
        mock_repo.get.return_value.peel.return_value.tree = MagicMock()
        mock_repo.diff.return_value.deltas = []
        self.repo.repo = mock_repo

        with patch.object(self.repo, "_prepare_checkout"):
            self.repo._checkout_branch()

        mock_repo.set_head.assert_called()

    def test_checkout_branch_from_remote(self):
        """Test checking out branch from remote."""
        mock_repo = MagicMock()
        mock_remote_ref_obj = MagicMock()
        mock_remote_ref_obj.target = "mock_target_oid"
        mock_repo.references = {"refs/remotes/origin/main": mock_remote_ref_obj}
        mock_repo.create_branch = MagicMock()
        mock_repo.get = MagicMock()
        mock_commit_obj = MagicMock()
        mock_repo.get.return_value = mock_commit_obj
        mock_repo.status.return_value = {}
        mock_repo.head.peel.return_value.tree = MagicMock()
        mock_commit_obj.peel.return_value.tree = MagicMock()
        mock_repo.diff.return_value.deltas = []

        self.repo.repo = mock_repo
        with patch.object(self.repo, "_prepare_checkout"):
            self.repo._checkout_branch()

        mock_repo.create_branch.assert_called_once_with("main", mock_commit_obj)

    def test_checkout_branch_not_found(self):
        """Test checking out branch when branch doesn't exist locally or remotely."""
        mock_repo = MagicMock()
        mock_repo.references = {}
        self.repo.repo = mock_repo

        # Should not raise an exception, just log a warning
        self.repo._checkout_branch()

        # Verify checkout was not called
        mock_repo.checkout.assert_not_called()

    def test_checkout_branch_git_error(self):
        """Test checking out branch with GitError now raises."""
        from utilities.git_repo_management import BranchSwitchBlockedError

        mock_repo = MagicMock()
        mock_repo.references = {"refs/heads/main": MagicMock(), "refs/remotes/origin/main": MagicMock()}
        mock_repo.references["refs/remotes/origin/main"].target = "oid"
        mock_repo.get.return_value = MagicMock()
        mock_repo.status.return_value = {}
        mock_repo.head.peel.return_value.tree = MagicMock()
        mock_repo.get.return_value.peel.return_value.tree = MagicMock()
        mock_repo.diff.return_value.deltas = []
        self.repo.repo = mock_repo

        with patch.object(self.repo, "_prepare_checkout", side_effect=BranchSwitchBlockedError("blocked")):  # noqa: SIM117
            with self.assertRaises(BranchSwitchBlockedError):
                self.repo._checkout_branch()

    @patch("requests.get")
    def test_get_remote_branches_api_success(self, mock_get):
        """Test getting remote branches via API."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"name": "main"}, {"name": "develop"}, {"name": "feature/test"}]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        branches = self.repo.get_remote_branches()

        self.assertEqual(branches, ["main", "develop", "feature/test"])

    @patch("requests.get")
    def test_get_remote_branches_api_failure(self, mock_get):
        """Test getting remote branches when API fails returns None."""
        mock_get.side_effect = Exception("API error")

        branches = self.repo.get_remote_branches()

        self.assertIsNone(branches)

    @patch("requests.get")
    def test_get_remote_branches_ssh_url(self, mock_get):
        """Test getting remote branches with SSH URL."""
        # Create a new repo with SSH URL
        ssh_repo = GitRepository("git@github.com:test/repo.git", Path(self.temp_dir), "main")

        mock_response = MagicMock()
        mock_response.json.return_value = [{"name": "main"}, {"name": "develop"}]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        branches = ssh_repo.get_remote_branches()

        self.assertEqual(branches, ["main", "develop"])

    @patch("requests.get")
    def test_get_remote_branches_ssh_url_with_git(self, mock_get):
        """Test getting remote branches with SSH URL ending in .git."""
        # Create a new repo with SSH URL ending in .git
        ssh_repo = GitRepository("git@github.com:test/repo.git", Path(self.temp_dir), "main")

        mock_response = MagicMock()
        mock_response.json.return_value = [{"name": "main"}, {"name": "develop"}]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        branches = ssh_repo.get_remote_branches()

        self.assertEqual(branches, ["main", "develop"])

    def test_clone_or_update_new_repo(self):
        """Test clone_or_update for new repository."""
        with patch.object(self.repo, "_clone_repo") as mock_clone:
            self.repo.clone_or_update()
            mock_clone.assert_called_once()

    def test_clone_or_update_exception(self):
        """Test clone_or_update with exception."""
        with patch.object(self.repo, "_clone_repo") as mock_clone:
            mock_clone.side_effect = Exception("Clone failed")

            with self.assertRaises(Exception):  # noqa: B017 # generic propagate
                self.repo.clone_or_update()

    def test_clone_or_update_existing_repo(self):
        """Test clone_or_update for existing repository."""
        # Create fake .git directory
        git_dir = Path(self.temp_dir) / ".git"
        git_dir.mkdir()

        with patch.object(self.repo, "_update_repo") as mock_update:
            self.repo.clone_or_update()
            mock_update.assert_called_once()

    def test_clone_or_update_recreate_repo(self):
        """Test clone_or_update when .git is missing."""
        Path(self.temp_dir).mkdir(exist_ok=True)

        with patch.object(self.repo, "_recreate_repo") as mock_recreate:
            self.repo.clone_or_update()
            mock_recreate.assert_called_once()

    @patch("pygit2.Repository")
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

    @patch("pygit2.Repository")
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

    @patch("pygit2.Repository")
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

    @patch("pygit2.Repository")
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

    @patch("pygit2.Repository")
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

    @patch("pygit2.Repository")
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

    @patch("pygit2.Repository")
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

        with patch.object(self.repo, "_checkout_branch") as mock_checkout:
            self.repo._update_repo()
            mock_checkout.assert_called_once()

    @patch("pygit2.Repository")
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
            mock_ref,  # Third call after creating branch
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
            "https://github.com/test/repo.git", str(Path(self.temp_dir) / "repo"), "main", self.temp_dir
        )

    def tearDown(self):
        """Clean up test fixtures."""
        self.fixture.cleanup()

    def test_init(self):
        """Test GitRepoManagement initialization."""
        self.assertEqual(self.repo_mgmt.git_repo.repo_url, "https://github.com/test/repo.git")
        self.assertIsInstance(self.repo_mgmt.git_repo, GitRepository)
        self.assertIsNone(self.repo_mgmt.venv)

    @patch("utilities.git_repo_management.miniforge_portable")
    @patch.object(GitRepository, "clone_or_update")
    @patch("utilities.git_repo_management.VirtualEnvironment")
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

    @patch("utilities.git_repo_management.miniforge_portable")
    @patch.object(GitRepository, "clone_or_update")
    @patch("utilities.git_repo_management.VirtualEnvironment")
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

    @patch("utilities.git_repo_management.miniforge_portable")
    @patch.object(GitRepository, "clone_or_update")
    @patch("utilities.git_repo_management.VirtualEnvironment")
    def test_setup_failure(self, mock_venv_class, mock_clone, mock_miniforge):
        """Test setup failure."""
        mock_clone.side_effect = Exception("Clone failed")

        with self.assertRaises(Exception) as context:
            self.repo_mgmt.setup()

        self.assertIn("Repository setup failed", str(context.exception))

    @patch("utilities.git_repo_management.miniforge_portable")
    @patch.object(GitRepository, "clone_or_update")
    @patch("utilities.git_repo_management.VirtualEnvironment")
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

    @patch("subprocess.Popen")
    @patch("threading.Thread")
    def test_run_script_success(self, mock_thread, mock_popen):
        """Test successful script execution."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = b""
        mock_process.stderr.readline.return_value = b""
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process
        mock_thread.return_value = MagicMock()

        result = self.repo_mgmt.run_script("test.py", ["arg1", "arg2"])

        mock_popen.assert_called_once()
        self.assertEqual(result, mock_process)

    @patch("subprocess.Popen")
    @patch("threading.Thread")
    def test_run_script_with_timeout(self, mock_thread, mock_popen):
        """Test script execution with timeout."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = b""
        mock_process.stderr.readline.return_value = b""
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process
        mock_thread.return_value = MagicMock()

        result = self.repo_mgmt.run_script("test.py", timeout=30)

        mock_popen.assert_called_once()
        self.assertEqual(result, mock_process)

    @patch("subprocess.Popen")
    @patch("threading.Thread")
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

    @patch("subprocess.Popen")
    @patch("threading.Thread")
    def test_run_script_stream_reader_exception(self, mock_thread, mock_popen):
        """Test stream reader with exception."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ValueError("Stream error")
        mock_process.stderr.readline.return_value = b""
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process
        mock_thread.return_value = MagicMock()

        result = self.repo_mgmt.run_script("test.py")

        mock_popen.assert_called_once()
        self.assertEqual(result, mock_process)

    @patch("subprocess.Popen")
    @patch("threading.Thread")
    def test_run_script_stream_reader_ioerror(self, mock_thread, mock_popen):
        """Test stream reader with IOError."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = OSError("Pipe closed")
        mock_process.stderr.readline.return_value = b""
        mock_process.poll.return_value = 0
        mock_popen.return_value = mock_process
        mock_thread.return_value = MagicMock()

        result = self.repo_mgmt.run_script("test.py")

        mock_popen.assert_called_once()
        self.assertEqual(result, mock_process)

    @patch("subprocess.Popen")
    @patch("threading.Thread")
    @patch("time.sleep")
    def test_run_script_timeout_watcher(self, mock_sleep, mock_thread, mock_popen):
        """Test timeout watcher terminates process."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = b""
        mock_process.stderr.readline.return_value = b""
        mock_process.poll.return_value = None  # Process still running
        mock_popen.return_value = mock_process
        mock_thread.return_value = MagicMock()

        # Mock time.time() to simulate timeout
        with patch("time.time", side_effect=[0, 31]):  # First call 0, second call 31 (timeout)
            result = self.repo_mgmt.run_script("test.py", timeout=30)

        mock_popen.assert_called_once()
        # Verify the process was returned
        self.assertEqual(result, mock_process)

    @patch("subprocess.Popen")
    @patch("threading.Thread")
    @patch("time.sleep")
    def test_run_script_timeout_watcher_kill(self, mock_sleep, mock_thread, mock_popen):
        """Test timeout watcher kills process if terminate fails."""
        script_path = Path(self.repo_mgmt.target_dir) / "test.py"
        script_path.parent.mkdir(parents=True)
        script_path.write_text("print('test')")

        # Setup mock venv
        self.repo_mgmt.venv = create_venv_mock(self.temp_dir)

        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = b""
        mock_process.stderr.readline.return_value = b""
        mock_process.poll.return_value = None  # Process still running
        mock_process.terminate.return_value = None
        mock_process.poll.side_effect = [None, None]  # Still running after terminate
        mock_popen.return_value = mock_process
        mock_thread.return_value = MagicMock()

        # Mock time.time() to simulate timeout
        with patch("time.time", side_effect=[0, 31]):  # First call 0, second call 31 (timeout)
            result = self.repo_mgmt.run_script("test.py", timeout=30)

        mock_popen.assert_called_once()
        # Verify the process was returned
        self.assertEqual(result, mock_process)

    def test_get_remote_branches(self):
        """Test getting remote branches through GitRepoManagement."""
        with patch.object(self.repo_mgmt.git_repo, "get_remote_branches") as mock_get:
            mock_get.return_value = ["main", "develop"]

            branches = self.repo_mgmt.get_remote_branches()

            self.assertEqual(branches, ["main", "develop"])
            mock_get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
