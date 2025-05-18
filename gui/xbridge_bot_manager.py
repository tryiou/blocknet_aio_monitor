import logging
import os
import subprocess
import threading

from utilities.git_repo_management import GitRepoManagement
from utilities.global_variables import aio_folder


class XBridgeBotManager:
    def __init__(self, repo_url: str = "https://github.com/tryiou/xbridge_trading_bots", current_branch: str = "main"):
        self.repo_url = repo_url
        self.target_dir = os.path.join(aio_folder, "xbridge_trading_bots")
        self.execution_enabled = False
        self.current_branch = current_branch
        self.repo_management = GitRepoManagement(self.repo_url, self.target_dir, branch=self.current_branch,
                                                 workdir=aio_folder)
        self.thread = None
        self.process = None

    def repo_exists(self) -> bool:
        return os.path.exists(os.path.join(self.target_dir, ".git"))

    def get_available_branches(self) -> list:
        """Return list of available branches from remote repo"""
        try:
            if not self.repo_exists():
                return ["main"]

            if not self.repo_management:
                self.repo_management = GitRepoManagement(self.repo_url, self.target_dir, branch=self.current_branch,
                                                         workdir=aio_folder)
            return self.repo_management.get_remote_branches()
        except Exception as e:
            logging.error(f"Error fetching branches: {e}")
            return ["main"]

    def install_or_update(self, branch: str) -> None:
        """Install or update repo from given branch"""

        if self.thread and self.thread.is_alive():
            logging.warning("Install/update already in progress")
            return

        if not branch or not isinstance(branch, str):
            logging.error(f"Invalid branch: {branch}")
            return

        logging.info(f"Starting install/update for branch: {branch}")
        self.thread = threading.Thread(
            target=self._do_install_update,
            args=(branch,),
            name=f"XBridgeBotInstaller-{branch}"
        )
        self.thread.start()
        # self.thread.join()
        logging.info(f"Started installer thread {self.thread.name}")

    def _do_install_update(self, branch: str) -> None:
        try:
            logging.info(f"Attempting to install/update from {self.repo_url} to {self.target_dir}")
            self.repo_management = GitRepoManagement(self.repo_url, self.target_dir, branch=branch,
                                                     workdir=aio_folder)

            if not os.path.exists(self.target_dir):
                logging.info(f"Creating target directory: {self.target_dir}")
                os.makedirs(self.target_dir, exist_ok=True)

            self.repo_management.setup()
            self.current_branch = branch
            logging.info(f"Successfully updated to branch {branch}")
        except Exception as e:
            logging.error(f"Failed to update: {str(e)}", exc_info=True)
            logging.debug(f"Repository URL: {self.repo_url}")
            logging.debug(f"Target directory: {self.target_dir}")
            logging.debug(f"Branch: {branch}")

    def delete_local_repo(self) -> None:
        """Delete local repository"""
        if self.repo_exists():
            try:
                logging.info(f"Attempting to delete repository at {self.target_dir}")
                import shutil
                if os.path.exists(self.target_dir):
                    shutil.rmtree(self.target_dir)
                    logging.info("Successfully deleted repository")
                else:
                    logging.warning("Delete requested but directory does not exist")

                # Reset state
                self.repo_management = None
                self.current_branch = "main"
            except Exception as e:
                logging.error(f"Failed to delete repository: {str(e)}", exc_info=True)

    def toggle_execution(self) -> bool:
        """Toggle script execution state. Returns new state"""
        if not self.repo_exists():
            self.install_or_update(self.current_branch)

        self.execution_enabled = not self.execution_enabled
        if self.execution_enabled:
            self._start_execution()
        else:
            self._stop_execution()
        return self.execution_enabled

    def _start_execution(self) -> None:
        """Start script execution in background"""
        if self.thread and self.thread.is_alive():
            return

        self.thread = threading.Thread(target=self._run_script)
        self.thread.start()

    def _stop_execution(self) -> None:
        """Stop script execution"""
        if self.repo_management and self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                logging.info("Script execution stopped")
                self.process = None
            except Exception as e:
                logging.error(f"Error stopping script: {e}")

    def _run_script(self) -> None:
        """Internal method to run the script"""
        try:
            if self.repo_management:
                logging.info(f"Attempting to run script gui_pingpong.py in {self.target_dir}")
                self.process = self.repo_management.run_script("gui_pingpong.py")
                if self.process:
                    logging.info(f"Script started with PID: {self.process.pid}")
                else:
                    logging.error("Failed to start script - no process returned")
            else:
                logging.error("Cannot run script - repo management not initialized")
        except Exception as e:
            logging.error(f"Error executing script: {str(e)}", exc_info=True)
