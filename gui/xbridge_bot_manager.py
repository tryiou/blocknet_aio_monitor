import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, cast
from subprocess import TimeoutExpired

from utilities.git_repo_management import GitRepoManagement
from utilities.app_container import get_container

logger = logging.getLogger(__name__)


class XBridgeBotManager:
    """Manages installation and execution of XBridge trading bots."""
    
    def __init__(self, current_branch: str = "main") -> None:
        self.author = "tryiou"
        self.repo_name = "xbridge_trading_bots"
        self.repo_url = f"https://github.com/{self.author}/{self.repo_name}"
        container = get_container()
        aio_folder = container.aio_folder
        if not aio_folder:
            raise ValueError("AIO folder not configured")
        self.aio_folder = cast(str, aio_folder)  # Type assertion - __post_init__ ensures it's set
        self.target_dir_path = Path(self.aio_folder) / "xbridge_trading_bots"
        self.target_dir = str(self.target_dir_path)  # For GitRepoManagement (expects str)
        self.started = False
        self.current_branch = current_branch
        self.repo_management: Optional[GitRepoManagement] = None
        self.installer_thread: Optional[threading.Thread] = None
        self.process: Optional[subprocess.Popen] = None
        self.deferred_start = False  # New flag for deferred execution

    def repo_exists(self) -> bool:
        """Check if bot repository exists locally."""
        return self.target_dir_path.exists() and (self.target_dir_path / ".git").is_dir()

    def get_available_branches(self) -> List[str]:
        """Get list of available branches from remote."""
        try:
            if self.repo_management is None:
                self.repo_management = GitRepoManagement(
                    self.repo_url, 
                    self.target_dir,
                    branch=self.current_branch,
                    workdir=self.aio_folder
                )
            return self.repo_management.get_remote_branches() or ["main"]
        except Exception as e:
            logger.error(f"Error fetching branches: {e}", exc_info=True)
            return ["main"]

    def install_or_update(self, branch: str) -> None:
        """Install or update repository from specified branch."""
        if self.installer_thread and self.installer_thread.is_alive():
            logger.warning("Install/update already in progress - skipping")
            return
        if not branch:
            logger.error("Invalid branch name: empty string")
            return

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
            self.current_branch = branch
            logger.info(f"Successfully updated repository to branch: {branch}")
        except Exception as e:
            logger.debug(f"Repository URL: {self.repo_url}")
            logger.debug(f"Target directory: {self.target_dir}")
            logger.debug(f"Branch: {branch}")
            if "conflict prevents checkout" in str(e) or "conflicts prevent checkout" in str(e):
                logger.warning("Detected config conflict during update")
                self.handle_config_folder_rename()
            else:
                logger.error(f"Repository update failed: {str(e)}", exc_info=True)
            self.installer_thread = None
            self.deferred_start = False  # Reset deferred flag on failure   
        finally:
            # Start execution if flag was set
            if self.deferred_start:
                self.deferred_start = False
                if self.repo_management:  # Only start if installation succeeded
                    logger.debug("Triggering deferred execution post-install")
                    self._start_execution()

    def handle_config_folder_rename(self) -> None:
        """Resolve config conflicts by renaming folder."""
        config_path = self.target_dir_path / "config"
        if not config_path.exists():
            logger.warning("Config directory not found, cannot resolve conflict")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config_bak_path = self.target_dir_path / f"config_bak_{timestamp}"

        try:
            os.rename(str(config_path), str(config_bak_path))
            logger.info(f"Renamed config to resolve conflict: {config_bak_path}")
            
            if self.repo_management:
                logger.info("Retrying setup after config rename")
                self.repo_management.setup()
                logger.info("Setup completed after conflict resolution")
        except Exception as e:
            logger.error(f"Failed to resolve config conflict: {str(e)}")

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
            self.current_branch = "main"
            logger.info("Repository deleted successfully")
        except Exception as e:
            logger.error(f"Repository delete failed: {str(e)}", exc_info=True)

    def toggle_execution(self, branch: Optional[str] = None) -> None:
        """Toggle trading bots execution state without blocking GUI."""
        logger.info("Toggling bot execution")
        use_branch = branch or self.current_branch
        
        # Check if installation in progress and defer execution
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
                self.process.wait(timeout=10)  # 10 second timeout
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
