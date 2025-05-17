import logging
import shutil
import sys
import venv
import subprocess
from pathlib import Path
from typing import List, Optional

import git  # GitPython package


class GitRepoManagement:
    """
    Manages a Git repository with an associated virtual environment.
    Enforces the use of the virtual environment for all operations.
    Uses GitPython instead of system Git commands.
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
        """Clone a new repository or update an existing one using GitPython."""
        if not self.target_dir.exists():
            self._clone_repo()
            return

        if not (self.target_dir / ".git").is_dir():
            self._recreate_repo()
            return

        # Repository exists, update it
        try:
            self.repo = git.Repo(self.target_dir)
            origin = self.repo.remotes.origin
            origin.fetch()

            # Check if branch exists locally
            try:
                self.repo.git.checkout(self.branch)
            except git.GitCommandError:
                # If branch doesn't exist locally but exists remotely, create it
                remote_branch = f"origin/{self.branch}"
                if remote_branch in [ref.name for ref in self.repo.refs]:
                    self.repo.git.checkout('-b', self.branch, remote_branch)
                else:
                    self._fail(f"Branch {self.branch} does not exist locally or remotely")

            # Pull updates
            origin.pull(ff_only=True)
            logging.info(f"Repository updated successfully")
        except git.GitCommandError as e:
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
        """Clone a fresh repository using GitPython."""
        logging.info(f"Cloning repository to {self.target_dir}")
        self.target_dir.mkdir(exist_ok=True, parents=True)
        try:
            self.repo = git.Repo.clone_from(
                self.repo_url,
                str(self.target_dir),
                branch=self.branch
            )
            logging.info(f"Repository cloned successfully")
        except git.GitCommandError as e:
            self._fail(f"Failed to clone repository: {e}")

    def _recreate_repo(self) -> None:
        """Remove and recreate the repository directory using GitPython."""
        logging.info(f"Recreating repository at {self.target_dir}")

        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)

        self.target_dir.mkdir(exist_ok=True, parents=True)
        try:
            self.repo = git.Repo.clone_from(
                self.repo_url,
                str(self.target_dir),
                branch=self.branch
            )
            logging.info(f"Repository recreated successfully")
        except git.GitCommandError as e:
            self._fail(f"Failed to recreate repository: {e}")

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
        """Fetch list of remote branch names using GitPython."""
        try:
            if not self.repo:
                # Initialize repo if not already done
                if (self.target_dir / ".git").is_dir():
                    self.repo = git.Repo(self.target_dir)
                else:
                    # Create a temporary repo object to get remote info
                    temp_repo = git.Repo.init(self.target_dir, mkdir=True)
                    temp_repo.create_remote("origin", self.repo_url)
                    self.repo = temp_repo

            # Fetch remote refs
            remote_refs = self.repo.remote().refs

            # Extract branch names (remove 'origin/' prefix)
            branches = [ref.name.split('/')[-1] for ref in remote_refs
                        if ref.name.startswith('origin/') and not ref.name.endswith('HEAD')]

            return branches
        except git.GitCommandError as e:
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