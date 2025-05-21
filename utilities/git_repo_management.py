import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

import requests

from utilities import global_variables

try:
    import utilities.miniforge_portable as miniforge_portable
except ModuleNotFoundError:
    import miniforge_portable

import pygit2


class ExecutionError(Exception):
    """Custom exception for execution failures."""
    pass


def run_command(cmd_list: List[str], cwd: Optional[Path] = None,
                timeout: int = 300) -> Tuple[int, str, str]:
    """
    Run a command and return its output.

    Args:
        cmd_list: Command and arguments as a list
        cwd: Working directory
        timeout: Command timeout in seconds

    Returns:
        Tuple of (return_code, stdout, stderr)

    Raises:
        ExecutionError: On command execution failure
    """
    try:
        process = subprocess.run(
            cmd_list,
            check=False,  # Don't raise exception, we'll handle the return code
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        return process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired:
        raise ExecutionError(f"Command timed out after {timeout} seconds: {' '.join(cmd_list)}")
    except FileNotFoundError:
        raise ExecutionError(f"Command not found: {cmd_list[0]}")
    except Exception as e:
        raise ExecutionError(f"Command execution failed: {e}")


class VirtualEnvironment:
    def __init__(self, target_dir: Path, portable_python_path: str = None):
        self.target_dir = target_dir
        self.venv_dir = target_dir / "venv"
        self.portable_python_path = portable_python_path
        self.is_windows = sys.platform == "win32"
        self.bin_dir = "Scripts" if self.is_windows else "bin"
        self.python_exe = "python.exe" if self.is_windows else "python"
        self.pip_exe = "pip.exe" if self.is_windows else "pip"
        self.venv_bin_path = self.venv_dir / self.bin_dir
        logging.info(f"venv_bin_path: {self.venv_bin_path}")

    def create(self) -> None:
        """Create a virtual environment if it doesn't exist, using a specific Python interpreter."""
        if self.venv_bin_path.exists():
            logging.info("Virtual environment already exists")
            return

        logging.info(f"Creating virtual environment at {self.venv_dir}")
        try:
            # Make sure parent directory exists
            self.venv_dir.parent.mkdir(exist_ok=True, parents=True)

            # Use portable Python if provided, else system Python
            python_path = self.portable_python_path
            returncode, stdout, stderr = run_command(
                [python_path, "-m", "venv", str(self.venv_dir)]
            )

            if returncode != 0:
                raise ExecutionError(f"Virtual environment creation failed: {stderr}")

            # Verify creation
            if not self.venv_bin_path.exists():
                raise ExecutionError("Virtual environment creation failed: missing bin directory")

            logging.info("Virtual environment created successfully")
        except Exception as e:
            logging.error(f"Failed to create virtual environment: {e}")
            raise

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
                cmd = [pip_path, "install", "-r", str(requirements_path)]
            else:
                cmd = [python_path, "-m", "pip", "install", "-r", str(requirements_path)]

            returncode, stdout, stderr = run_command(cmd, self.target_dir)

            if returncode != 0:
                raise ExecutionError(f"Failed to install requirements: {stderr}")

            logging.info("Requirements installed successfully")
        except Exception as e:
            logging.error(f"Failed to install requirements: {e}")
            raise

    def get_python_path(self) -> str:
        """Get the path to Python executable in the virtual environment."""
        venv_python_path = self.venv_bin_path / self.python_exe
        if venv_python_path.exists():
            logging.info(f"Using virtual environment Python: {venv_python_path}")
            return str(venv_python_path)
        else:
            raise FileNotFoundError(f"Virtual environment Python not found at {venv_python_path}")

    def get_pip_path(self) -> str:
        """Get the path to pip executable in the virtual environment."""
        pip_path = self.venv_bin_path / self.pip_exe
        if pip_path.exists():
            logging.info(f"Using virtual environment pip: {pip_path}")
            return str(pip_path)
        raise FileNotFoundError(f"Virtual environment pip not found in {self.venv_bin_path}")


class GitRepository:
    """Manages Git operations using pygit2."""

    def __init__(self, repo_url: str, target_dir: Path, branch: str = "main"):
        self.repo_url = repo_url
        self.target_dir = target_dir
        self.branch = branch
        self.repo = None
        # Default timeout for Git operations (in seconds)
        self.git_timeout = 300

    def clone_or_update(self) -> None:
        """Clone a new repository or update an existing one."""
        try:
            if not self.target_dir.exists():
                self._clone_repo()
                return

            if not (self.target_dir / ".git").is_dir():
                self._recreate_repo()
                return

            self._update_repo()
        except Exception as e:
            logging.error(f"Repository operation failed: {e}")
            raise

    def _clone_repo(self) -> None:
        """Clone a fresh repository."""
        logging.info(f"Cloning repository to {self.target_dir}")
        self.target_dir.mkdir(exist_ok=True, parents=True)
        try:
            callbacks = pygit2.RemoteCallbacks()

            # Set a timeout for the clone operation
            start_time = time.time()

            self.repo = pygit2.clone_repository(
                self.repo_url,
                str(self.target_dir),
                callbacks=callbacks
            )

            elapsed_time = time.time() - start_time
            logging.info(f"Clone completed in {elapsed_time:.2f} seconds")

            self._checkout_branch()
            logging.info(f"Repository cloned successfully")
        except pygit2.GitError as e:
            logging.error(f"Failed to clone repository: {e}")
            # Clean up partial clone if it exists
            if self.target_dir.exists():
                shutil.rmtree(self.target_dir)
            raise

    def _checkout_branch(self) -> None:
        """Checkout the specified branch."""
        try:
            branch_ref = f"refs/heads/{self.branch}"
            if branch_ref in self.repo.references:
                self.repo.checkout(branch_ref)
                logging.info(f"Checked out existing branch: {self.branch}")
                return

            # Try to create and checkout the branch from origin
            remote_ref = f"refs/remotes/origin/{self.branch}"
            if remote_ref in self.repo.references:
                remote_branch = self.repo.references[remote_ref]
                self.repo.create_branch(self.branch, self.repo.get(remote_branch.target))
                self.repo.checkout(branch_ref)
                logging.info(f"Created and checked out branch from remote: {self.branch}")
                return

            # If we get here, the branch doesn't exist locally or remotely
            logging.warning(f"Branch '{self.branch}' not found locally or remotely. Staying on current branch.")
        except pygit2.GitError as e:
            logging.warning(f"Could not checkout branch {self.branch}: {e}")

    def _recreate_repo(self) -> None:
        """Remove and recreate the repository directory."""
        logging.info(f"Recreating repository at {self.target_dir}")

        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)

        self.target_dir.mkdir(exist_ok=True, parents=True)
        self._clone_repo()

    def _update_repo(self) -> bool:
        """Update an existing repository using fetch + merge logic (like git pull)."""
        try:
            self.repo = pygit2.Repository(str(self.target_dir))
            logging.info("Opened existing repository")

            # Fetch updates from remote
            logging.info("Fetching updates from remote")
            remote_name = "origin"

            # Make sure remote exists
            try:
                remote = self.repo.remotes[remote_name]
            except KeyError:
                logging.warning(f"Remote '{remote_name}' not found. Adding it.")
                self.repo.remotes.create(remote_name, self.repo_url)
                remote = self.repo.remotes[remote_name]

            # Set fetch timeout
            start_time = time.time()
            remote.fetch()
            elapsed_time = time.time() - start_time
            logging.info(f"Fetch completed in {elapsed_time:.2f} seconds")

            # Get the remote branch reference
            remote_branch_ref = f"refs/remotes/{remote_name}/{self.branch}"
            remote_branch = self.repo.references.get(remote_branch_ref)
            if not remote_branch:
                logging.error(f"Remote branch '{self.branch}' not found in '{remote_name}'")
                return False

            # Get the local branch
            local_branch_ref = f"refs/heads/{self.branch}"
            local_branch = self.repo.references.get(local_branch_ref)

            # If local branch doesn't exist, create it
            if not local_branch:
                logging.info(f"Local branch '{self.branch}' not found. Creating it.")
                self.repo.create_branch(self.branch, self.repo.get(remote_branch.target))
                self.repo.checkout(local_branch_ref)
                logging.info(f"Created and checked out branch: {self.branch}")
                return True

            # Log current and remote commit IDs
            logging.info(f"Current local commit: {local_branch.target}")
            logging.info(f"Remote commit: {remote_branch.target}")

            # Check if we're already up to date
            if local_branch.target == remote_branch.target:
                logging.info("Repository is already up to date")
                return True

            # Perform a merge analysis (simulate git pull)
            self.repo.checkout(local_branch_ref)
            merge_result, _ = self.repo.merge_analysis(remote_branch.target)

            # Handle different merge situations
            if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
                logging.info("Repository is already up to date")
                return True

            elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
                # Fast-forward merge
                logging.info("Performing fast-forward merge")
                local_branch.set_target(remote_branch.target)
                self.repo.checkout(local_branch_ref)
                logging.info("Fast-forward merge completed")
                return True

            elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
                # Normal merge (might have conflicts)
                logging.info("Performing normal merge")

                try:
                    # Attempt the merge
                    self.repo.merge(remote_branch.target)

                    # Check for conflicts
                    if self.repo.index.conflicts:
                        conflict_paths = [c[0].path for c in self.repo.index.conflicts]
                        logging.error(f"Merge conflicts in: {', '.join(conflict_paths)}")
                        # Abort the merge
                        self.repo.state_cleanup()
                        return False

                    # Create the merge commit
                    author = pygit2.Signature('Auto Merger', 'auto@merger.local')
                    self.repo.create_commit(
                        'HEAD',
                        author, author,
                        f"Merge branch '{self.branch}' of {self.repo_url}",
                        self.repo.index.write_tree(),
                        [self.repo.head.target, remote_branch.target]
                    )
                    self.repo.state_cleanup()
                    logging.info("Merge completed successfully")
                    return True

                except pygit2.GitError as e:
                    logging.error(f"Merge failed: {e}")
                    # Try to abort the merge if it's in progress
                    try:
                        self.repo.state_cleanup()
                    except:
                        pass
                    return False
            else:
                logging.error("Merge analysis returned an unexpected result")
                return False

        except pygit2.GitError as e:
            logging.error(f"Failed to update repository: {e}")
            return False

    def get_remote_branches(self) -> List[str]:
        """
        Return list of available branches from remote repo using GitHub API.
        Falls back to default branch if API request fails.
        """
        try:
            # Extract owner and repo name from URL
            url_parts = self.repo_url.rstrip('/').split('/')
            if self.repo_url.startswith('http'):
                owner = url_parts[-2]
                repo_name = url_parts[-1]
                if repo_name.endswith('.git'):
                    repo_name = repo_name[:-4]
            else:
                # Handle SSH URLs (git@github.com:owner/repo.git)
                repo_part = url_parts[-1]
                owner, repo_name = repo_part.split(':')[-1].split('/')
                if repo_name.endswith('.git'):
                    repo_name = repo_name[:-4]

            # API request with timeout
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo_name}/branches",
                timeout=10
            )
            response.raise_for_status()
            branches = [branch["name"] for branch in response.json()]
            logging.info(f"Found {len(branches)} remote branches")
            return branches
        except Exception as e:
            logging.warning(f"Error fetching branches via API: {e}")
            return ["main", "master"]  # Fallback to common default branches


class GitRepoManagement:
    """
    Manages a Git repository with an associated virtual environment.
    Enforces the use of the virtual environment for all operations.
    """

    def __init__(self, repo_url: str, target_dir: str, branch: str = "main", workdir: str = None):
        """
        Initialize repository management.

        Args:
            repo_url: URL of the Git repository
            target_dir: Local directory where the repository will be cloned
            branch: Git branch to use (default: "main")
            workdir: Work directory for portable Python installation
        """
        self.target_dir = Path(target_dir).resolve()
        self.workdir = Path(workdir) if workdir else None
        self.portable_python_dir = self.workdir / "portable_python" if self.workdir else None
        self.portable_python_path = None
        self.git_repo = GitRepository(repo_url, self.target_dir, branch)
        self.venv = None

    def setup(self) -> bool:
        """
        Clone/update the repository and set up the virtual environment.

        Returns:
            True if setup completed successfully
        """
        try:
            logging.info(f"Setting up repository in {self.target_dir}")

            # Check if portable Python exists, install if not
            if self.portable_python_dir and not (self.portable_python_dir / "miniforge").exists():
                logging.info("Portable Python not found. Installing...")
                installer = miniforge_portable.PortablePythonInstaller(self.portable_python_dir)
                installer.install()

            # Set the Python path
            if self.portable_python_dir:
                self.portable_python_path = self.portable_python_dir / "miniforge" / (
                    "python.exe" if global_variables.system == "Windows" else "bin/python")

            # Clone or update the repository
            self.git_repo.clone_or_update()

            # Setup the virtual environment
            self.venv = VirtualEnvironment(self.target_dir, str(self.portable_python_path))
            self.venv.create()
            self.venv.install_requirements(self.target_dir / "requirements.txt")

            logging.info(f"Repository setup complete")
            return True

        except Exception as e:
            logging.error(f"Repository setup failed: {e}")
            return False

    def run_script(self, script_path: str, script_args: Optional[List[str]] = None,
                   timeout: Optional[int] = None) -> Optional[subprocess.Popen]:
        """
        Execute a Python script using the virtual environment's Python interpreter.

        Args:
            script_path: Path to the script relative to the target directory
            script_args: List of arguments to pass to the script
            timeout: Timeout for script execution in seconds (None for no timeout)

        Returns:
            subprocess.Popen object representing the running script
        """
        if script_args is None:
            script_args = []

        abs_script_path = (self.target_dir / script_path).resolve()
        if not abs_script_path.exists():
            logging.error(f"Script not found: {abs_script_path}")
            return None

        # Use the Python from the virtual environment
        python_path = self.venv.get_python_path()
        cmd = [str(python_path), str(abs_script_path)] + script_args

        logging.info(f"Running script with venv Python: {' '.join(cmd)}")

        try:
            process = subprocess.Popen(
                cmd,
                cwd=self.target_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )

            # Create daemon threads to read stdout/stderr
            def stream_reader(stream, prefix):
                try:
                    for line in iter(stream.readline, ''):
                        if line:  # Skip empty lines
                            print(f"{prefix}: {line.strip()}")
                except (ValueError, IOError) as e:
                    # Handle pipe closed or other IO errors
                    logging.debug(f"Stream reader stopped: {e}")

            stdout_thread = threading.Thread(target=stream_reader,
                                             args=(process.stdout, "STDOUT"),
                                             daemon=True)
            stderr_thread = threading.Thread(target=stream_reader,
                                             args=(process.stderr, "STDERR"),
                                             daemon=True)

            stdout_thread.start()
            stderr_thread.start()

            # If timeout is specified, start a watcher thread
            if timeout:
                def timeout_watcher():
                    start_time = time.time()
                    while process.poll() is None:
                        if time.time() - start_time > timeout:
                            logging.warning(f"Script execution timed out after {timeout} seconds")
                            process.terminate()
                            time.sleep(1)
                            if process.poll() is None:
                                process.kill()
                            break
                        time.sleep(1)

                threading.Thread(target=timeout_watcher, daemon=True).start()

            return process

        except Exception as e:
            logging.error(f"Failed to run script: {e}")
            return None

    def get_remote_branches(self) -> List[str]:
        """Fetch list of remote branch names."""
        return self.git_repo.get_remote_branches()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # Example usage
    git_repo_url = "https://github.com/tryiou/xbridge_trading_bots"
    local_target_dir = "xbridge_trading_bots"
    remote_branch = "main"
    logging.info(f"aio_folder: {global_variables.aio_folder}")
    manager = GitRepoManagement(git_repo_url, local_target_dir, remote_branch, global_variables.aio_folder)
    manager.setup()

    # Example of running a script after setup
    manager.run_script("gui_pingpong.py")
