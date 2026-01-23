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

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Custom exception for Git execution failures."""
    pass


def run_command(cmd_list: List[str], 
               cwd: Optional[Path] = None,
               timeout: int = 300) -> Tuple[int, str, str]:
    """
    Execute a command and capture its output.

    Args:
        cmd_list: Command and arguments as list of strings
        cwd: Working directory path (default: None)
        timeout: Timeout in seconds (default: 300)

    Returns:
        Tuple of (return_code, stdout, stderr)

    Raises:
        ExecutionError: On command failure or timeout
    """
    try:
        process = subprocess.run(
            cmd_list,
            check=False,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        return process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired as e:
        raise ExecutionError(f"Command timed out after {timeout} seconds: {' '.join(cmd_list)}") from e
    except FileNotFoundError as e:
        raise ExecutionError(f"Command not found: {cmd_list[0]}") from e
    except Exception as e:
        raise ExecutionError(f"Command execution failed: {e}") from e


class VirtualEnvironment:
    """Manages Python virtual environments with portable support."""

    def __init__(self, target_dir: Path, portable_python_path: str = None):
        """
        Initialize virtual environment manager.
        
        Args:
            target_dir: Base directory for environment
            portable_python_path: Path to portable Python binary
        """
        self.target_dir = target_dir
        self.venv_dir = target_dir / "venv"
        self.portable_python_path = portable_python_path
        self.is_windows = sys.platform == "win32"
        self.is_darwin = sys.platform == "darwin"
        self.bin_dir = "Scripts" if self.is_windows else "bin"
        self.python_exe = "python.exe" if self.is_windows else "python"
        self.pip_exe = "pip.exe" if self.is_windows else "pip"
        self.venv_bin_path = self.venv_dir / self.bin_dir
        logger.info(f"Virtual environment path: {self.venv_bin_path}")

    def create(self) -> None:
        """Create virtual environment using specified Python interpreter."""
        if self.venv_bin_path.exists():
            logger.info("Virtual environment already exists - skipping creation")
            return

        logger.info(f"Creating virtual environment at {self.venv_dir}")
        self.venv_dir.parent.mkdir(exist_ok=True, parents=True)

        if self.is_darwin and self.portable_python_path:
            python_path = Path(self.portable_python_path)
            if not python_path.exists():
                # logger.warning(f"Portable Python path invalid: {python_path}")
                raise FileNotFoundError(f"Python not found: {python_path}")
            real_python_path = python_path.resolve()
        else:
            real_python_path = self.portable_python_path

        try:
            returncode, stdout, stderr = run_command(
                [str(real_python_path), "-m", "venv", str(self.venv_dir)],
                timeout=300
            )
            if returncode != 0:
                logger.error(f"venv creation failed: {stderr}")
                raise ExecutionError(f"Virtual environment creation failed: {stderr}")
                
            if not self.venv_bin_path.exists():
                raise ExecutionError("Virtual environment bin directory not created")
                
            logger.info("Virtual environment created successfully")
        except Exception as e:
            logger.error(f"Failed to create virtual environment: {str(e)}")
            raise

    def install_requirements(self, requirements_path: Path) -> None:
        """
        Install packages from requirements file.
        
        Args:
            requirements_path: Path to requirements.txt
        """
        if not requirements_path.exists():
            logger.info("requirements.txt not found - skipping install")
            return

        logger.info("Installing requirements from requirements.txt")
        pip_path = self.get_pip_path()
        python_path = self.get_python_path()

        try:
            cmd = [str(pip_path), "install", "-r", str(requirements_path)]
            returncode, stdout, stderr = run_command(cmd, self.target_dir, timeout=300)
            if returncode != 0:
                raise ExecutionError(f"Requirements installation failed: {stderr}")
            logger.info("Requirements installed successfully")
        except Exception as e:
            logger.error(f"Failed to install requirements: {str(e)}")
            raise

    def get_python_path(self) -> str:
        """
        Get path to virtual environment's Python binary.
        
        Returns:
            Path to Python interpreter as string
            
        Raises:
            FileNotFoundError: When binary not found
        """
        venv_python_path = self.venv_bin_path / self.python_exe
        if venv_python_path.exists():
            logger.debug(f"Using virtual environment Python: {venv_python_path}")
            return str(venv_python_path)
        raise FileNotFoundError(f"Python not found in {self.venv_bin_path}")

    def get_pip_path(self) -> str:
        """
        Get path to virtual environment's pip binary.
        
        Returns:
            Path to pip as string
            
        Raises:
            FileNotFoundError: When binary not found
        """
        pip_path = self.venv_bin_path / self.pip_exe
        if pip_path.exists():
            logger.debug(f"Using virtual environment pip: {pip_path}")
            return str(pip_path)
        raise FileNotFoundError(f"pip not found in {self.venv_bin_path}")


class GitRepository:
    """Manages Git operations using pygit2."""

    def __init__(self, repo_url: str, target_dir: Path, remote_branch: str = "main"):
        self.repo_url = repo_url
        self.target_dir = target_dir
        self.remote_branch = remote_branch
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
            logger.error(f"Repository operation failed: {e}")
            raise

    def _clone_repo(self) -> None:
        """Clone a fresh repository."""
        logger.info(f"Cloning repository to {self.target_dir}")
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
            logger.info(f"Clone completed in {elapsed_time:.2f} seconds")

            self._checkout_branch()
            logger.info(f"Repository cloned successfully")
        except pygit2.GitError as e:
            logger.error(f"Failed to clone repository: {e}")
            # Clean up partial clone if it exists
            if self.target_dir.exists():
                shutil.rmtree(self.target_dir)
            raise

    def _checkout_branch(self) -> None:
        """Checkout the specified branch."""
        try:
            branch_ref = f"refs/heads/{self.remote_branch}"
            if branch_ref in self.repo.references:
                self.repo.checkout(branch_ref)
                logger.info(f"Checked out existing branch: {self.remote_branch}")
                return

            # Try to create and checkout the branch from origin
            remote_ref = f"refs/remotes/origin/{self.remote_branch}"
            if remote_ref in self.repo.references:
                remote_branch = self.repo.references[remote_ref]
                self.repo.create_branch(self.remote_branch, self.repo.get(remote_branch.target))
                self.repo.checkout(branch_ref)
                logger.info(f"Created and checked out branch from remote: {self.remote_branch}")
                return

            # If we get here, the branch doesn't exist locally or remotely
            logger.warning(f"Branch '{self.remote_branch}' not found locally or remotely. Staying on current branch.")
        except pygit2.GitError as e:
            logger.warning(f"Could not checkout branch {self.remote_branch}: {e}")

    def _recreate_repo(self) -> None:
        """Remove and recreate the repository directory."""
        logger.info(f"Recreating repository at {self.target_dir}")

        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)

        self.target_dir.mkdir(exist_ok=True, parents=True)
        self._clone_repo()

    def _update_repo(self):
        """Update an existing repository using fetch + merge logic (like git pull).
        mimics the pull method logic from MichaelBoselowitz's pygit2 "pull" example.
        """
        self.repo = pygit2.Repository(str(self.target_dir))
        logger.info("Opened existing repository")

        remote_name = "origin"
        branch = self.remote_branch

        # Find the remote
        for remote in self.repo.remotes:
            if remote.name == remote_name:
                # Fetch from remote
                logger.info(f"Fetching updates from remote '{remote_name}'")
                start_time = time.time()
                remote.fetch()
                elapsed_time = time.time() - start_time
                logger.info(f"Fetch completed in {elapsed_time:.2f} seconds")

                # Get remote master id
                remote_master_id = None
                try:
                    remote_master_id = self.repo.lookup_reference(
                        f"refs/remotes/{remote_name}/{branch}"
                    ).target
                except KeyError:
                    logger.error(f"Remote branch '{branch}' not found in '{remote_name}'")
                    return

                current_branch = self.repo.head.shorthand
                logger.info(f"current_branch: {current_branch}, self.remote_branch: {self.remote_branch}")
                if current_branch != self.remote_branch:
                    self._checkout_branch()

                # Ensure local branch exists
                try:
                    repo_branch = self.repo.lookup_reference(f"refs/heads/{branch}")
                except KeyError:
                    logger.info(f"Local branch '{branch}' not found. Creating it.")
                    self.repo.create_branch(branch, self.repo.get(remote_master_id))
                    repo_branch = self.repo.lookup_reference(f"refs/heads/{branch}")

                # Get merge analysis results
                merge_result, _ = self.repo.merge_analysis(remote_master_id)

                # Up to date, do nothing
                if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
                    logger.info("Repository is already up to date")
                    return

                # We can just fastforward
                elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
                    logger.info("Performing fast-forward merge")
                    self.repo.checkout_tree(self.repo.get(remote_master_id))
                    master_ref = self.repo.lookup_reference(f"refs/heads/{branch}")
                    master_ref.set_target(remote_master_id)
                    self.repo.head.set_target(remote_master_id)
                    logger.info("Fast-forward merge completed")
                    return

                # Normal merge would create conflicts
                elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
                    logger.error("Pulling remote changes leads to a conflict")
                    raise Exception("Git conflicts detected during pull operation")

                # Unknown result
                else:
                    logger.error(f"Unexpected merge result: {merge_result}")
                    raise AssertionError("Unknown merge analysis result")

        # If we got here, the remote wasn't found
        logger.error(f"Remote '{remote_name}' not found")
        raise Exception(f"Remote '{remote_name}' not found")

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
                # For git@github.com:test/repo.git, url_parts = ['git@github.com:test', 'repo.git']
                # owner is in first part after ':', repo_name is last part
                first_part = url_parts[0]
                owner = first_part.split(':')[-1]
                repo_name = url_parts[-1]
                if repo_name.endswith('.git'):
                    repo_name = repo_name[:-4]

            # API request with timeout
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo_name}/branches",
                timeout=10
            )
            response.raise_for_status()
            branches = [branch["name"] for branch in response.json()]
            logger.info(f"Found {len(branches)} remote branches")
            return branches
        except Exception as e:
            logger.warning(f"Error fetching branches via API: {e}")
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

    def setup(self) -> None:
        """
        Clone/update the repository and set up the virtual environment.

        Returns:
            True if setup completed successfully
        """
        try:
            logger.info(f"Setting up repository in {self.target_dir}")

            # Check if portable Python exists, install if not
            if self.portable_python_dir and not (self.portable_python_dir / "miniforge").exists():
                logger.info("Portable Python not found. Installing...")
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

            logger.info(f"Repository setup complete")

        except Exception as e:
            raise Exception(f"Repository setup failed: {e}")

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
            logger.error(f"Script not found: {abs_script_path}")
            return None

        # Use the Python from the virtual environment
        python_path = self.venv.get_python_path()
        cmd = [str(python_path), str(abs_script_path)] + script_args

        logger.info(f"Running script with venv Python: {' '.join(cmd)}")

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
                    logger.debug(f"Stream reader stopped: {e}")

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
                            logger.warning(f"Script execution timed out after {timeout} seconds")
                            process.terminate()
                            time.sleep(1)
                            if process.poll() is None:
                                process.kill()
                            break
                        time.sleep(1)

                threading.Thread(target=timeout_watcher, daemon=True).start()

            return process

        except Exception as e:
            logger.error(f"Failed to run script: {e}")
            return None

    def get_remote_branches(self) -> List[str]:
        """Fetch list of remote branch names."""
        return self.git_repo.get_remote_branches()


if __name__ == "__main__":
    # Configure logging

    # Example usage
    git_repo_url = "https://github.com/tryiou/xbridge_trading_bots"
    local_target_dir = "xbridge_trading_bots"
    branch = "main"
    logger.info(f"aio_folder: {global_variables.aio_folder}")
    manager = GitRepoManagement(git_repo_url, local_target_dir, branch, global_variables.aio_folder)
    manager.setup()

    # Example of running a script after setup
    manager.run_script("main_gui.py")
