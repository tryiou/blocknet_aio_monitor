import logging
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import List, Optional

import pygit2


class SystemPaths:
    """Manages system paths, particularly for PyInstaller environments."""

    @staticmethod
    def python_path():
        """Get the path to the Python interpreter."""
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller 
            exe = 'python.exe' if sys.platform == "win32" else 'python'
            path = os.path.join(sys._MEIPASS, 'venv', 'bin', exe)
        else:
            # Running as normal Python script
            path = sys.executable
        logging.info(f"System Python path: {path}")
        return path

    @staticmethod
    def pip_path():
        """Get the path to pip."""
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller 
            exe = 'pip.exe' if sys.platform == "win32" else 'pip'
            path = os.path.join(sys._MEIPASS, 'venv', 'bin', exe)
        else:
            path = shutil.which('pip')
        logging.info(f"System pip path: {path}")
        return path


class VirtualEnvironment:
    """Manages virtual environment creation and operations."""

    def __init__(self, target_dir: Path):
        self.target_dir = target_dir
        self.venv_dir = target_dir / "venv"
        self.is_windows = sys.platform == "win32"

        self.bin_dir = "Scripts" if self.is_windows else "bin"
        self.python_exe = "python.exe" if self.is_windows else "python"
        self.pip_exe = "pip.exe" if self.is_windows else "pip"
        self.venv_bin_path = self.venv_dir / self.bin_dir

    def create(self) -> None:
        """Create a virtual environment if it doesn't exist, using a specific Python interpreter."""
        if self.venv_bin_path.exists():
            logging.info("Virtual environment already exists")
            return

        logging.info(f"Creating virtual environment at {self.venv_dir}")
        try:
            # Make sure parent directory exists
            self.venv_dir.parent.mkdir(exist_ok=True, parents=True)

            # Use the bundled Python interpreter to create the venv
            subprocess.check_call([SystemPaths.python_path(), "-m", "venv", str(self.venv_dir)])

            # Verify creation
            if not self.venv_bin_path.exists():
                self._fail("Virtual environment creation failed: missing bin directory")

            # Optionally, upgrade pip if needed
            # e.g., subprocess.check_call([self.venv_bin_path / "pip", "install", "--upgrade", "pip"])

            logging.info("Virtual environment created successfully")
        except Exception as e:
            self._fail(f"Failed to create virtual environment: {e}")

    # def create_1(self) -> None:
    #     """Create a virtual environment if it doesn't exist."""
    #     if self.venv_bin_path.exists():
    #         logging.info(f"Virtual environment already exists")
    #         return

    #     logging.info(f"Creating virtual environment at {self.venv_dir}")
    #     try:
    #         # Make sure parent directory exists
    #         self.venv_dir.parent.mkdir(exist_ok=True, parents=True)
    #         bundled_python = SystemPaths.python_path()
    #         bundled_pip = SystemPaths.pip_path()
    #             # Standard venv creation
    #         venv.create(self.venv_dir, with_pip=True, system_site_packages=False)

    #         if not self.venv_bin_path.exists():
    #             self._fail(f"Virtual environment creation failed")

    #         logging.info(f"Virtual environment created successfully")
    #     except Exception as e:
    #         self._fail(f"Failed to create virtual environment: {e}")

    def _create_pyinstaller_venv(self) -> None:
        """Create a virtual environment when running as PyInstaller bundle."""
        logging.info("Creating venv in PyInstaller context")
        os.makedirs(self.venv_dir, exist_ok=True)
        os.makedirs(self.venv_bin_path, exist_ok=True)

        # Create symlinks/copies to bundled Python and pip
        bundled_python = SystemPaths.python_path()
        bundled_pip = SystemPaths.pip_path()

        if os.path.exists(bundled_python):
            exe = 'python.exe' if sys.platform == "win32" else 'python'
            self._create_executable_link(bundled_python, exe)

        if os.path.exists(bundled_pip):
            exe = 'pip.exe' if sys.platform == "win32" else 'pip'
            self._create_executable_link(bundled_pip, exe)

        # Create a simple activation script
        self._create_activation_script(bundled_python)

    def _create_executable_link(self, source_path: str, exe_name: str) -> None:
        """Create link to executable (symlink on Unix, copy on Windows)."""
        if self.is_windows:
            dest_path = os.path.join(self.venv_bin_path, f"{exe_name}")
            if not os.path.exists(dest_path):
                try:
                    shutil.copy2(source_path, dest_path)
                    logging.info(f"Copied bundled {exe_name} to: {dest_path}")
                except Exception as e:
                    logging.warning(f"Failed to copy {exe_name}: {e}")
        else:
            dest_path = os.path.join(self.venv_bin_path, exe_name)
            if not os.path.exists(dest_path):
                try:
                    os.symlink(source_path, dest_path)
                    logging.info(f"Created symlink to bundled {exe_name}: {dest_path}")
                except Exception as e:
                    logging.warning(f"Failed to create symlink to {exe_name}: {e}")

    def _create_activation_script(self, python_path: str) -> None:
        """Create activation script for the virtual environment."""
        activate_path = self.venv_bin_path / ("activate.bat" if self.is_windows else "activate")
        with open(activate_path, "w") as f:
            if self.is_windows:
                f.write(f"@echo off\nSET PATH={os.path.dirname(python_path)};%PATH%\n")
            else:
                f.write(f"#!/bin/bash\nexport PATH={os.path.dirname(python_path)}:$PATH\n")

        if not self.is_windows:
            os.chmod(activate_path, 0o755)  # Make executable on Unix

    def install_requirements(self, requirements_path: Path) -> None:
        """Install packages from requirements.txt."""
        if not requirements_path.exists():
            logging.info("No requirements.txt found. Skipping installation.")
            return

        logging.info("Installing requirements from requirements.txt")

        pip_path = self.get_pip_path()
        python_path = self.get_python_path()

        try:
            if os.path.exists(pip_path):
                self._run_command([pip_path, "install", "-r", str(requirements_path)])
            else:
                self._run_command([python_path, "-m", "pip", "install", "-r", str(requirements_path)])
            logging.info("Requirements installed successfully")
        except Exception as e:
            self._fail(f"Failed to install requirements: {e}")

    def get_python_path(self) -> str:
        """Get the path to Python executable in the virtual environment."""
        venv_python_path = self.venv_bin_path / self.python_exe
        if venv_python_path.exists():
            logging.info(f"Using virtual environment Python: {venv_python_path}")
            return str(venv_python_path)
        else:
            self._fail(f"Virtual environment Python not found at {venv_python_path}")

    def get_pip_path(self) -> str:
        """Get the path to pip executable in the virtual environment."""
        pip_path = self.venv_bin_path / self.pip_exe
        if pip_path.exists():
            logging.info(f"Using virtual environment pip: {pip_path}")
            return str(pip_path)
        self._fail(f"Virtual environment pip not found in {self.venv_bin_path}")

    def _run_command(self, cmd_list: List[str], cwd: Optional[Path] = None) -> None:
        """Run a command and handle errors."""
        try:
            subprocess.run(
                cmd_list,
                check=True,
                cwd=cwd or self.target_dir
            )
        except subprocess.CalledProcessError as e:
            self._fail(f"Command failed: {e}")
        except FileNotFoundError as e:
            self._fail(f"Command not found: {e}")

    def _fail(self, message: str) -> None:
        """Log an error message and exit."""
        logging.error(message)
        sys.exit(1)


class GitRepository:
    """Manages Git operations using pygit2."""

    def __init__(self, repo_url: str, target_dir: Path, branch: str = "main"):
        self.repo_url = repo_url
        self.target_dir = target_dir
        self.branch = branch
        self.repo = None

    def clone_or_update(self) -> None:
        """Clone a new repository or update an existing one."""
        if not self.target_dir.exists():
            self._clone_repo()
            return

        if not (self.target_dir / ".git").is_dir():
            self._recreate_repo()
            return

        self._update_repo()

    def _clone_repo(self) -> None:
        """Clone a fresh repository."""
        logging.info(f"Cloning repository to {self.target_dir}")
        self.target_dir.mkdir(exist_ok=True, parents=True)
        try:
            callbacks = pygit2.RemoteCallbacks()
            self.repo = pygit2.clone_repository(
                self.repo_url,
                str(self.target_dir),
                callbacks=callbacks
            )

            self._checkout_branch()
            logging.info(f"Repository cloned successfully")
        except pygit2.GitError as e:
            self._fail(f"Failed to clone repository: {e}")

    def _checkout_branch(self) -> None:
        """Checkout the specified branch."""
        try:
            branch_ref = f"refs/heads/{self.branch}"
            if branch_ref in self.repo.references:
                self.repo.checkout(branch_ref)
            else:
                # Try to create and checkout the branch from origin
                remote_ref = f"refs/remotes/origin/{self.branch}"
                if remote_ref in self.repo.references:
                    remote_branch = self.repo.references[remote_ref]
                    self.repo.create_branch(self.branch, self.repo.get(remote_branch.target))
                    self.repo.checkout(branch_ref)
        except pygit2.GitError as e:
            logging.warning(f"Could not checkout branch {self.branch}: {e}")

    def _recreate_repo(self) -> None:
        """Remove and recreate the repository directory."""
        logging.info(f"Recreating repository at {self.target_dir}")

        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)

        self.target_dir.mkdir(exist_ok=True, parents=True)
        self._clone_repo()

    def _update_repo(self) -> None:
        """Update an existing repository."""
        try:
            self.repo = pygit2.Repository(str(self.target_dir))

            # Fetch updates from remote
            remote_name = "origin"
            remote = self.repo.remotes[remote_name]
            remote.fetch()

            # Get the remote reference for the branch
            remote_branch_ref = f"refs/remotes/{remote_name}/{self.branch}"
            remote_branch = None
            try:
                remote_branch = self.repo.references[remote_branch_ref]
            except KeyError:
                self._fail(f"Branch {self.branch} does not exist remotely")

            # Check if branch exists locally
            local_branch_ref = f"refs/heads/{self.branch}"
            try:
                local_branch = self.repo.references[local_branch_ref]
                # Checkout the branch
                self.repo.checkout(f"refs/heads/{self.branch}")
            except KeyError:
                # If branch doesn't exist locally but exists remotely, create it
                if remote_branch:
                    # Create local branch pointing to the same commit as remote branch
                    self.repo.create_branch(self.branch, self.repo.get(remote_branch.target))
                    self.repo.checkout(f"refs/heads/{self.branch}")
                else:
                    self._fail(f"Branch {self.branch} does not exist locally or remotely")

            # Get the latest commit from remote branch
            remote_commit_id = remote_branch.target
            local_branch = self.repo.references[local_branch_ref]

            # Only merge if the branches have diverged
            if local_branch.target != remote_commit_id:
                # Get the target commits
                remote_commit = self.repo.get(remote_commit_id)

                # Check if fast-forward is possible
                if self.repo.merge_base(local_branch.target, remote_commit_id) == local_branch.target:
                    # Fast-forward update
                    local_branch.set_target(remote_commit_id)
                    # Reset the working directory to match
                    self.repo.checkout_tree(remote_commit)
                    self.repo.head.set_target(remote_commit_id)
                else:
                    # Not a fast-forward merge
                    self._fail("Cannot perform fast-forward merge. Repository may have local changes.")

            logging.info(f"Repository updated successfully")
        except pygit2.GitError as e:
            self._fail(f"Failed to update repository: {e}")

    def get_remote_branches(self) -> List[str]:
        """Fetch list of remote branch names."""
        try:
            # If repo doesn't exist yet, initialize and add remote
            if not (self.target_dir / ".git").is_dir():
                self.target_dir.mkdir(exist_ok=True, parents=True)
                self.repo = pygit2.init_repository(str(self.target_dir))
                # Add the remote
                self.repo.remotes.create("origin", self.repo_url)
            elif not self.repo:
                # Repository exists, but repo object isn't initialized
                self.repo = pygit2.Repository(str(self.target_dir))

            # Fetch remote refs
            remote = self.repo.remotes["origin"]
            remote.fetch()

            # Extract branch names (remove 'origin/' prefix)
            branches = []
            prefix = "refs/remotes/origin/"
            for ref_name in self.repo.references:
                if ref_name.startswith(prefix) and not ref_name.endswith('HEAD'):
                    branches.append(ref_name[len(prefix):])

            return branches
        except pygit2.GitError as e:
            self._fail(f"Failed to fetch remote branches: {e}")

    def _fail(self, message: str) -> None:
        """Log an error message and exit."""
        logging.error(message)
        sys.exit(1)


class GitRepoManagement:
    """
    Manages a Git repository with an associated virtual environment.
    Enforces the use of the virtual environment for all operations.
    """

    def __init__(self, repo_url: str, target_dir: str, branch: str = "main"):
        """
        Initialize repository management.

        Args:
            repo_url: URL of the Git repository
            target_dir: Local directory where the repository will be cloned
            branch: Git branch to use (default: "main")
        """
        self.target_dir = Path(target_dir).resolve()
        self.git_repo = GitRepository(repo_url, self.target_dir, branch)
        self.venv = VirtualEnvironment(self.target_dir)

    def setup(self) -> bool:
        """
        Clone/update the repository and set up the virtual environment.

        Returns:
            True if setup completed successfully
        """
        logging.info(f"Setting up repository in {self.target_dir}")

        self.git_repo.clone_or_update()
        self.venv.create()
        self.venv.install_requirements(self.target_dir / "requirements.txt")

        logging.info(f"Repository setup complete")
        return True

    def run_script(self, script_path: str, script_args: Optional[List[str]] = None) -> Optional[subprocess.Popen]:
        """
        Execute a Python script using the virtual environment's Python interpreter.

        Args:
            script_path: Path to the script relative to the target directory
            script_args: List of arguments to pass to the script

        Returns:
            subprocess.Popen object representing the running script
        """
        if script_args is None:
            script_args = []

        abs_script_path = (self.target_dir / script_path).resolve()
        if not abs_script_path.exists():
            logging.error(f"Script not found: {abs_script_path}")
            sys.exit(1)

        # Use the Python from the virtual environment
        python_path = self.venv.get_python_path()
        cmd = [str(python_path), str(abs_script_path)] + script_args

        logging.info(f"Running script with venv Python: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            cwd=self.target_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Start a thread to read and print output                                                                                                                                                                                
        def read_output():
            for line in process.stdout:
                print(line.strip())
            for line in process.stderr:
                print(line.strip())

        threading.Thread(target=read_output, daemon=True).start()

        return process

    def get_remote_branches(self) -> List[str]:
        """Fetch list of remote branch names."""
        return self.git_repo.get_remote_branches()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Example usage
    git_repo_url = "https://github.com/tryiou/xbridge_trading_bots"
    local_target_dir = "xbridge_trading_bots"
    local_branch = "main"

    manager = GitRepoManagement(git_repo_url, local_target_dir, local_branch)
    manager.setup()

    # Example of running a script after setup
    manager.run_script("gui_pingpong.py")
