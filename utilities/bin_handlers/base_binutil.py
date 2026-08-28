import logging
import os
import subprocess
import sys
import tarfile
import zipfile

import psutil
import requests

from gui.constants import DOWNLOAD_CHUNK_SIZE, RPC_TIMEOUT_S
from utilities.app_container import AppContainer, get_container

# from utilities.helper_util import UtilityHelper
logger = logging.getLogger(__name__)


def _is_mocked_path(p) -> bool:
    """Return True if path looks like a MagicMock repr (e.g. \"<MagicMock name='mock.aio_folder' ...>\").

    Guards against os.makedirs(Path(str(MagicMock))) creating real folders named "<MagicMock ...>".
    """
    if p is None:
        return False
    try:
        s = str(p)
        return s.startswith("<MagicMock") or "MagicMock" in s
    except Exception:
        return True


class BaseBinUtil:
    def __init__(self, app_name: str, container: AppContainer | None = None):
        self.executable_path: str | None = None
        self.dmg_mount_path: str | None = None
        self.app_name = app_name
        self.binary_percent_download: float | None = None
        self.downloading_bin = False
        self.system = os.name
        self.process = None
        self.container = container or get_container()
        # for error reporting (issue #14)
        self._stderr_log_path: str | None = None
        self._stderr_file_handle = None
        self._last_command: list | None = None
        self._last_cwd: str | None = None

    def download_binary(self, url: str, tmp_filename: str, exe_path: str, extract_path: str) -> None:
        self.downloading_bin = True
        try:
            aio_folder = self.container.aio_folder
            if aio_folder is None:
                raise ValueError("AIO folder not configured")
            if _is_mocked_path(aio_folder):
                logger.debug("Skipping download_binary for mocked aio_folder %s", aio_folder)
                return
            # Also guard extract_path which may be derived from mocked aio_folder
            if _is_mocked_path(extract_path):
                logger.debug("Skipping download_binary for mocked extract_path %s", extract_path)
                return
            self.download_file(
                url,
                os.path.join(aio_folder, tmp_filename),
                exe_path,
                extract_path,
                self.system,
                "binary_percent_download",
                self,
            )
        finally:
            self.downloading_bin = False

    def download_file(self, url, tmp_path, final_path, extract_to, system, progress_attr, instance):
        # Guard mocked paths before any FS ops (would otherwise create "<MagicMock ...>" folders)
        if _is_mocked_path(tmp_path) or _is_mocked_path(final_path) or _is_mocked_path(extract_to):
            logger.debug(
                "Skipping download_file for mocked path tmp=%s final=%s extract=%s",
                tmp_path,
                final_path,
                extract_to,
            )
            # For MagicMock paths, skip entirely to avoid creating real "<MagicMock ...>" directories.
            return
        logger.info(f"Starting download from {url}")
        try:
            response = requests.get(url, stream=True, timeout=(RPC_TIMEOUT_S, 30))
            response.raise_for_status()

            remote_size = int(response.headers.get("Content-Length", 0))
            with open(tmp_path, "wb") as f:
                bytes_downloaded = 0
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        if progress_attr and instance:
                            if remote_size:
                                setattr(instance, progress_attr, (bytes_downloaded / remote_size) * 100)
                            else:
                                setattr(instance, progress_attr, 0)
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
                with zipfile.ZipFile(tmp_path, "r") as zip_ref:
                    # Use handler class name to determine extraction method
                    handler_class = instance.__class__.__name__

                    # Blocknet preserves internal folder structure
                    if handler_class == "BlocknetHandler":
                        if _is_mocked_path(extract_to):
                            logger.debug("Skipping mocked extract_to %s", extract_to)
                        else:
                            zip_ref.extractall(extract_to)  # noqa: S202 # trusted Blocknet archive
                        logger.info(f"Extracted Blocknet ZIP directly to {extract_to}")
                        # XLite/BlockDX create new archive-named subfolders
                    elif handler_class in ["XliteHandler", "BlockDXHandler"]:
                        archive_name = os.path.splitext(os.path.basename(url))[0]
                        target_path = os.path.join(extract_to, archive_name)
                        if _is_mocked_path(target_path) or _is_mocked_path(extract_to):
                            logger.debug("Skipping mocked target_path %s", target_path)
                        else:
                            os.makedirs(target_path, exist_ok=True)
                            zip_ref.extractall(target_path)  # noqa: S202 # trusted archive
                        logger.info(f"Extracted {handler_class} to new folder {target_path}")
                        # Other handlers use default extraction
                    else:
                        if _is_mocked_path(extract_to):
                            logger.debug("Skipping mocked extract_to %s", extract_to)
                        else:
                            zip_ref.extractall(extract_to)  # noqa: S202 # trusted archive
                        logger.info(f"Extracted {handler_class} ZIP to {extract_to}")

            os.remove(tmp_path)
        elif url.endswith(".tar.gz"):
            try:
                with tarfile.open(tmp_path, "r:gz") as tar:
                    try:
                        if _is_mocked_path(extract_to):
                            logger.debug("Skipping mocked tar extract_to %s", extract_to)
                        else:
                            tar.extractall(extract_to, filter="data")
                    except (
                        tarfile.AbsoluteLinkError,
                        tarfile.AbsolutePathError,
                        tarfile.LinkOutsideDestinationError,
                        tarfile.OutsideDestinationError,
                        tarfile.FilterError,
                        tarfile.TarError,
                    ):
                        for member in tar.getmembers():
                            try:
                                if _is_mocked_path(extract_to):
                                    logger.debug("Skipping mocked tar member extract %s", extract_to)
                                    continue
                                tar.extract(member, path=extract_to, filter="data")
                            except (
                                tarfile.AbsoluteLinkError,
                                tarfile.AbsolutePathError,
                                tarfile.LinkOutsideDestinationError,
                                tarfile.OutsideDestinationError,
                                tarfile.FilterError,
                                tarfile.TarError,
                            ) as e:
                                logger.warning(f"Skipping tar member {member.name}: {e}")
                            except Exception as e:
                                logger.warning(f"Skipping tar member {member.name}: {e}")
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception as e:  # debug logged
                        logger.debug("Suppressed Exception: %s", e, exc_info=True)
            logger.info(f"Extracted TAR.GZ file to {extract_to}")
        elif url.endswith(".dmg") and self.container.system == "Darwin":
            os.rename(tmp_path, final_path)
            logger.info(f"Renamed DMG file to {final_path}")

    def start_process(
        self, command, cwd=None, env_vars=None, dmg_path=None, mount_point=None
    ):  # Prepare environment variables if provided
        if not command:
            raise ValueError("Command list cannot be empty")

        if env_vars:
            full_env = os.environ.copy()
            full_env.update(env_vars)
        else:
            full_env = None

        # Capture stderr to a per-app log file for error reporting (issue #14).
        # Keep file handle open so child can write after Popen; close in graceful_terminate.
        stderr_log_path = None
        stderr_file = None
        try:
            aio_folder = self.container.aio_folder
            if aio_folder:
                if _is_mocked_path(aio_folder):
                    logger.debug("Skipping mocked aio_folder for stderr log %s", aio_folder)
                    self._stderr_log_path = None
                    self._stderr_file_handle = None
                else:
                    os.makedirs(aio_folder, exist_ok=True)
                    stderr_log_path = os.path.join(aio_folder, f"{self.app_name.lower()}_launch.log")
                    # truncate previous launch log
                    stderr_file = open(  # noqa: SIM115 # keep handle open for Popen
                        stderr_log_path, "w", encoding="utf-8", errors="replace"
                    )
                    self._stderr_log_path = stderr_log_path
                    self._stderr_file_handle = stderr_file
            else:
                self._stderr_log_path = None
                self._stderr_file_handle = None
        except Exception as e:
            logger.debug(f"Failed to open stderr log file: {e}")
            stderr_file = None
            self._stderr_log_path = None
            self._stderr_file_handle = None

        # If we have a file, use it; otherwise fall back to DEVNULL
        # (preserve old behavior for tests where folder is mocked)
        stderr_dest = stderr_file if stderr_file is not None else subprocess.DEVNULL

        # store context before Popen so exception reports contain it
        self._last_command = list(command) if isinstance(command, (list, tuple)) else [str(command)]
        self._last_cwd = cwd

        try:
            self.process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr_dest,
                env=full_env,
                start_new_session=True,
            )
        except Exception:
            # Close handle on failure to avoid FD leak (P0)
            if stderr_file is not None:
                try:
                    stderr_file.close()
                except Exception as e:  # debug logged
                    logger.debug("Suppressed Exception: %s", e, exc_info=True)
                self._stderr_file_handle = None
            raise
        return self.process

    def get_stderr_snippet(self, max_lines: int = 80, max_chars: int = 4000) -> str:
        """Read last lines of the launch log for reporting."""
        path = getattr(self, "_stderr_log_path", None)
        if not path or not os.path.exists(path):
            return ""
        try:
            # ensure data flushed
            fh = getattr(self, "_stderr_file_handle", None)
            if fh:
                try:
                    fh.flush()
                    try:
                        os.fsync(fh.fileno())
                    except Exception as e:  # debug logged
                        logger.debug("Suppressed Exception: %s", e, exc_info=True)
                except Exception as e:  # debug logged
                    logger.debug("Suppressed Exception: %s", e, exc_info=True)
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
                if not content.strip():
                    return ""
                # truncate by chars then lines
                if len(content) > max_chars:
                    content = content[-max_chars:]
                lines = content.splitlines()
                if len(lines) > max_lines:
                    lines = lines[-max_lines:]
                return "\n".join(lines)
        except Exception as e:
            logger.debug(f"Failed to read stderr log {path}: {e}")
            return ""

    def get_launch_context(self) -> dict:
        """Return last launch context for error reporting."""
        return {
            "command": getattr(self, "_last_command", None),
            "cwd": getattr(self, "_last_cwd", None),
            "stderr": self.get_stderr_snippet(),
            "executable": self.executable_path,
            "app_name": self.app_name,
            "stderr_log_path": getattr(self, "_stderr_log_path", None),
        }

    def graceful_terminate(self, timeout=10):
        if not self.process:
            logger.info("No running process to terminate")
            self._close_stderr_handle()
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
        finally:
            self._close_stderr_handle()

    def _close_stderr_handle(self):
        fh = getattr(self, "_stderr_file_handle", None)
        if fh:
            try:
                fh.close()
            except Exception as e:  # debug logged
                logger.debug("Suppressed Exception: %s", e, exc_info=True)
            self._stderr_file_handle = None

    def force_kill(self):
        if self.process:
            try:
                self.process.kill()
                logger.info(f"Killed {self.app_name}")
                self.process = None
            except Exception as e:
                logger.error(f"Error killing {self.app_name}: {e}")
        self._close_stderr_handle()

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
                    except Exception as e:  # debug logged
                        logger.debug("Suppressed Exception: %s", e, exc_info=True)
                    logger.warning(f"Process {name} PID {pid}: Timeout expired, killed process")
                else:
                    logger.warning(f"Process {name} PID {pid}: {str(e)}")

    def download_standalone_binary(self, url: str, target_path: str) -> bool:
        """Download non-archive binaries with security checks"""
        if _is_mocked_path(target_path):
            logger.debug("Skipping download_standalone_binary for mocked target_path %s", target_path)
            return False
        temp_path = f"{target_path}.tmp"
        try:
            target_dir = os.path.dirname(target_path)
            if _is_mocked_path(target_dir):
                logger.debug("Skipping mocked target_dir %s", target_dir)
            else:
                os.makedirs(target_dir, exist_ok=True)

            # Only download if doesn't exist
            if not os.path.exists(target_path):
                logger.info(f"Downloading {url}")
                response = requests.get(url, stream=True, timeout=30)  # keep 30s for standalone
                response.raise_for_status()

                with open(temp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)

                # Atomic replace
                os.replace(temp_path, target_path)

                # Set executable permissions
                if sys.platform in ["linux", "darwin"]:
                    os.chmod(target_path, 0o755)  # noqa: S103 # intentional executable

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
