import logging
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import List, Optional

import pygit2


class GitRepoManagement:
    """
    Manages a Git repository with an associated virtual environment.
    Enforces the use of the virtual environment for all operations.
    Uses pygit2 instead of GitPython for Git operations.
    """

    def __init__(self, repo_url: str, target_dir: str, branch: str = "main"):
        """
        Initialize repository management.

        Args:
            repo_url: URL of the Git repository
            target_dir: Local directory where the repository will be cloned
            branch: Git branch to use (default: "main")
        """
        self.repo_url = repo_url
        self.target_dir = Path(target_dir).resolve()  # Consistently use Path objects
        self.branch = branch
        self.venv_dir = self.target_dir / "venv"
        self.repo = None  # Will hold the Git repository object

        # Define platform-specific paths
        self.bin_dir = "Scripts" if sys.platform == "win32" else "bin"
        self.venv_bin_path = self.venv_dir / self.bin_dir

    def setup(self) -> bool:
        """
        Clone/update the repository and set up the virtual environment.

        Returns:
            True if setup completed successfully
        """
        logging.info(f"Setting up repository: {self.repo_url} in {self.target_dir}")

        self.clone_or_update_repo()
        self.create_virtualenv()
        self.install_requirements()

        logging.info(f"Repository setup complete")
        return True

    def clone_or_update_repo(self) -> None:
        """Clone a new repository or update an existing one using pygit2."""
        if not self.target_dir.exists():
            self._clone_repo()
            return

        if not (self.target_dir / ".git").is_dir():
            self._recreate_repo()
            return

        # Repository exists, update it
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

    def create_virtualenv(self) -> None:
        """Create a virtual environment if it doesn't exist."""
        if self.venv_bin_path.exists():
            logging.info(f"Virtual environment already exists")
            return

        logging.info(f"Creating virtual environment at {self.venv_dir}")
        try:
            self.venv_dir.parent.mkdir(exist_ok=True, parents=True)
            venv.create(self.venv_dir, with_pip=True, system_site_packages=False)

            if not self.venv_bin_path.exists():
                self._fail(f"Virtual environment creation failed")

            logging.info(f"Virtual environment created successfully")
        except Exception as e:
            self._fail(f"Failed to create virtual environment: {e}")

    def install_requirements(self) -> None:
        """Install packages from requirements.txt using the virtual environment's pip."""
        requirements_path = self.target_dir / "requirements.txt"

        if not requirements_path.exists():
            logging.info("No requirements.txt found. Skipping installation.")
            return

        logging.info("Installing requirements from requirements.txt")

        pip_path = self._get_venv_executable("pip") or self._get_venv_executable("pip3")
        if not pip_path:
            self._fail("Pip not found in virtual environment")

        python_path = self._get_venv_python()
        self._run_command([python_path, "-m", "pip", "install", "-r", str(requirements_path)])
        logging.info("Requirements installed successfully")

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
            self._fail(f"Script not found: {abs_script_path}")

        python_path = self._get_venv_python()
        cmd = [str(python_path), str(abs_script_path)] + script_args

        logging.info(f"Running script: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            cwd=self.target_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return process

    def _clone_repo(self) -> None:
        """Clone a fresh repository using pygit2."""
        logging.info(f"Cloning repository to {self.target_dir}")
        self.target_dir.mkdir(exist_ok=True, parents=True)
        try:
            # Set up callbacks (empty for now, but could be used for auth)
            callbacks = pygit2.RemoteCallbacks()

            # Perform the clone with minimal parameters for cross-platform compatibility
            self.repo = pygit2.clone_repository(
                self.repo_url,
                str(self.target_dir),
                callbacks=callbacks
            )

            # After clone, checkout the specified branch if it's not the default branch
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

            logging.info(f"Repository cloned successfully")
        except pygit2.GitError as e:
            self._fail(f"Failed to clone repository: {e}")

    def _recreate_repo(self) -> None:
        """Remove and recreate the repository directory using pygit2."""
        logging.info(f"Recreating repository at {self.target_dir}")

        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)

        self.target_dir.mkdir(exist_ok=True, parents=True)

        # Use the existing clone method to keep the implementation consistent
        self._clone_repo()

    def _get_venv_executable(self, name: str) -> Optional[Path]:
        """Get path to an executable in the virtual environment."""
        if sys.platform == "win32" and not name.endswith(".exe"):
            name += ".exe"

        exe_path = self.venv_bin_path / name
        return exe_path if exe_path.exists() else None

    def _get_venv_python(self) -> Path:
        """Get path to the Python interpreter in the virtual environment."""
        python_exe = self._get_venv_executable("python") or self._get_venv_executable("python3")
        if not python_exe:
            self._fail("Python interpreter not found in virtual environment")
        return python_exe

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

    def _run_command_with_output(self, cmd_list: List[str], cwd: Optional[Path] = None) -> str:
        """Run a command and return its output."""
        try:
            result = subprocess.run(
                cmd_list,
                check=True,
                cwd=cwd or self.target_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return result.stdout
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            self._fail(f"Command failed: {e}")
            return ""  # Will never reach here due to _fail raising SystemExit

    def get_remote_branches(self) -> List[str]:
        """Fetch list of remote branch names using pygit2."""
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
