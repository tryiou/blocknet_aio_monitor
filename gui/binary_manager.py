import errno
import logging
import os
import queue
import shutil
import threading
import time
from pathlib import Path
from threading import Thread

import customtkinter as ctk
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

try:
    from watchdog.observers.polling import PollingObserver
except ImportError:
    PollingObserver = None  # type: ignore

import widgets_strings
from gui.binary_frame_manager import BinaryFrameManager
from utilities import utils
from utilities.app_container import get_container

logger = logging.getLogger(__name__)


class BinaryFileHandler(FileSystemEventHandler):
    """
    Handles file modification events with rate limiting for binary updates.
    """

    def __init__(self, binary_manager: "BinaryManager"):
        """
        Initializes the handler.
        :param binary_manager: The manager responsible for binary updates.
        """
        super().__init__()
        self.binary_manager: BinaryManager = binary_manager
        self.max_delay: float = 5  # seconds
        self.last_run: float = 0
        self.scheduled: bool = False

    def on_modified(self, event: "FileSystemEvent") -> None:
        """
        Called when a file is modified. Schedules binary update after delay.
        """
        if self.scheduled:
            return

        time_since_last = time.time() - self.last_run
        delay_seconds = max(0, self.max_delay - time_since_last)
        delay_ms = int(delay_seconds * 1000)

        self.scheduled = True
        # Use thread-safe queue instead of direct after() call
        self.binary_manager.file_change_queue.put(("delayed_update", delay_ms))

    def schedule_delayed_task(self, delay_ms):
        # Only the main thread should execute after()
        if threading.current_thread().name == "MainThread":
            self.binary_manager.root_gui.after(delay_ms, self._execute_scheduled)
        else:
            # Schedule through queue if in worker thread
            self.binary_manager.file_change_queue.put(("delayed_task", delay_ms))

    def _execute_scheduled(self) -> None:
        """
        Executes the scheduled update and resets the schedule flag.
        """
        # Run file handling through main thread only
        self.binary_manager.check_and_update_aio_folder()
        self.last_run = time.time()
        self.scheduled = False


class BinaryManager:
    def __init__(self, root_gui):
        self.root_gui = root_gui
        self.frame_manager = None
        self.container = get_container()

        self.disable_start_blocknet_button = False
        self.disable_start_xlite_button = False
        self.disable_start_blockdx_button = False

        self.download_blocknet_thread = None
        self.download_blockdx_thread = None
        self.download_xlite_thread = None

        self.tooltip_manager = self.root_gui.tooltip_manager
        self.file_change_queue = queue.Queue()
        self.last_directory_mtime = 0  # Added tracker
        self._reported_failures: set = set()
        self._inotify_fallback_active = False
        self._poll_after_id = None

        aio_folder = self.container.aio_folder
        self.handler = BinaryFileHandler(self) if aio_folder else None
        self.observer = self._create_observer(aio_folder)

        self.process_file_changes()
        # If observer unavailable, ensure periodic mtime poll still updates UI
        if self.observer is None and aio_folder:
            # start periodic poll (2000ms) as fallback — mirrors update_all_binary_buttons cadence
            try:
                self._poll_after_id = self.root_gui.after(2000, self._poll_aio_folder)
            except Exception as e:  # debug logged
                logger.debug("Suppressed Exception: %s", e, exc_info=True)

    def _create_observer(self, aio_folder) -> object | None:
        """Create file watcher with ENOSPC fallback to PollingObserver (2.0s)."""
        if not aio_folder or not self.handler:
            return None
        # Try inotify first, then polling
        for cls, name, kwargs in [
            (Observer, "inotify", {}),
            (PollingObserver, "polling", {"timeout": 2.0} if PollingObserver else {}),
        ]:
            if cls is None:
                continue
            obs = None
            try:
                obs = cls(**kwargs) if kwargs else cls()
                obs.schedule(self.handler, aio_folder, recursive=False)
                obs.start()
                if name == "polling":
                    self._inotify_fallback_active = True
                    logger.warning("Inotify watch limit reached — using PollingObserver (2.0s) fallback")
                    self._show_enospc_hint()
                else:
                    logger.info(f"File watcher started with {name} for {aio_folder}")
                return obs
            except OSError as e:
                # Handle ENOSPC even when wrapped in WatchDogError
                err_no = getattr(e, "errno", None)
                cause_no = getattr(getattr(e, "__cause__", None), "errno", None)
                if err_no == errno.ENOSPC or cause_no == errno.ENOSPC:
                    logger.warning(
                        f"{name} observer failed: inotify watch limit reached ({e}), trying fallback", exc_info=True
                    )
                    if obs is not None:
                        try:
                            obs.stop()
                            obs.join(0.5)
                        except Exception as e:  # debug logged
                            logger.debug("Suppressed Exception: %s", e, exc_info=True)
                    continue
                logger.error(f"Observer {name} failed: {e}", exc_info=True)
                raise
            except Exception as e:
                # Also check for WatchDogError wrapping ENOSPC
                cause = getattr(e, "__cause__", None)
                if getattr(e, "errno", None) == errno.ENOSPC or getattr(cause, "errno", None) == errno.ENOSPC:
                    logger.warning(
                        f"{name} observer failed: inotify watch limit reached ({e}), trying fallback", exc_info=True
                    )
                    if obs is not None:
                        try:
                            obs.stop()
                            obs.join(0.5)
                        except Exception as e:  # debug logged
                            logger.debug("Suppressed Exception: %s", e, exc_info=True)
                    continue
                logger.error(f"Observer {name} failed: {e}", exc_info=True)
                raise
        # Both failed — will use periodic mtime poll only
        logger.warning(
            "File watcher unavailable (ENOSPC even for polling) — falling back to periodic mtime polling (2000ms)"
        )
        self._inotify_fallback_active = True
        self._show_enospc_hint()
        return None

    def _poll_aio_folder(self) -> None:
        """Periodic mtime poll when observer is unavailable (2000ms)."""
        try:
            if hasattr(self.root_gui, "winfo_exists") and not self.root_gui.winfo_exists():
                return
        except Exception:
            return
        try:
            self.check_and_update_aio_folder()
        except Exception as e:
            logger.debug(f"Periodic poll failed: {e}")
        try:
            self._poll_after_id = self.root_gui.after(2000, self._poll_aio_folder)
        except Exception as e:  # debug logged
            logger.debug("Suppressed Exception: %s", e, exc_info=True)

    def stop(self) -> None:
        """Stop observer cleanly (call from on_close)."""
        # Cancel periodic poll
        poll_id = getattr(self, "_poll_after_id", None)
        if poll_id is not None:
            try:
                self.root_gui.after_cancel(poll_id)
            except Exception as e:  # debug logged
                logger.debug("Suppressed Exception: %s", e, exc_info=True)
            self._poll_after_id = None
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(1)
                logger.info("File watcher stopped")
            except Exception as e:
                logger.debug(f"Error stopping observer: {e}")
            self.observer = None

    def _show_enospc_hint(self):
        """Show one-time copyable hint for ENOSPC with current limit (for #14 dialog)."""
        try:
            # Read current limit dynamically
            cur = "unknown"
            try:
                cur = Path("/proc/sys/fs/inotify/max_user_watches").read_text().strip()
            except Exception as e:  # debug logged
                logger.debug("Suppressed Exception: %s", e, exc_info=True)
            cmd = (  # sudo command, not wrapped
                f"echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf && sudo sysctl -p  # current {cur}"  # noqa: E501
            )
            # Log with copyable command; GUI will also show via error_report if needed
            logger.warning(f"Inotify limit hit (current {cur}). Fix (click to copy): {cmd}")
            # Schedule a one-time popup via error_report dialog if GUI ready
            try:
                from gui.error_report_dialog import show_error_report

                # Use after to ensure main thread
                def _show():
                    try:
                        show_error_report(
                            self.root_gui,
                            app_name="File Watcher",
                            returncode=28,
                            command=["inotify", "watch", "limit"],
                            cwd=self.container.aio_folder,
                            stderr_text=f"inotify watch limit reached (current {cur})",
                            executable_path=None,
                            extra_info=f"Fix (click to copy): {cmd}",
                        )
                    except Exception as ex:
                        logger.debug(f"ENOSPC hint dialog failed: {ex}")

                # Defer slightly to let GUI init
                self.root_gui.after(1500, _show)
            except Exception as e:  # debug logged
                logger.debug("Suppressed Exception: %s", e, exc_info=True)
        except Exception as e:
            logger.debug(f"Failed to show ENOSPC hint: {e}")

    async def setup(self):
        self.frame_manager = BinaryFrameManager(self)

        self.root_gui.after(0, self.check_and_update_aio_folder)
        self.root_gui.after(0, self.update_all_binary_buttons)
        self.root_gui.after(0, self.update_xbridge_bots_buttons)

    def _start_or_close_binary(
        self,
        process_running: bool,
        stop_func: callable,
        start_func: callable,
        button: ctk.CTkButton,
        disable_flag: str,
        app_name: str = "",
        handler=None,
    ) -> None:
        """
        Starts or stops a binary process and updates UI state accordingly.
        When starting, monitors the launched process for early failure (return code !=0)
        and shows a copy-pasteable error report dialog (issue #14).

        Args:
            process_running: Indicates if the binary process is currently running
            stop_func: Function to call for stopping the process
            start_func: Function to call for starting the process
            button: The UI button being processed
            disable_flag: Attribute name for the button disable flag
            app_name: Human readable name for reporting
            handler: Utility handler instance (with process / get_launch_context)
        """
        img = self.root_gui.stop_greyed_img if process_running else self.root_gui.start_greyed_img
        utils.disable_button(button, img=img)
        setattr(self, disable_flag, True)
        if process_running:
            Thread(target=stop_func, daemon=True).start()
        else:
            # Wrap start_func to catch immediate launch exceptions (e.g., ENOENT, Permission)
            def _wrapped_start():
                try:
                    start_func()
                except Exception as e:
                    logger.error(f"Launch exception for {app_name}: {e}", exc_info=True)
                    # Try to get context from handler if available
                    cmd = None
                    cwd = None
                    exe = None
                    stderr = str(e)
                    if handler and hasattr(handler, "get_launch_context"):
                        try:
                            ctx = handler.get_launch_context()
                            cmd = ctx.get("command")
                            cwd = ctx.get("cwd")
                            exe = ctx.get("executable")
                            # prefer captured stderr if any, else exception
                            if ctx.get("stderr"):
                                stderr = ctx.get("stderr") + f"\nException: {e}"
                        except Exception as ex:
                            logger.debug(f"Failed to get launch context: {ex}")
                    # schedule dialog on main thread
                    try:
                        from gui.error_report_dialog import show_error_report

                        show_error_report(
                            self.root_gui,
                            app_name=app_name or "Application",
                            returncode=None,
                            command=cmd,
                            cwd=cwd,
                            stderr_text=stderr,
                            executable_path=exe,
                            extra_info=f"Exception type: {type(e).__name__}",
                        )
                    except Exception as dlg_e:
                        logger.error(f"Failed to show error dialog: {dlg_e}", exc_info=True)
                else:
                    # No exception: schedule poll check for early exit (e.g., return code 127)
                    if handler is not None and app_name:
                        # use default args to avoid late binding
                        self.root_gui.after(1500, lambda a=app_name, h=handler: self._check_launch_failure(a, h))
                        self.root_gui.after(4000, lambda a=app_name, h=handler: self._check_launch_failure(a, h))

            Thread(target=_wrapped_start, daemon=True).start()
        self.root_gui.after(self.root_gui.time_disable_button, self._enable_binary_start_button, disable_flag)

    def _check_launch_failure(self, app_name: str, handler) -> None:
        """Check if a just-launched process has already terminated with error."""
        try:
            # avoid checking after GUI destroyed
            try:
                if hasattr(self.root_gui, "winfo_exists") and not self.root_gui.winfo_exists():
                    return
            except Exception:
                return
            # handler.process is the BaseBinUtil.process or handler-specific attribute
            proc = getattr(handler, "process", None)
            # also check for app-specific process attrs (blocknet_process, blockdx_process, xlite_process)
            if proc is None:
                for attr in ("blocknet_process", "blockdx_process", "xlite_process"):
                    proc = getattr(handler, attr, None)
                    if proc is not None:
                        break
            if proc is None:
                return
            rc = proc.poll()
            if rc is None:
                return  # still running
            if rc == 0:
                return  # clean exit (user closed quickly, not an error)
            # de-dupe: avoid double dialog from 1.5s and 4s checks
            pid = getattr(proc, "pid", "n/a")
            key = f"{app_name}:{id(proc)}:{pid}:{rc}"
            if key in self._reported_failures:
                return
            self._reported_failures.add(key)
            # bound set to avoid unbounded growth
            if len(self._reported_failures) > 100:
                self._reported_failures.clear()
            # non-zero -> failure
            ctx = {}
            if hasattr(handler, "get_launch_context"):
                try:
                    ctx = handler.get_launch_context()
                except Exception as ex:
                    logger.debug(f"Failed to get launch context: {ex}")
                    ctx = {}
            from gui.error_report_dialog import show_error_report

            show_error_report(
                self.root_gui,
                app_name=app_name,
                returncode=rc,
                command=ctx.get("command"),
                cwd=ctx.get("cwd"),
                stderr_text=ctx.get("stderr") or "",
                executable_path=ctx.get("executable"),
                extra_info=(
                    f"Process terminated shortly after launch (code {rc}). "
                    f"If this repeats, copy this report to {widgets_strings.github_issue_url}"
                ),
            )
            logger.warning(f"{app_name} launch failed with code {rc}")
        except Exception as e:
            logger.error(f"Failed to check launch failure for {app_name}: {e}", exc_info=True)

    def _enable_binary_start_button(self, disable_flag):
        setattr(self, disable_flag, False)

    def start_or_close_blocknet(self):
        if not self.root_gui.blocknet_manager.blocknet_process_running:
            self.root_gui.blocknet_manager.check_config()
        self._start_or_close_binary(
            process_running=self.root_gui.blocknet_manager.blocknet_process_running,
            stop_func=self.root_gui.blocknet_manager.utility.close_blocknet,
            start_func=self.root_gui.blocknet_manager.utility.start_blocknet,
            button=self.frame_manager.blocknet_start_close_button,
            disable_flag="disable_start_blocknet_button",
            app_name="Blocknet Core",
            handler=self.root_gui.blocknet_manager.utility,
        )

    def start_or_close_blockdx(self):
        if not self.root_gui.blockdx_manager.process_running:
            self.root_gui.blockdx_manager.blockdx_check_config()
        self._start_or_close_binary(
            process_running=self.root_gui.blockdx_manager.process_running,
            stop_func=self.root_gui.blockdx_manager.utility.close_blockdx,
            start_func=self.root_gui.blockdx_manager.utility.start_blockdx,
            button=self.frame_manager.blockdx_start_close_button,
            disable_flag="disable_start_blockdx_button",
            app_name="Block-DX",
            handler=self.root_gui.blockdx_manager.utility,
        )

    def start_or_close_xlite(self):
        env_vars = []
        if not self.root_gui.xlite_manager.process_running and self.root_gui.stored_password:
            env_vars.append(f"CC_WALLET_PASS={self.root_gui.stored_password}")
            env_vars.append("CC_WALLET_AUTOLOGIN=true")

        self._start_or_close_binary(
            process_running=self.root_gui.xlite_manager.process_running,
            stop_func=self.root_gui.xlite_manager.utility.close_xlite,
            start_func=lambda: self.root_gui.xlite_manager.utility.start_xlite(env_vars=env_vars),
            button=self.frame_manager.xlite_toggle_execution_button,
            disable_flag="disable_start_xlite_button",
            app_name="XLite",
            handler=self.root_gui.xlite_manager.utility,
        )

    def install_delete_blocknet_command(self):
        blocknet_boolvar = self.frame_manager.blocknet_installed_boolvar.get()
        if blocknet_boolvar:
            self.delete_blocknet_command()
        else:
            self.download_blocknet_command()

    def download_blocknet_command(self):
        utils.disable_button(self.frame_manager.install_delete_blocknet_button, img=self.root_gui.install_greyed_img)
        self.download_blocknet_thread = Thread(
            target=self.root_gui.blocknet_manager.utility.download_blocknet_bin, daemon=True
        )
        self.download_blocknet_thread.start()

    def delete_blocknet_command(self):
        blocknet_pruned_version = self.root_gui.blocknet_manager.version[0].replace("v", "")
        aio_folder = self.container.aio_folder
        if not aio_folder:
            return
        for item in os.listdir(aio_folder):
            item_path = os.path.join(aio_folder, item)
            # if a wrong version is found, delete it.
            if os.path.isdir(item_path) and "blocknet-" in item and blocknet_pruned_version in item:
                logger.info(f"deleting {item_path}")
                shutil.rmtree(item_path)

    def install_delete_blockdx_command(self):
        blockdx_boolvar = self.frame_manager.blockdx_installed_boolvar.get()
        if blockdx_boolvar:
            self.delete_blockdx_command()
        else:
            self.download_blockdx_command()

    def download_blockdx_command(self):
        utils.disable_button(self.frame_manager.install_delete_blockdx_button, img=self.root_gui.install_greyed_img)
        self.download_blockdx_thread = Thread(
            target=self.root_gui.blockdx_manager.utility.download_blockdx_bin, daemon=True
        )
        self.download_blockdx_thread.start()

    def delete_blockdx_command(self):
        blockdx_pruned_version = self.root_gui.blockdx_manager.version[0].replace("v", "")
        aio_folder = self.container.aio_folder
        if not aio_folder:
            return
        for item in os.listdir(aio_folder):
            item_path = os.path.join(aio_folder, item)
            if self.container.system == "Darwin":
                blockdx_filename = os.path.basename(self.container.blockdx_release_url or "")
                if os.path.isfile(item_path) and blockdx_filename in item_path:
                    self.root_gui.blockdx_manager.unmount_dmg()
                    os.remove(item_path)
            else:
                if os.path.isdir(item_path) and "BLOCK-DX-" in item and blockdx_pruned_version in item:
                    logger.info(f"deleting {item_path}")
                    shutil.rmtree(item_path)

    def install_delete_xlite_command(self):
        xlite_boolvar = self.frame_manager.xlite_installed_boolvar.get()
        if xlite_boolvar:
            self.delete_xlite_command()
        else:
            self.download_xlite_command()

    def download_xlite_command(self):
        utils.disable_button(self.frame_manager.install_delete_xlite_button, img=self.root_gui.install_greyed_img)
        self.download_xlite_thread = Thread(target=self.root_gui.xlite_manager.utility.download_xlite_bin, daemon=True)
        self.download_xlite_thread.start()

    def delete_xlite_command(self):
        xlite_pruned_version = self.root_gui.xlite_manager.version[0].replace("v", "")
        aio_folder = self.container.aio_folder
        if not aio_folder:
            return
        for item in os.listdir(aio_folder):
            item_path = os.path.join(aio_folder, item)
            if self.container.system == "Darwin":
                xlite_filename = os.path.basename(self.container.xlite_release_url or "")
                if os.path.isfile(item_path) and xlite_filename in item_path:
                    self.root_gui.xlite_manager.utility.unmount_dmg()
                    os.remove(item_path)
            else:
                if os.path.isdir(item_path) and "XLite-" in item and xlite_pruned_version in item:
                    logger.info(f"deleting {item_path}")
                    shutil.rmtree(item_path)

    def get_directory_mtime(self) -> int:
        """
        Retrieves the last modified time of the AIO directory with nanosecond
        precision where available, falling back to second precision on FAT filesystems.

        Returns:
            int: Directory modification time in nanoseconds
        """
        aio_folder = self.container.aio_folder
        if not aio_folder:
            return 0
        try:
            stat_info = os.stat(aio_folder)
            try:
                return stat_info.st_mtime_ns
            except AttributeError:
                return int(stat_info.st_mtime * 1_000_000_000)
        except OSError as e:
            logger.warning(f"Directory stat error: {e}", exc_info=True)
            return 0

    def scan_directory_for_binaries(self, apps_info: dict) -> None:
        """
        Scans the AIO folder directory and updates the found status of each application.

        Args:
            apps_info: Dictionary containing app information structures
        """
        aio_folder = self.container.aio_folder
        if not aio_folder:
            return
        for base_name in os.listdir(aio_folder):
            full_path = os.path.join(aio_folder, base_name)
            for app_info in apps_info.values():
                if self._is_item_match(app_info, base_name, full_path):
                    self._check_app_version(app_info, base_name, full_path)

    def _is_item_match(self, app_info: dict, base_name: str, full_path: str) -> bool:
        """
        Determines if a directory item matches the expected pattern for an application.

        Args:
            app_info: Application information structure
            base_name: The base name of the directory item
            full_path: The full path to the directory item

        Returns:
            bool: True if item matches the application's pattern, False otherwise
        """
        if app_info["is_dir"] and os.path.isdir(full_path):
            return app_info["dir_prefix"] in base_name
        elif not app_info["is_dir"]:
            darwin_file = app_info.get("darwin_file")
            if not darwin_file:
                return False
            return darwin_file in base_name
        return False

    def check_and_update_aio_folder(self) -> None:
        """
        Checks the AIO folder contents and updates installation statuses.

        Compares directory modification timestamps to skip redundant checks,
        scans for installed binaries, and updates UI state accordingly.
        """
        current_mtime = self.get_directory_mtime()
        if current_mtime == self.last_directory_mtime:
            return

        self.last_directory_mtime = current_mtime
        is_darwin = self.container.system == "Darwin"

        apps_info = {
            "blocknet": {
                "version": self._prune_version(self.root_gui.blocknet_manager.version),
                "dir_prefix": "blocknet-",
                "is_dir": True,
                "darwin_file": None,
                "boolvar": self.frame_manager.blocknet_installed_boolvar,
                "found": False,
            },
            "blockdx": {
                "version": self._prune_version(self.root_gui.blockdx_manager.version),
                "dir_prefix": "BLOCK-DX-",
                "is_dir": not is_darwin,
                "darwin_file": os.path.basename(self.container.blockdx_release_url or "") if is_darwin else None,
                "boolvar": self.frame_manager.blockdx_installed_boolvar,
                "found": False,
            },
            "xlite": {
                "version": self._prune_version(self.root_gui.xlite_manager.version),
                "dir_prefix": "XLite-",
                "is_dir": not is_darwin,
                "darwin_file": os.path.basename(self.container.xlite_release_url or "") if is_darwin else None,
                "boolvar": self.frame_manager.xlite_installed_boolvar,
                "found": False,
            },
        }

        self.scan_directory_for_binaries(apps_info)

        for app_info in apps_info.values():
            app_info["boolvar"].set(app_info["found"])

    def _prune_version(self, version):
        """Remove 'v' prefix from version string."""
        return version[0].replace("v", "")

    def _log_incorrect_target(self, target: str) -> None:
        """
        Logs incorrect binary version found in directory scan.

        Args:
            target: Path to the incorrect binary version
        """
        logger.info(f"incorrect version: {target}")

    def _check_app_version(self, app_info, item, full_path):
        """Check if the item matches the expected version for the given app."""
        if app_info["is_dir"] and os.path.isdir(full_path):
            # Directory check for non-Darwin or blocknet
            if app_info["version"] in item:
                app_info["found"] = True
            else:
                self._log_incorrect_target(full_path)
        elif not app_info["is_dir"] and os.path.isfile(full_path):
            # File check for Darwin (macOS) for blockdx and xlite
            darwin_file = app_info.get("darwin_file")
            if not darwin_file:
                self._log_incorrect_target(full_path)
                return
            if darwin_file in item:
                app_info["found"] = True
            else:
                self._log_incorrect_target(full_path)

    def _update_install_delete_button(
        self, binary_name, bool_var, button, string_var, manager, release_url, folder_path, process_running_attr_name
    ):
        """
        Updates the install/delete button for a given binary.
        """
        is_installed = bool_var.get()
        percent_download = manager.utility.binary_percent_download
        downloading = manager.utility.downloading_bin
        dl_string = f"{int(percent_download)}%" if percent_download is not None else ""
        display_text = dl_string if downloading else ""
        if is_installed:
            display_text = ""
            self.tooltip_manager.update_tooltip(widget=button, msg=folder_path)
            button_condition = getattr(manager, process_running_attr_name) or downloading
        else:
            self.tooltip_manager.update_tooltip(widget=button, msg=release_url)
            button_condition = downloading

        if button_condition:
            utils.disable_button(
                button, img=self.root_gui.delete_greyed_img if is_installed else self.root_gui.install_greyed_img
            )
        else:
            utils.enable_button(button, img=self.root_gui.delete_img if is_installed else self.root_gui.install_img)

        string_var.set(display_text)

    def update_binary_buttons(self, binary_name):
        """
        Updates buttons related to a specific binary (install/delete and start/close).
        """
        if binary_name == "blocknet":
            self.update_blocknet_start_close_button()
            folder_path = os.path.join(self.container.aio_folder or "", self.container.conf_data.blocknet_bin_path[0])
            self._update_install_delete_button(
                binary_name,
                self.frame_manager.blocknet_installed_boolvar,
                self.frame_manager.install_delete_blocknet_button,
                self.frame_manager.install_delete_blocknet_string_var,
                self.root_gui.blocknet_manager,
                self.container.blocknet_release_url,
                folder_path,
                "blocknet_process_running",
            )
        elif binary_name == "blockdx":
            self.update_blockdx_start_close_button()
            folder_path = os.path.join(self.container.aio_folder or "", self.container.blockdx_curpath or "")
            self._update_install_delete_button(
                binary_name,
                self.frame_manager.blockdx_installed_boolvar,
                self.frame_manager.install_delete_blockdx_button,
                self.frame_manager.install_delete_blockdx_string_var,
                self.root_gui.blockdx_manager,
                self.container.blockdx_release_url,
                folder_path,
                "process_running",
            )
        elif binary_name == "xlite":
            self.update_xlite_start_close_button()
            folder_path = os.path.join(self.container.aio_folder or "", self.container.xlite_curpath or "")
            self._update_install_delete_button(
                binary_name,
                self.frame_manager.xlite_installed_boolvar,
                self.frame_manager.install_delete_xlite_button,
                self.frame_manager.install_delete_xlite_string_var,
                self.root_gui.xlite_manager,
                self.container.xlite_release_url,
                folder_path,
                "process_running",
            )

    def process_file_changes(self) -> None:
        """
        Processes file change events from a thread-safe queue.

        Continuously checks for file system events and schedules corresponding
        UI updates in the main thread.
        """
        try:
            while True:
                msg_type, param = self.file_change_queue.get_nowait()
                if msg_type == "delayed_update" or msg_type == "delayed_task":
                    self.root_gui.after(param, self.handler._execute_scheduled)
        except queue.Empty:
            pass
        self.root_gui.after(100, self.process_file_changes)

    def update_all_binary_buttons(self):
        """
        Updates all binary-related buttons.
        """
        if not self.root_gui.winfo_exists():
            return
        self.update_binary_buttons("blocknet")
        self.update_binary_buttons("blockdx")
        self.update_binary_buttons("xlite")
        self.root_gui.after(2000, self.update_all_binary_buttons)

    def update_blocknet_start_close_button(self):
        var = (
            widgets_strings.close_string
            if self.root_gui.blocknet_manager.blocknet_process_running
            else widgets_strings.start_string
        )
        self.frame_manager.blocknet_start_close_button_string_var.set(var)

        if self.root_gui.blocknet_manager.blocknet_process_running:
            self.tooltip_manager.update_tooltip(
                widget=self.frame_manager.blocknet_start_close_button, msg=widgets_strings.close_string
            )
        else:
            self.tooltip_manager.update_tooltip(
                widget=self.frame_manager.blocknet_start_close_button, msg=widgets_strings.start_string
            )

        enabled = (
            not self.root_gui.blocknet_manager.utility.downloading_bin
            and not self.frame_manager.parent.disable_start_blocknet_button
            and not self.root_gui.blocknet_manager.utility.bootstrap_checking
        )
        if enabled:
            img = (
                self.root_gui.stop_img
                if self.root_gui.blocknet_manager.blocknet_process_running
                else self.root_gui.start_img
            )
            utils.enable_button(self.frame_manager.blocknet_start_close_button, img=img)
        else:
            img = (
                self.root_gui.stop_greyed_img
                if self.root_gui.blocknet_manager.blocknet_process_running
                else self.root_gui.start_greyed_img
            )
            utils.disable_button(self.frame_manager.blocknet_start_close_button, img=img)

    def update_blockdx_start_close_button(self):
        # blockdx_start_close_button_string_var
        var = (
            widgets_strings.close_string
            if self.root_gui.blockdx_manager.process_running
            else widgets_strings.start_string
        )
        self.frame_manager.blockdx_start_close_button_string_var.set(var)

        enabled = (
            self.root_gui.blockdx_manager.process_running
            or (
                not self.root_gui.blockdx_manager.utility.downloading_bin
                and self.root_gui.blocknet_manager.utility.valid_rpc
            )
            and not self.frame_manager.parent.disable_start_blockdx_button
        )
        if enabled:
            if self.root_gui.blockdx_manager.process_running:
                self.tooltip_manager.update_tooltip(
                    widget=self.frame_manager.blockdx_start_close_button, msg=widgets_strings.close_string
                )
                img = self.root_gui.stop_img
            else:
                self.tooltip_manager.update_tooltip(
                    widget=self.frame_manager.blockdx_start_close_button, msg=widgets_strings.start_string
                )
                img = self.root_gui.start_img
            utils.enable_button(self.frame_manager.blockdx_start_close_button, img=img)

        else:
            if self.root_gui.blockdx_manager.process_running:
                img = self.root_gui.stop_greyed_img
                self.tooltip_manager.update_tooltip(
                    widget=self.frame_manager.blockdx_start_close_button, msg=widgets_strings.close_string
                )
            else:
                self.tooltip_manager.update_tooltip(
                    widget=self.frame_manager.blockdx_start_close_button,
                    msg=widgets_strings.blockdx_missing_blocknet_config_string,
                )
                img = self.root_gui.start_greyed_img
            utils.disable_button(self.frame_manager.blockdx_start_close_button, img=img)

    def update_xlite_start_close_button(self):
        # xlite_start_close_button_string_var
        var = (
            widgets_strings.close_string
            if self.root_gui.xlite_manager.process_running
            else widgets_strings.start_string
        )
        self.frame_manager.xlite_toggle_execution_string_var.set(var)

        if self.root_gui.xlite_manager.process_running:
            self.tooltip_manager.update_tooltip(
                widget=self.frame_manager.xlite_toggle_execution_button, msg=widgets_strings.close_string
            )
        else:
            self.tooltip_manager.update_tooltip(
                widget=self.frame_manager.xlite_toggle_execution_button, msg=widgets_strings.start_string
            )

        # xlite_start_close_button
        disable_start_close_button = (
            self.root_gui.xlite_manager.utility.downloading_bin or self.disable_start_xlite_button
        )

        if not disable_start_close_button:
            img = self.root_gui.stop_img if self.root_gui.xlite_manager.process_running else self.root_gui.start_img
            # self.xlite_start_close_button.configure(image=img)
            utils.enable_button(self.frame_manager.xlite_toggle_execution_button, img=img)
        else:
            img = (
                self.root_gui.stop_greyed_img
                if self.root_gui.xlite_manager.process_running
                else self.root_gui.start_greyed_img
            )
            utils.disable_button(self.frame_manager.xlite_toggle_execution_button, img=img)

    def update_xbridge_bots_buttons(self):
        if not self.root_gui.winfo_exists():
            return
        # XBridge Bots
        self.update_xbridge_bots_start_close_button()
        self.update_xbridge_bots_install_delete_button()

        if (
            self.frame_manager.xbridge_bot_manager.process
            and self.frame_manager.xbridge_bot_manager.process.poll() is not None
        ):
            self.frame_manager.xbridge_bot_manager.process = None

        # Schedule next update
        self.root_gui.after(2000, self.update_xbridge_bots_buttons)

    def update_xbridge_bots_install_delete_button(self):
        bots_boolvar = self.frame_manager.bots_installed_boolvar.get()
        # if bots_boolvar:
        # self.tooltip_manager.update_tooltip(widget=self.frame_manager.install_delete_bots_button,
        #                                     msg=self.frame_manager.xbridge_bot_manager.target_dir)
        button_condition = (
            self.frame_manager.xbridge_bot_manager.process
            or self.frame_manager.xbridge_bot_manager.installer_thread
            and self.frame_manager.xbridge_bot_manager.installer_thread.is_alive()
        )
        # else:
        #     # self.tooltip_manager.update_tooltip(widget=self.frame_manager.install_delete_bots_button,
        #     #                                     msg=self.frame_manager.xbridge_bot_manager.repo_url)
        #     button_condition = (  # noqa: E501 # long logic, commented
        #         self.frame_manager.xbridge_bot_manager.process
        #         or self.frame_manager.xbridge_bot_manager.installer_thread
        #         and self.frame_manager.xbridge_bot_manager.installer_thread.is_alive()
        #     )

        # Set install/delete button image based on state
        if button_condition:
            utils.disable_button(
                self.frame_manager.install_delete_bots_button,
                img=self.root_gui.delete_greyed_img if bots_boolvar else self.root_gui.install_greyed_img,
            )
        else:
            utils.enable_button(
                self.frame_manager.install_delete_bots_button,
                img=self.root_gui.delete_img if bots_boolvar else self.root_gui.install_img,
            )

    def update_xbridge_bots_start_close_button(self):
        # Update tooltip message
        if self.frame_manager.xbridge_bot_manager.process:
            self.tooltip_manager.update_tooltip(
                widget=self.frame_manager.bots_toggle_execution_button, msg=widgets_strings.close_string
            )
        else:
            self.tooltip_manager.update_tooltip(
                widget=self.frame_manager.bots_toggle_execution_button, msg=widgets_strings.start_string
            )

            # Determine if button should be enabled/disabled based on download status
        disable_start_close_button = (
            self.frame_manager.xbridge_bot_manager.installer_thread
            and self.frame_manager.xbridge_bot_manager.installer_thread.is_alive()
        )
        # or not self.frame_manager.xbridge_bot_manager.repo_management.venv

        if not disable_start_close_button:
            img = self.root_gui.stop_img if self.frame_manager.xbridge_bot_manager.process else self.root_gui.start_img
            utils.enable_button(self.frame_manager.bots_toggle_execution_button, img=img)
        else:
            img = (
                self.root_gui.stop_greyed_img
                if self.frame_manager.xbridge_bot_manager.process
                else self.root_gui.start_greyed_img
            )
            utils.disable_button(self.frame_manager.bots_toggle_execution_button, img=img)

    def update_xbridge_bots_version_optionmenu(self):
        branches = self.frame_manager.xbridge_bot_manager.get_available_branches()
        if branches is not None:
            self.frame_manager.bots_version_optionmenu.configure(values=branches)
