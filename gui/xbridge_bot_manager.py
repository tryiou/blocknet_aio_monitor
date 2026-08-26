import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import List, Optional, cast
from subprocess import TimeoutExpired

from utilities.git_repo_management import BranchSwitchBlockedError, GitRepoManagement
from utilities.app_container import get_container

logger = logging.getLogger(__name__)

DEFAULT_BOTS_BRANCH = "main"
SETTINGS_KEY = "xbridge_bots_branch"


class XBridgeBotManager:
    """Manages installation and execution of XBridge trading bots."""
    
    def __init__(self, current_branch: Optional[str] = None) -> None:
        self.author = "tryiou"
        self.repo_name = "xbridge_trading_bots"
        self.repo_url = f"https://github.com/{self.author}/{self.repo_name}"
        container = get_container()
        aio_folder = container.aio_folder
        if not aio_folder:
            raise ValueError("AIO folder not configured")
        self.aio_folder = cast(str, aio_folder)
        self.target_dir_path = Path(self.aio_folder) / "xbridge_trading_bots"
        self.target_dir = str(self.target_dir_path)
        self.started = False
        # Resolve startup branch from persisted settings
        persisted = self._load_saved_branch()
        self.current_branch = persisted if persisted else (current_branch or DEFAULT_BOTS_BRANCH)
        self.repo_management: Optional[GitRepoManagement] = None
        self.installer_thread: Optional[threading.Thread] = None
        self.process: Optional[subprocess.Popen] = None
        self.deferred_start = False
        self.last_error: Optional[str] = None

    # -- branch persistence --

    def _settings_path(self) -> Path:
        return Path(os.path.expandvars(os.path.expanduser(self.aio_folder))) / "aio_settings.json"

    def _load_saved_branch(self) -> Optional[str]:
        try:
            p = self._settings_path()
            if p.exists():
                data = json.loads(p.read_text())
                v = data.get(SETTINGS_KEY)
                if isinstance(v, str) and v.strip():
                    return v.strip()
        except Exception as e:
            logger.warning(f"Could not load saved branch: {e}")
        return None

    def save_branch(self, branch: str) -> None:
        if not branch or not branch.strip():
            return
        branch = branch.strip()
        try:
            p = self._settings_path()
            data: dict = {}
            if p.exists():
                try:
                    data = json.loads(p.read_text())
                except Exception:
                    data = {}
            data[SETTINGS_KEY] = branch
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(data, indent=2))
            logger.info(f"Saved bots branch '{branch}' to {p}")
        except Exception as e:
            logger.error(f"Failed to save branch '{branch}': {e}")

    def get_saved_branch(self) -> str:
        return self._load_saved_branch() or DEFAULT_BOTS_BRANCH

    def resolve_startup_branch(self, remote_branches: Optional[List[str]]) -> str:
        """Return persisted branch if it exists on remote, else default."""
        saved = self._load_saved_branch()
        if not saved:
            return DEFAULT_BOTS_BRANCH
        if remote_branches is None:
            # API failure: keep saved (don't invalidate)
            return saved
        if saved in remote_branches:
            return saved
        logger.warning(f"Saved branch '{saved}' not on remote {remote_branches} -> fallback to {DEFAULT_BOTS_BRANCH}")
        self.save_branch(DEFAULT_BOTS_BRANCH)
        return DEFAULT_BOTS_BRANCH

    def repo_exists(self) -> bool:
        """Check if bot repository exists locally."""
        return self.target_dir_path.exists() and (self.target_dir_path / ".git").is_dir()

    def get_available_branches(self) -> Optional[List[str]]:
        """Get list of available branches from remote. Returns None on failure."""
        try:
            if self.repo_management is None:
                self.repo_management = GitRepoManagement(
                    self.repo_url, 
                    self.target_dir,
                    branch=self.current_branch,
                    workdir=self.aio_folder
                )
            result = self.repo_management.get_remote_branches()
            if result is None:
                return None
            return result or [DEFAULT_BOTS_BRANCH]
        except Exception as e:
            logger.error(f"Error fetching branches: {e}", exc_info=True)
            return None

    def install_or_update(self, branch: str) -> None:
        """Install or update repository from specified branch."""
        if self.installer_thread and self.installer_thread.is_alive():
            logger.warning("Install/update already in progress - skipping")
            return
        if not branch:
            logger.error("Invalid branch name: empty string")
            return

        # Persist user choice immediately (even before install succeeds)
        self.save_branch(branch)

        logger.info(f"Starting install/update for branch: {branch}")
        self.installer_thread = threading.Thread(
            target=self._do_install_update,
            args=(branch,),
            name=f"XBridgeBotInstaller-{branch}",
            daemon=True
        )
        self.installer_thread.start()
        logger.info(f"Started installer thread: {self.installer_thread.name}")

    def _do_install_update(self, branch: str) -> None:
        """Implementation of repository installation/update."""
        # Detect broken state before switch (for post-repair)
        try:
            from utilities.repo_repair import detect_broken_state, repair_broken_worktree
            broken_info = detect_broken_state(self.target_dir_path)
            has_broken = broken_info.get("broken", False)
        except Exception:
            has_broken = False
            broken_info = {}

        try:
            logger.info(f"Starting install/update for {branch}")
            self.repo_management = GitRepoManagement(
                self.repo_url, 
                self.target_dir,
                branch=branch,
                workdir=self.aio_folder
            )
            
            if not self.target_dir_path.exists():
                logger.info(f"Creating repo directory: {self.target_dir}")
                self.target_dir_path.mkdir(parents=True, exist_ok=True)

            logger.info(f"Setting up repository...")
            self.repo_management.setup()

            # Post-repair: archive orphan config_bak_* and restore user configs verbatim
            if has_broken:
                try:
                    from utilities.repo_repair import repair_broken_worktree
                    report = repair_broken_worktree(
                        self.target_dir_path,
                        aio_folder=Path(self.aio_folder),
                        branch=branch,
                    )
                    logger.info(f"Repair completed: {report}")
                except Exception as repair_e:
                    logger.error(f"Post-repair failed: {repair_e}", exc_info=True)

            # Success: truthfully record branch
            self.current_branch = branch
            self.save_branch(branch)
            self.last_error = None
            logger.info(f"Successfully updated repository to branch: {branch}")
        except BranchSwitchBlockedError as e:
            self.last_error = str(e)
            logger.error(f"Branch switch blocked: {e} blocked_paths={getattr(e, 'blocked_paths', [])}", exc_info=True)
            self.installer_thread = None
            self.deferred_start = False
            return
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Repository update failed: {str(e)}", exc_info=True)
            logger.debug(f"Repository URL: {self.repo_url}")
            logger.debug(f"Target directory: {self.target_dir}")
            logger.debug(f"Branch: {branch}")
            self.installer_thread = None
            self.deferred_start = False
            return
        finally:
            if self.deferred_start:
                self.deferred_start = False
                if self.repo_management and self.last_error is None:
                    logger.debug("Triggering deferred execution post-install")
                    self._start_execution()

    def delete_local_repo(self) -> None:
        """Delete local repository."""
        if not self.repo_exists():
            logger.warning("No repository found to delete")
            return

        try:
            import shutil
            logger.info(f"Deleting repository at: {self.target_dir}")
            shutil.rmtree(self.target_dir)
            self.repo_management = None
            self.current_branch = DEFAULT_BOTS_BRANCH
            self.save_branch(DEFAULT_BOTS_BRANCH)
            logger.info("Repository deleted successfully")
        except Exception as e:
            logger.error(f"Repository delete failed: {str(e)}", exc_info=True)

    def toggle_execution(self, branch: Optional[str] = None) -> None:
        """Toggle trading bots execution state without blocking GUI."""
        logger.info("Toggling bot execution")
        use_branch = branch or self.current_branch
        
        if self.installer_thread and self.installer_thread.is_alive():
            logger.info("Deferring execution until installation completes")
            self.deferred_start = True
            return
            
        needs_install = (
            not self.repo_exists() or 
            self.repo_management is None or
            branch != self.current_branch
        )
            
        if needs_install:
            logger.info("Starting installation before execution")
            self.deferred_start = True
            self.install_or_update(use_branch)
        else:
            if self.process and self.process.poll() is None:
                self._stop_execution()
            else:
                self._start_execution()

    def _start_execution(self) -> None:
        """Start bots execution in background thread."""
        if not self.repo_management:
            logger.error("Cannot start execution - repo management not initialized")
            return

        if self.process is not None and self.process.poll() is None:
            logger.info("Bots already running")
            return

        try:
            logger.info("Starting bots execution")
            self.process = self.repo_management.run_script("main_gui.py")
            if self.process:
                logger.info(f"Started bots with PID: {self.process.pid}")
                self.started = True
            else:
                logger.error("Failed to start bots - no process returned")
        except Exception as e:
            logger.error(f"Error starting bots: {str(e)}", exc_info=True)

    def _stop_execution(self) -> None:
        """Stop bots with timeout handling."""
        if not self.process:
            return
            
        logger.info("Stopping bots execution")
        try:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except TimeoutExpired:
                logger.warning("Process not terminating, forcing kill")
                self.process.kill()
                self.process.wait()
        except Exception as e:
            logger.error(f"Error stopping bots: {e}", exc_info=True)
        finally:
            self.process = None
            self.started = False
            logger.info("Bots stopped")
