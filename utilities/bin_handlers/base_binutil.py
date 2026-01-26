import logging
import os
import subprocess
import sys
import tarfile
import zipfile
from typing import Optional

import psutil
import requests

from utilities.app_container import get_container, AppContainer

# from utilities.helper_util import UtilityHelper
logger = logging.getLogger(__name__)


class BaseBinUtil:
    def __init__(self, app_name: str, container: Optional[AppContainer] = None):
        self.executable_path: Optional[str] = None
        self.dmg_mount_path: Optional[str] = None
        self.app_name = app_name
        self.binary_percent_download: Optional[float] = None
        self.downloading_bin = False
        self.system = os.name
        self.process = None
        self.container = container or get_container()

    def download_binary(self, url: str, tmp_filename: str, exe_path: str, extract_path: str) -> None:
        self.downloading_bin = True
        try:
            aio_folder = self.container.aio_folder
            if aio_folder is None:
                raise ValueError("AIO folder not configured")
            self.download_file(
                url,
                os.path.join(aio_folder, tmp_filename),
                exe_path,
                extract_path,
                self.system,
                "binary_percent_download",
                self
            )
        finally:
            self.downloading_bin = False

    def download_file(self, url, tmp_path, final_path, extract_to, system, progress_attr, instance):
        logger.info(f"Starting download from {url}")
        try:
            response = requests.get(url, stream=True, timeout=(10, 30))
            response.raise_for_status()

            remote_size = int(response.headers.get('Content-Length', 0))
            with open(tmp_path, 'wb') as f:
                bytes_downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        if progress_attr and instance:
                            setattr(instance, progress_attr, (bytes_downloaded / remote_size) * 100)
                            # logger.debug(f"Downloaded {bytes_downloaded}/{remote_size} bytes")

            if os.path.getsize(tmp_path) != remote_size:
                os.remove(tmp_path)
                raise ValueError("Download size mismatch")
            logger.info(f"File downloaded successfully to {tmp_path}")
        except PermissionError as e:
            logger.error(f"Permission error writing file: {e}")
            raise

        if url.endswith(".zip"):
            # Skip extraction for empty files
            if os.path.getsize(tmp_path) > 0:
                with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                    # Use handler class name to determine extraction method
                    handler_class = instance.__class__.__name__

                    # Blocknet preserves internal folder structure
                    if handler_class == "BlocknetHandler":
                        zip_ref.extractall(extract_to)
                        logger.info(f"Extracted Blocknet ZIP directly to {extract_to}")
                        # XLite/BlockDX create new archive-named subfolders
                    elif handler_class in ["XliteHandler", "BlockDXHandler"]:
                        archive_name = os.path.splitext(os.path.basename(url))[0]
                        target_path = os.path.join(extract_to, archive_name)
                        os.makedirs(target_path, exist_ok=True)
                        zip_ref.extractall(target_path)
                        logger.info(f"Extracted {handler_class} to new folder {target_path}")
                        # Other handlers use default extraction
                    else:
                        zip_ref.extractall(extract_to)
                        logger.info(f"Extracted {handler_class} ZIP to {extract_to}")

            os.remove(tmp_path)
        elif url.endswith(".tar.gz"):
            with tarfile.open(tmp_path, 'r:gz') as tar:
                tar.extractall(extract_to)
            os.remove(tmp_path)
            logger.info(f"Extracted TAR.GZ file to {extract_to}")
        elif url.endswith(".dmg") and self.container.system == "Darwin":
            os.rename(tmp_path, final_path)
            logger.info(f"Renamed DMG file to {final_path}")

    def start_process(self, command, cwd=None, env_vars=None, dmg_path=None,
                      mount_point=None):  # Prepare environment variables if provided
        if not command:
            raise ValueError("Command list cannot be empty")

        if env_vars:
            full_env = os.environ.copy()
            full_env.update(env_vars)
        else:
            full_env = None

        self.process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=full_env,
            start_new_session=True
        )
        return self.process

    def graceful_terminate(self, timeout=10):
        if not self.process:
            logger.info("No running process to terminate")
            return

        try:
            self.process.terminate()
            self.process.wait(timeout=timeout)
            logger.info(f"Closed {self.app_name}")
            self.process = None
        except subprocess.TimeoutExpired:
            logger.info(f"Force terminating {self.app_name}")
            self.force_kill()
            logger.info(f"{self.app_name} has been force terminated")
            self.process = None

    def force_kill(self):
        if self.process:
            try:
                self.process.kill()
                logger.info(f"Killed {self.app_name}")
                self.process = None
            except Exception as e:
                logger.error(f"Error killing {self.app_name}: {e}")

    def terminate_processes(self, pids, name):
        if not pids:
            logger.warning(f"No PIDs to terminate for {name}")
            return

        for pid in pids:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                proc.wait(timeout=10)
                logger.info(f"Process {name} PID {pid} terminated successfully")
            except (psutil.NoSuchProcess, psutil.TimeoutExpired) as e:
                if isinstance(e, psutil.TimeoutExpired):
                    try:
                        proc = psutil.Process(pid)
                        proc.kill()
                    except Exception:
                        pass
                    logger.warning(f"Process {name} PID {pid}: Timeout expired, killed process")
                else:
                    logger.warning(f"Process {name} PID {pid}: {str(e)}")
    
    def download_standalone_binary(self, url: str, target_path: str) -> bool:
        """Download non-archive binaries with security checks"""
        temp_path = f"{target_path}.tmp"
        try:
            target_dir = os.path.dirname(target_path)
            os.makedirs(target_dir, exist_ok=True)

            # Only download if doesn't exist
            if not os.path.exists(target_path):
                logger.info(f"Downloading {url}")
                response = requests.get(url, stream=True, timeout=30)
                response.raise_for_status()

                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                # Atomic replace
                os.replace(temp_path, target_path)

                # Set executable permissions
                if sys.platform in ["linux", "darwin"]:
                    os.chmod(target_path, 0o755)

                logger.info(f"Binary saved to {target_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Download failed: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False

    # Shared by BlockdxUtility and XliteUtility
    def handle_dmg(self, action: str) -> None:
        if self.container.system != "Darwin":
            logger.warning(f"Call handle_dmg with wrong OS, {self.container.system} ?")
            return
        if action == "mount":
            if self.dmg_mount_path and not os.path.ismount(self.dmg_mount_path):
                if self.executable_path:
                    subprocess.run(["hdiutil", "attach", self.executable_path], check=True)
                    logger.info(f"Mounted DMG {self.executable_path} to {self.dmg_mount_path}")
            elif self.dmg_mount_path:
                logger.warning(f"{self.dmg_mount_path} is already mounted")
        elif action == "unmount":
            if self.dmg_mount_path and os.path.ismount(self.dmg_mount_path):
                subprocess.run(["hdiutil", "detach", self.dmg_mount_path], check=True)
                logger.info(f"Unmounted DMG from {self.dmg_mount_path}")
            else:
                logger.warning(f"{self.dmg_mount_path or 'Unknown path'} is not mounted")
