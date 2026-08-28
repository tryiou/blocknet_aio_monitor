import logging
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests

from gui.constants import DOWNLOAD_CHUNK_SIZE, GIT_COMMAND_TIMEOUT_S, RPC_TIMEOUT_S
from utilities.app_container import get_container

try:
    import utilities.miniforge_portable as miniforge_portable
except ModuleNotFoundError:
    import miniforge_portable

import pygit2

logger = logging.getLogger(__name__)


class ExecutionError(Exception):
    """Custom exception for Git execution failures."""

    pass


class BranchSwitchBlockedError(Exception):
    """Raised when branch switch is blocked by local conflicts."""

    def __init__(self, message: str, blocked_paths: list[str] | None = None):
        super().__init__(message)
        self.blocked_paths = blocked_paths or []


def run_command(
    cmd_list: list[str], cwd: Path | None = None, timeout: int = GIT_COMMAND_TIMEOUT_S
) -> tuple[int, str, str]:
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
        process = subprocess.run(cmd_list, check=False, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return process.returncode, process.stdout, process.stderr
    except subprocess.TimeoutExpired as e:
        raise ExecutionError(f"Command timed out after {timeout} seconds: {' '.join(cmd_list)}") from e
    except FileNotFoundError as e:
        raise ExecutionError(f"Command not found: {cmd_list[0]}") from e
    except Exception as e:
        raise ExecutionError(f"Command execution failed: {e}") from e


class VirtualEnvironment:
    """Manages Python virtual environments with portable support."""

    def __init__(self, target_dir: Path, portable_python_path: str = None, venv_dir: Path | None = None):
        """
        Initialize virtual environment manager.

        Args:
            target_dir: Base directory for environment
            portable_python_path: Path to portable Python binary
            venv_dir: Explicit venv directory (if None, uses target_dir/venv for legacy compat)
        """
        self.target_dir = target_dir
        if venv_dir is not None:
            self.venv_dir = Path(venv_dir)
        else:
            self.venv_dir = target_dir / "venv"
        self.portable_python_path = portable_python_path
        self.is_windows = sys.platform == "win32"
        self.is_darwin = sys.platform == "darwin"
        self.bin_dir = "Scripts" if self.is_windows else "bin"
        self.python_exe = "python.exe" if self.is_windows else "python"
        self.pip_exe = "pip.exe" if self.is_windows else "pip"
        self.venv_bin_path = self.venv_dir / self.bin_dir
        logger.info(f"Virtual environment path: {self.venv_bin_path}")

    def _is_broken(self) -> tuple[bool, str]:
        """Check if venv is broken (missing files or stale shebang)."""
        if not self.venv_bin_path.is_dir():
            if self.venv_dir.exists():
                return True, "missing bin dir"
            return False, ""  # not broken — simply doesn't exist yet, create will handle
        venv_python = self.venv_bin_path / self.python_exe
        if not venv_python.exists():
            return True, "missing python"
        pip_path = self.venv_bin_path / self.pip_exe
        if not pip_path.exists():
            return True, "missing pip"
        # Check pip shebang points to existing interpreter (covers relocated venv)
        # Windows pip.exe has no shebang — skip
        if not self.is_windows:
            try:
                if pip_path.is_file():
                    data = (
                        pip_path.read_bytes().split(b"\n", 1)[0]
                        if pip_path.stat().st_size < DOWNLOAD_CHUNK_SIZE
                        else b""
                    )
                    if data.startswith(b"#!"):
                        interp = data[2:].strip().split(b" ")[0].decode(errors="ignore")
                        if interp and not Path(interp).exists():
                            return True, f"stale pip shebang -> {interp}"
                        # Also detect legacy in-tree path after relocation
                        if b"xbridge_trading_bots/venv" in data and str(self.venv_dir).encode() not in data:
                            return True, "stale pip shebang (legacy path)"
            except Exception as e:
                logger.debug(f"pip shebang check skipped: {e}")
        # Verify pip is actually runnable via venv python (cheap)
        try:
            rc, _, _ = run_command([str(venv_python), "-m", "pip", "--version"], timeout=RPC_TIMEOUT_S)
            if rc != 0:
                return True, "pip not runnable"
        except Exception as e:
            return True, f"pip check failed: {e}"
        return False, ""

    def ensure_healthy(self) -> bool:
        """Auto-repair broken venv by recreating it. Returns True if recreated."""
        broken, reason = self._is_broken()
        if not broken:
            return False
        logger.warning(f"Venv broken ({reason}) at {self.venv_dir} — recreating")
        try:
            if self.venv_dir.exists():
                shutil.rmtree(str(self.venv_dir), ignore_errors=True)
                if self.venv_dir.exists():
                    logger.error(f"Failed to remove broken venv {self.venv_dir} — still exists")
                    # don't return, try to recreate anyway (venv --clear may handle)
        except Exception as e:
            logger.warning(f"Failed to remove broken venv: {e}")
        self._create_venv_force()
        # verify after recreate
        broken2, reason2 = self._is_broken()
        if broken2:
            logger.error(f"Venv still broken after recreate: {reason2}")
            raise ExecutionError(f"Venv still broken after recreate: {reason2}")
        return True

    def _resolve_python(self) -> str:
        """Resolve interpreter for venv creation, fallback to sys.executable."""
        raw = self.portable_python_path
        if raw is None or str(raw) == "None" or str(raw).strip() == "":
            return sys.executable
        if self.is_darwin and raw:
            p = Path(str(raw))
            if not p.exists():
                raise FileNotFoundError(f"Python not found: {p}")
            return str(p.resolve())
        # Linux/Windows: use portable if exists, else fallback
        p = Path(str(raw))
        if p.exists():
            return str(p)
        logger.warning(f"Python {raw} not found, using {sys.executable}")
        return sys.executable

    def _create_venv_force(self) -> None:
        """Force-create venv (no existence check)."""
        logger.info(f"Creating virtual environment at {self.venv_dir}")
        self.venv_dir.parent.mkdir(exist_ok=True, parents=True)
        real_python_path = self._resolve_python()
        try:
            returncode, stdout, stderr = run_command(
                [str(real_python_path), "-m", "venv", str(self.venv_dir)], timeout=GIT_COMMAND_TIMEOUT_S
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

    def create(self) -> None:
        """Create virtual environment using specified Python interpreter."""
        # Auto-heal if existing venv is broken (e.g. stale shebang after move)
        broken, reason = self._is_broken()
        if self.venv_bin_path.exists():
            if not broken:
                logger.info("Virtual environment already exists - skipping creation")
                return
            logger.warning(f"Venv exists but broken ({reason}) — recreating")
            try:
                shutil.rmtree(str(self.venv_dir), ignore_errors=True)
                if self.venv_dir.exists():
                    logger.error(f"Failed to remove broken venv {self.venv_dir} — still exists")
            except Exception as e:
                logger.warning(f"Failed to remove broken venv dir: {e}")
        elif broken:
            # venv dir exists but bin missing (or other broken) — recreate
            logger.warning(f"Venv broken ({reason}) at {self.venv_dir} — recreating")
            try:
                shutil.rmtree(str(self.venv_dir), ignore_errors=True)
                if self.venv_dir.exists():
                    logger.error(f"Failed to remove broken venv {self.venv_dir} — still exists")
            except Exception as e:
                logger.warning(f"Failed to remove broken venv dir: {e}")
        self._create_venv_force()

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
        # Prefer python -m pip (shebang-independent) — fixes relocated venv
        try:
            python_path = self.get_python_path()
        except FileNotFoundError as e:
            # venv broken — try auto-heal once
            logger.warning(f"Python missing for pip install: {e} — attempting venv repair")
            if self.ensure_healthy():
                python_path = self.get_python_path()
            else:
                raise

        for attempt in range(2):
            try:
                cmd = [str(python_path), "-m", "pip", "install", "-r", str(requirements_path)]
                returncode, stdout, stderr = run_command(cmd, self.target_dir, timeout=GIT_COMMAND_TIMEOUT_S)
                if returncode != 0:
                    raise ExecutionError(f"Requirements installation failed: {stderr}")
                logger.info("Requirements installed successfully")
                return
            except Exception as e:
                if attempt == 0:
                    try:
                        broken, _ = self._is_broken()
                    except Exception:
                        broken = False
                    if broken or isinstance(e, ExecutionError):
                        logger.warning(f"pip install failed ({e}) — attempting venv repair and retry")
                        try:
                            if self.ensure_healthy():
                                python_path = self.get_python_path()
                                continue
                        except Exception as heal_e:
                            logger.error(f"Venv heal failed: {heal_e}")
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

    def __init__(self, repo_url: str, target_dir: Path, remote_branch: str = "main", backup_base: Path | None = None):
        self.repo_url = repo_url
        self.target_dir = target_dir
        self.remote_branch = remote_branch
        self.repo = None
        self.git_timeout = GIT_COMMAND_TIMEOUT_S
        self.backup_base = Path(backup_base) if backup_base else None

    def _get_backup_base(self) -> Path:
        if self.backup_base:
            return self.backup_base
        # Default: parent of target_dir / backups
        return self.target_dir.parent / "backups"

    def _get_changed_paths(self, target_oid) -> set:
        """Get set of paths changed between HEAD and target."""
        try:
            head_commit = self.repo.head.peel(pygit2.Commit)
            target_commit = self.repo.get(target_oid).peel(pygit2.Commit)
            diff = self.repo.diff(head_commit.tree, target_commit.tree)
            changed = set()
            for delta in diff.deltas:
                if delta.old_file.path:
                    changed.add(delta.old_file.path)
                if delta.new_file.path:
                    changed.add(delta.new_file.path)
            return changed
        except Exception as e:
            logger.warning(f"Could not compute changed paths: {e}")
            return set()

    def _collect_blockers(self, target_oid) -> list[str]:
        """Collect dirty/untracked paths that would block checkout to target."""
        try:
            status = self.repo.status()
        except Exception as e:
            logger.warning(f"Could not get repo status: {e}")
            return []
        if not status:
            return []
        changed = self._get_changed_paths(target_oid)
        # If diff failed or empty, be conservative: any dirty file could block
        # but we already filtered to changed-intersection for surgical backup
        blockers: list[str] = []
        for path, _flags in status.items():
            if changed and path not in changed:
                # File not on the changed path set -> not blocking
                # Exception: untracked colliding with new file should be in changed
                continue
            # Any non-zero status that overlaps changed paths is a blocker
            blockers.append(path)
        if blockers:
            logger.warning(f"Checkout blockers detected ({len(blockers)}): {blockers[:10]}")
        return blockers

    def _backup_blockers(self, blockers: list[str]) -> Path | None:
        """Move blocking paths to timestamped backup dir. Returns backup dir."""
        if not blockers:
            return None
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self._get_backup_base() / f"{self.target_dir.name}_{timestamp}_checkout"
        backup_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Backing up {len(blockers)} blocking paths to {backup_dir}")
        for rel_path in blockers:
            src = self.target_dir / rel_path
            dst = backup_dir / rel_path
            try:
                if not src.exists() and not src.is_symlink():
                    # Deleted file: record but nothing to move
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                logger.info(f"Backed up {rel_path} -> {dst}")
            except Exception as e:
                logger.error(f"Failed to backup {rel_path}: {e}")
        # Clean up empty parent dirs left behind (not critical)
        return backup_dir

    def _prepare_checkout(self, target_oid) -> None:
        """Backup blockers then checkout target tree."""
        blockers = self._collect_blockers(target_oid)
        if blockers:
            self._backup_blockers(blockers)
        target_commit = self.repo.get(target_oid)
        strategy = pygit2.GIT_CHECKOUT_SAFE | pygit2.GIT_CHECKOUT_RECREATE_MISSING
        try:
            self.repo.checkout_tree(target_commit, strategy=strategy)
        except pygit2.GitError as e:
            # After backup, retry once with precise diagnostics
            remaining = self.repo.status()
            detail = ", ".join(list(remaining.keys())[:10]) if remaining else str(e)
            logger.error(f"Checkout still blocked after backup: {detail}")
            raise BranchSwitchBlockedError(
                f"Checkout blocked: {e}", blocked_paths=list(remaining.keys()) if remaining else []
            ) from e

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
        except BranchSwitchBlockedError:
            raise
        except Exception as e:
            logger.error(f"Repository operation failed: {e}")
            raise

    def _clone_repo(self) -> None:
        """Clone a fresh repository."""
        logger.info(f"Cloning repository to {self.target_dir}")
        self.target_dir.mkdir(exist_ok=True, parents=True)
        try:
            callbacks = pygit2.RemoteCallbacks()
            start_time = time.time()
            self.repo = pygit2.clone_repository(self.repo_url, str(self.target_dir), callbacks=callbacks)
            elapsed_time = time.time() - start_time
            logger.info(f"Clone completed in {elapsed_time:.2f} seconds")
            self._checkout_branch()
            logger.info("Repository cloned successfully")
        except pygit2.GitError as e:
            logger.error(f"Failed to clone repository: {e}")
            if self.target_dir.exists():
                shutil.rmtree(self.target_dir)
            raise

    def _checkout_branch(self) -> None:
        """Checkout the specified branch. Raises on failure."""
        try:
            branch_ref = f"refs/heads/{self.remote_branch}"
            if branch_ref in self.repo.references:
                # Heal stale local branch: reset to remote tip if exists
                remote_ref = f"refs/remotes/origin/{self.remote_branch}"
                if remote_ref in self.repo.references:
                    remote_oid = self.repo.references[remote_ref].target
                    try:
                        self._prepare_checkout(remote_oid)
                        self.repo.references[branch_ref].set_target(remote_oid)
                        self.repo.set_head(branch_ref)
                        logger.info(f"Reset and checked out existing branch: {self.remote_branch}")
                        return
                    except BranchSwitchBlockedError:
                        raise
                    except pygit2.GitError as e:
                        raise BranchSwitchBlockedError(f"Could not checkout branch {self.remote_branch}: {e}") from e
                # No remote yet (fresh clone race)
                self.repo.checkout(branch_ref)
                logger.info(f"Checked out existing branch: {self.remote_branch}")
                return

            remote_ref = f"refs/remotes/origin/{self.remote_branch}"
            if remote_ref in self.repo.references:
                remote_branch_ref = self.repo.references[remote_ref]
                target_oid = remote_branch_ref.target
                target_commit = self.repo.get(target_oid)
                # Prepare worktree before creating branch
                self._prepare_checkout(target_oid)
                self.repo.create_branch(self.remote_branch, target_commit)
                branch_ref_created = f"refs/heads/{self.remote_branch}"
                self.repo.set_head(branch_ref_created)
                logger.info(f"Created and checked out branch from remote: {self.remote_branch}")
                return

            logger.warning(f"Branch '{self.remote_branch}' not found locally or remotely. Staying on current branch.")
        except BranchSwitchBlockedError:
            raise
        except pygit2.GitError as e:
            raise BranchSwitchBlockedError(f"Could not checkout branch {self.remote_branch}: {e}") from e

    def _recreate_repo(self) -> None:
        """Remove and recreate the repository directory."""
        logger.warning(f"Recreating repository at {self.target_dir} - this will preserve backups")
        if self.target_dir.exists():
            shutil.rmtree(self.target_dir)
        self.target_dir.mkdir(exist_ok=True, parents=True)
        self._clone_repo()

    def _update_repo(self):
        """Update an existing repository using fetch + merge logic."""
        self.repo = pygit2.Repository(str(self.target_dir))
        logger.info("Opened existing repository")

        remote_name = "origin"
        branch = self.remote_branch

        for remote in self.repo.remotes:
            if remote.name == remote_name:
                logger.info(f"Fetching updates from remote '{remote_name}'")
                start_time = time.time()
                remote.fetch()
                elapsed_time = time.time() - start_time
                logger.info(f"Fetch completed in {elapsed_time:.2f} seconds")

                try:
                    remote_master_id = self.repo.lookup_reference(f"refs/remotes/{remote_name}/{branch}").target
                except KeyError:
                    logger.error(f"Remote branch '{branch}' not found in '{remote_name}'")
                    return

                current_branch = self.repo.head.shorthand
                logger.info(f"current_branch: {current_branch}, self.remote_branch: {self.remote_branch}")
                if current_branch != self.remote_branch:
                    self._checkout_branch()

                try:
                    self.repo.lookup_reference(f"refs/heads/{branch}")
                except KeyError:
                    logger.info(f"Local branch '{branch}' not found. Creating it.")
                    target_commit = self.repo.get(remote_master_id)
                    self._prepare_checkout(remote_master_id)
                    self.repo.create_branch(branch, target_commit)
                    self.repo.lookup_reference(f"refs/heads/{branch}")
                    self.repo.set_head(f"refs/heads/{branch}")

                merge_result, _ = self.repo.merge_analysis(remote_master_id)

                if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
                    logger.info("Repository is already up to date")
                    # Ensure HEAD is symbolic to correct branch
                    try:
                        if self.repo.head.shorthand != branch:
                            self.repo.set_head(f"refs/heads/{branch}")
                    except Exception as e:  # debug logged
                        logger.debug("Suppressed Exception: %s", e, exc_info=True)
                    return

                elif merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD:
                    logger.info("Performing fast-forward merge")
                    # Hygiene: backup any dirty files that overlap the FF diff
                    blockers = self._collect_blockers(remote_master_id)
                    if blockers:
                        self._backup_blockers(blockers)
                    target_commit = self.repo.get(remote_master_id)
                    strategy = pygit2.GIT_CHECKOUT_SAFE | pygit2.GIT_CHECKOUT_RECREATE_MISSING
                    try:
                        self.repo.checkout_tree(target_commit, strategy=strategy)
                    except pygit2.GitError as e:
                        remaining = self.repo.status()
                        raise BranchSwitchBlockedError(
                            f"Fast-forward checkout blocked: {e}",
                            blocked_paths=list(remaining.keys()) if remaining else [],
                        ) from e
                    # Update branch ref and ensure HEAD symbolic
                    branch_ref = self.repo.lookup_reference(f"refs/heads/{branch}")
                    branch_ref.set_target(remote_master_id)
                    try:
                        self.repo.set_head(f"refs/heads/{branch}")
                    except Exception as e:
                        logger.warning(f"Could not set HEAD to {branch}: {e}")
                    # Verify not detached
                    try:
                        head = self.repo.head
                        if head.shorthand != branch:
                            logger.warning(f"HEAD not on {branch} after FF (head={head.name})")
                    except Exception as e:  # debug logged
                        logger.debug("Suppressed Exception: %s", e, exc_info=True)
                    logger.info("Fast-forward merge completed")
                    return

                elif merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL:
                    logger.error("Pulling remote changes leads to a conflict")
                    raise BranchSwitchBlockedError(
                        "Git conflicts detected during pull operation - branches have diverged"
                    )

                else:
                    logger.error(f"Unexpected merge result: {merge_result}")
                    raise AssertionError("Unknown merge analysis result")

        logger.error(f"Remote '{remote_name}' not found")
        raise ExecutionError(f"Remote '{remote_name}' not found")

    def get_remote_branches(self) -> list[str] | None:
        """
        Return list of available branches from remote repo using GitHub API.
        Returns None if API request fails (caller should not invalidate saved branch).
        """
        try:
            url_parts = self.repo_url.rstrip("/").split("/")
            if self.repo_url.startswith("http"):
                owner = url_parts[-2]
                repo_name = url_parts[-1]
                if repo_name.endswith(".git"):
                    repo_name = repo_name[:-4]
            else:
                first_part = url_parts[0]
                owner = first_part.split(":")[-1]
                repo_name = url_parts[-1]
                if repo_name.endswith(".git"):
                    repo_name = repo_name[:-4]

            response = requests.get(f"https://api.github.com/repos/{owner}/{repo_name}/branches", timeout=RPC_TIMEOUT_S)
            response.raise_for_status()
            branches = [branch["name"] for branch in response.json()]
            logger.info(f"Found {len(branches)} remote branches")
            return branches
        except Exception as e:
            logger.warning(f"Error fetching branches via API: {e}")
            return None


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
        # Venv relocated outside worktree when workdir is available
        if self.workdir:
            self.venv_dir = self.workdir / f"{self.target_dir.name}_venv"
        else:
            self.venv_dir = None  # use legacy in-tree venv
        backup_base = self.workdir / "backups" if self.workdir else None
        self.git_repo = GitRepository(repo_url, self.target_dir, branch, backup_base=backup_base)
        self.venv = None
        self._reader_threads: list[threading.Thread] = []
        self._watcher_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._process: subprocess.Popen | None = None
        self._lock = threading.RLock()

    def _migrate_legacy_venv(self) -> None:
        """Move legacy in-tree venv to relocated location if needed."""
        if self.venv_dir is None:
            return
        legacy = self.target_dir / "venv"
        if legacy.exists() and legacy.is_dir() and not self.venv_dir.exists():
            try:
                logger.info(f"Migrating legacy venv {legacy} -> {self.venv_dir}")
                shutil.move(str(legacy), str(self.venv_dir))
                logger.info("Legacy venv migrated successfully")
                # venv is not relocatable due to absolute pip shebangs — heal inline
                try:
                    tmp_venv = VirtualEnvironment(
                        self.target_dir,
                        str(self.portable_python_path) if self.portable_python_path else None,
                        venv_dir=self.venv_dir,
                    )
                    if tmp_venv.ensure_healthy():
                        logger.info("Migrated venv healed after relocation")
                except Exception as heal_e:
                    logger.warning(f"Post-migration heal failed (will retry on setup): {heal_e}")
            except Exception as e:
                logger.warning(f"Could not migrate legacy venv (will create fresh): {e}")

    def setup(self) -> None:
        """
        Clone/update the repository and set up the virtual environment.

        Returns:
            True if setup completed successfully
        """
        try:
            logger.info(f"Setting up repository in {self.target_dir}")

            if self.portable_python_dir and not (self.portable_python_dir / "miniforge").exists():
                logger.info("Portable Python not found. Installing...")
                installer = miniforge_portable.PortablePythonInstaller(self.portable_python_dir)
                installer.install()
                # Clean up installer archive
                try:
                    for pattern in ["*.sh", "*.exe"]:
                        for f in self.portable_python_dir.glob(pattern):
                            if f.is_file() and f.stat().st_size > 1024 * 1024:
                                f.unlink()
                                logger.info(f"Removed installer archive {f.name}")
                except Exception as e:
                    logger.warning(f"Could not clean installer archive: {e}")

            if self.portable_python_dir:
                container = get_container()
                self.portable_python_path = (
                    self.portable_python_dir
                    / "miniforge"
                    / ("python.exe" if container.system == "Windows" else "bin/python")
                )

            self._migrate_legacy_venv()

            self.git_repo.clone_or_update()

            # Setup the virtual environment (relocated if available)
            if self.venv_dir:
                self.venv = VirtualEnvironment(
                    self.target_dir,
                    str(self.portable_python_path) if self.portable_python_path else None,
                    venv_dir=self.venv_dir,
                )
            else:
                self.venv = VirtualEnvironment(
                    self.target_dir, str(self.portable_python_path) if self.portable_python_path else None
                )
            self.venv.create()
            self.venv.install_requirements(self.target_dir / "requirements.txt")

            logger.info("Repository setup complete")

        except BranchSwitchBlockedError:
            raise
        except Exception as e:
            raise Exception(f"Repository setup failed: {e}") from e

    def run_script(
        self, script_path: str, script_args: list[str] | None = None, timeout: int | None = None
    ) -> subprocess.Popen | None:
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

        if self.venv is None:
            logger.error("Cannot run script - venv not initialized")
            return None
        python_path = self.venv.get_python_path()
        cmd = [str(python_path), str(abs_script_path)] + script_args

        logger.info(f"Running script with venv Python: {' '.join(cmd)}")

        try:
            with self._lock:
                self._stop_event.clear()
                process = subprocess.Popen(
                    cmd, cwd=self.target_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
                )
                self._process = process

                def stream_reader(stream, prefix):
                    try:
                        for line in iter(stream.readline, ""):
                            if self._stop_event.is_set():
                                break
                            if line:
                                print(f"{prefix}: {line.strip()}")
                    except (OSError, ValueError) as e:
                        logger.debug(f"Stream reader stopped: {e}")

                stdout_thread = threading.Thread(
                    target=stream_reader, args=(process.stdout, "STDOUT"), daemon=True, name="GitRepoStdoutReader"
                )
                stderr_thread = threading.Thread(
                    target=stream_reader, args=(process.stderr, "STDERR"), daemon=True, name="GitRepoStderrReader"
                )

                stdout_thread.start()
                stderr_thread.start()
                self._reader_threads = [stdout_thread, stderr_thread]

                if timeout:

                    def timeout_watcher():
                        start_time = time.time()
                        while process.poll() is None and not self._stop_event.is_set():
                            if time.time() - start_time > timeout:
                                logger.warning(f"Script execution timed out after {timeout} seconds")
                                process.terminate()
                                time.sleep(1)
                                if process.poll() is None:
                                    process.kill()
                                break
                            self._stop_event.wait(1)

                    self._watcher_thread = threading.Thread(
                        target=timeout_watcher, daemon=True, name="GitRepoTimeoutWatcher"
                    )
                    self._watcher_thread.start()

            return process

        except Exception as e:
            logger.error(f"Failed to run script: {e}")
            return None

    def stop(self) -> None:
        """Terminate running script and join cooperative reader/watcher threads."""
        self._stop_event.set()
        with self._lock:
            proc = getattr(self, "_process", None)
            if proc is not None:
                try:
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except Exception:
                            try:
                                proc.kill()
                            except Exception as e:  # debug logged
                                logger.debug(f"Suppressed Exception: {e}", exc_info=True)
                except Exception as e:  # debug logged
                    logger.debug(f"Suppressed Exception: {e}", exc_info=True)
            for thr in getattr(self, "_reader_threads", []):
                try:
                    if thr.is_alive():
                        thr.join(timeout=0.5)
                except Exception as e:  # debug logged
                    logger.debug(f"Suppressed Exception: {e}", exc_info=True)
            watcher = getattr(self, "_watcher_thread", None)
            if watcher is not None:
                try:
                    if watcher.is_alive():
                        watcher.join(timeout=0.5)
                except Exception as e:  # debug logged
                    logger.debug(f"Suppressed Exception: {e}", exc_info=True)
            self._reader_threads = []
            self._watcher_thread = None
            self._process = None

    def get_remote_branches(self) -> list[str] | None:
        """Fetch list of remote branch names. Returns None on failure."""
        return self.git_repo.get_remote_branches()


if __name__ == "__main__":
    git_repo_url = "https://github.com/tryiou/xbridge_trading_bots"
    local_target_dir = "xbridge_trading_bots"
    branch = "main"
    container = get_container()
    logger.info(f"aio_folder: {container.aio_folder}")
    manager = GitRepoManagement(git_repo_url, local_target_dir, branch, container.aio_folder)
    manager.setup()
    manager.run_script("main_gui.py")
