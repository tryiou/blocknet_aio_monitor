import logging
import os
import platform
import signal
import sys

from cryptography.fernet import InvalidToken as FernetInvalidToken

# Early environment validation before Tk imports (issue #26: no console debugging)
try:
    from utilities.environment import show_startup_error, validate_or_exit

    validate_or_exit()
except SystemExit:
    raise
except Exception as e:
    # Fallback: log and continue, later imports will show dialog
    logging.getLogger(__name__).error(f"Environment validation failed: {e}", exc_info=True)

# GUI imports — wrapped to show native dialog if Tk/pygit2 missing
try:
    import customtkinter as ctk
    from PIL import Image
except Exception as e:
    try:
        from utilities.environment import _current_py_mm, _tk_fix_commands, show_startup_error

        py_mm = _current_py_mm()
        tk_cmds = _tk_fix_commands()
        details = (
            f"Failed to import GUI library: {e}\n\n"
            f"System: {platform.system()} {platform.machine()} / Python {platform.python_version()}\n\n"
            "Fix — click to copy:\n" + "\n".join(f"  {c}" for c in tk_cmds)
        )
        show_startup_error(
            "Missing GUI dependency",
            f"Failed to import GUI library: {e}",
            details,
        )
    except Exception:
        print(f"Failed to import GUI library: {e}", file=sys.stderr)
    sys.exit(1)

try:
    import widgets_strings
    from gui.binary_manager import BinaryManager
    from gui.blockdx_manager import BlockDXManager
    from gui.blocknet_manager import BlocknetManager
    from gui.tooltip_manager import TooltipManager
    from gui.xlite_manager import XliteManager
    from utilities import utils
    from utilities.app_container import get_container
except Exception as e:
    try:
        from utilities.environment import _current_py_mm, show_startup_error

        py_mm = _current_py_mm()
        details = (
            f"Failed to load application modules: {e}\n\n"
            f"System: {platform.system()} {platform.machine()} / "
            f"Python {platform.python_version()} ({sys.executable})\n\n"
            f"Try recreating venv: {sys.executable} -m venv venv && "
            f"{sys.executable} -m pip install -r requirements.txt\n"
            f"Or with versioned Python: python{py_mm} -m venv venv\n"
            f"Report: https://github.com/tryiou/blocknet_aio_monitor/issues/new"
        )
        show_startup_error(
            "Startup failed",
            f"Failed to load application modules: {e}",
            details,
        )
    except Exception:
        print(f"Failed to load modules: {e}", file=sys.stderr)
    sys.exit(1)

# Create or get the root logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)  # Set the logging level to DEBUG

# Create a console handler (prints to stdout)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Create a formatter and set it for the handler
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)

# Add the handler to the logger (only once to avoid duplicate logs)
if not logger.hasHandlers():
    logger.addHandler(console_handler)

asyncio_logger = logging.getLogger("asyncio")
asyncio_logger.setLevel(logging.WARNING)
pil_logger = logging.getLogger("PIL")
pil_logger.setLevel(logging.WARNING)
urllib3_logger = logging.getLogger("urllib3")
urllib3_logger.setLevel(logging.WARNING)
urllib3_logger = logging.getLogger("watchdog")
urllib3_logger.setLevel(logging.WARNING)

from gui.constants import (
    INTERVAL_PROCESS_CHECK_MS,
    MAIN_FRAMES_STICKY,
    TIME_DISABLE_BUTTON_MS,
    TITLE_FRAMES_STICKY,
    tooltip_bg_color,
)
from gui.ui_sync_controller import UiSyncController

container = get_container()
theme_path = container.theme_path
if theme_path:
    ctk.set_default_color_theme(theme_path)
else:
    logger.error("Theme path not configured")


class BlocknetAioGui(ctk.CTk):
    """Main GUI class for Blocknet AIO application."""

    def __init__(self):
        """Initialize the Blocknet AIO GUI application."""
        super().__init__()
        self.install_greyed_img = None
        self.install_img = None
        self.delete_greyed_img = None
        self.delete_img = None
        self.stop_greyed_img = None
        self.stop_img = None
        self.start_greyed_img = None
        self.start_img = None
        self.transparent_img = None
        self.theme_img = None

        self.disable_daemons_conf_check: bool = False

        self.cfg: dict = utils.load_cfg_json()
        self.adjust_theme()
        self.custom_path: str = None
        self.stored_password: str = None
        if self.cfg:
            if "custom_path" in self.cfg:
                self.custom_path = self.cfg["custom_path"]
            if "xl_pass" in self.cfg:
                try:
                    # Decrypt password using keyring (migration handled in load_cfg_json)
                    self.stored_password = utils.decrypt_password(self.cfg["xl_pass"])
                except Exception as e:
                    logger.error(f"Error decrypting XLite password: {e} ({type(e).__name__})", exc_info=True)
                    self.stored_password = None
                    # Only clear persisted xl_pass on InvalidToken (stale key/cipher mismatch);
                    # other exceptions (e.g. TypeError) indicate programming error, not stale data.
                    if isinstance(e, FernetInvalidToken):
                        try:
                            utils.remove_cfg_json_key("xl_pass")
                            logger.info("Cleared stale xl_pass after InvalidToken — please Store Password again")
                        except Exception as ce:
                            logger.error(f"Failed to clear stale xl_pass: {ce}", exc_info=True)

        self.time_disable_button: int = TIME_DISABLE_BUTTON_MS

        self._closing: bool = False
        self._after_ids: list[str] = []
        self._check_processes_after_id: str | None = None
        self.ui_sync: UiSyncController | None = None

        self.tooltip_manager: TooltipManager = TooltipManager(self)

        self.blocknet_manager: BlocknetManager = BlocknetManager(self)
        self.binary_manager: BinaryManager = BinaryManager(self)
        self.blockdx_manager: BlockDXManager = BlockDXManager(self)
        self.xlite_manager: XliteManager = XliteManager(self)

    def setup_management_sections(self) -> None:
        """Initialize and setup all management sections synchronously."""
        self.binary_manager.setup()
        self.blocknet_manager.setup()
        self.blockdx_manager.setup()
        self.xlite_manager.setup()

    def _track_after(self, after_id: str | None) -> str | None:
        """Track after ID for later cancellation."""
        if after_id is not None:
            self._after_ids.append(after_id)
            if after_id == self._check_processes_after_id or self._check_processes_after_id is None:
                # keep generic list; check_processes tracked separately via assignment
                pass
        return after_id

    def _cancel_all_afters(self) -> None:
        """Cancel all tracked afters, guarded by winfo_exists and TclError."""
        for aid in list(self._after_ids):
            try:
                if hasattr(self, "winfo_exists"):
                    try:
                        if not self.winfo_exists():
                            break
                    except Exception:
                        break
                self.after_cancel(aid)
            except Exception as e:  # TclError or ValueError if already cancelled
                logger.debug(f"after_cancel failed for {aid}: {e}")
        self._after_ids.clear()
        # Also try to cancel check_processes id if not in list (legacy)
        if self._check_processes_after_id is not None:
            try:
                if hasattr(self, "winfo_exists"):
                    try:
                        if self.winfo_exists():
                            self.after_cancel(self._check_processes_after_id)
                    except Exception as e:  # debug logged
                        logger.debug(f"Suppressed Exception: {e}", exc_info=True)
                else:
                    self.after_cancel(self._check_processes_after_id)
            except Exception as e:  # debug logged
                logger.debug(f"after_cancel check_processes failed: {e}")
            self._check_processes_after_id = None

    def _deferred_network_init(self) -> None:
        """Deferred network-heavy init off critical path (branch fetch, etc)."""
        try:
            # BinaryFrameManager already defers branch fetch via Thread;
            # Keep hook for future network deferrals (e.g., manifest refresh)
            pass
        except Exception as e:
            logger.debug(f"Deferred network init failed: {e}")

    def init_setup(self) -> None:
        """Initialize the GUI setup, including layout, images, and frame configuration."""
        self.title(widgets_strings.app_title_string)
        self.resizable(False, False)
        self.setup_load_images()
        aid = self.after(0, self.check_processes)
        self._track_after(aid)
        self.setup_management_sections()
        self.setup_tooltips()
        self.init_grid()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        # Deferred network off critical path
        try:
            self.after(100, self._deferred_network_init)
        except Exception as e:
            logger.debug(f"Deferred network schedule failed: {e}")
        # Start unified scheduler (replaces individual 2000ms loops)
        try:
            self.ui_sync = UiSyncController(self)
            self.ui_sync.start()
        except Exception as e:
            logger.debug(f"UiSync start failed: {e}")
        try:
            signal.signal(signal.SIGINT, self.handle_signal)
        except ValueError as e:
            logger.debug(f"SIGINT handler not set: {e}")
        try:
            signal.signal(signal.SIGTERM, self.handle_signal)
        except (ValueError, AttributeError, OSError) as e:
            logger.debug(f"SIGTERM handler not set (Windows/bypass): {e}")

    def setup_load_images(self) -> None:
        """Load and set up images for use in the GUI."""
        resize = (65, 30)
        self.theme_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(container.dirpath, "img", "light.png")).resize(
                resize, Image.Resampling.LANCZOS
            ),
            dark_image=Image.open(os.path.join(container.dirpath, "img", "dark.png")).resize(
                resize, Image.Resampling.LANCZOS
            ),
            size=resize,
        )
        resize = (50, 50)
        self.transparent_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(container.dirpath, "img", "transparent.png")).resize(
                resize, Image.Resampling.LANCZOS
            )
        )
        self.start_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(container.dirpath, "img", "start-50.png")).resize(
                resize, Image.Resampling.LANCZOS
            )
        )
        self.start_greyed_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(container.dirpath, "img", "start-50_greyed.png")).resize(
                resize, Image.Resampling.LANCZOS
            )
        )
        self.stop_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(container.dirpath, "img", "stop-50.png")).resize(
                resize, Image.Resampling.LANCZOS
            )
        )
        self.stop_greyed_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(container.dirpath, "img", "stop-50_greyed.png")).resize(
                resize, Image.Resampling.LANCZOS
            )
        )
        self.delete_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(container.dirpath, "img", "delete-50.png")).resize(
                resize, Image.Resampling.LANCZOS
            )
        )
        self.delete_greyed_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(container.dirpath, "img", "delete-50_greyed.png")).resize(
                resize, Image.Resampling.LANCZOS
            )
        )
        self.install_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(container.dirpath, "img", "installer-50.png")).resize(
                resize, Image.Resampling.LANCZOS
            )
        )
        self.install_greyed_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(container.dirpath, "img", "installer-50_greyed.png")).resize(
                resize, Image.Resampling.LANCZOS
            )
        )

    def setup_tooltips(self) -> None:
        """Set up tooltips for various GUI components."""
        self.tooltip_manager.register_tooltip(
            self.blocknet_manager.frame_manager.master_frame,
            msg=widgets_strings.tooltip_howtouse,
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.blockdx_manager.frame_manager.master_frame,
            msg=widgets_strings.tooltip_howtouse,
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.xlite_manager.frame_manager.master_frame,
            msg=widgets_strings.tooltip_howtouse,
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.binary_manager.frame_manager.master_frame,
            msg=widgets_strings.tooltip_howtouse,
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.binary_manager.frame_manager.title_frame,
            msg=widgets_strings.tooltip_bins_title_msg,
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.binary_manager.frame_manager.header_label,
            msg=widgets_strings.tooltip_bins_title_msg,
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.xlite_manager.frame_manager.xlite_label,
            msg=widgets_strings.tooltip_xlite_label_msg,
            delay=1.0,
            border_width=2,
            follow=True,
            bg_color=tooltip_bg_color,
        )
        self.tooltip_manager.register_tooltip(
            self.binary_manager.frame_manager.blocknet_label,
            msg=widgets_strings.tooltip_blocknet_core_label_msg,
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.binary_manager.frame_manager.blockdx_label,
            msg=widgets_strings.tooltip_blockdx_label_msg,
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.binary_manager.frame_manager.xlite_label,
            msg=widgets_strings.tooltip_xlite_label_msg,
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.binary_manager.frame_manager.install_delete_blocknet_button,
            msg="",
            delay=1,
            width=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.binary_manager.frame_manager.install_delete_blockdx_button,
            msg=container.blockdx_release_url,
            delay=1,
            width=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.binary_manager.frame_manager.install_delete_xlite_button,
            msg=container.xlite_release_url,
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.binary_manager.frame_manager.blocknet_start_close_button,
            msg="",
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.binary_manager.frame_manager.blockdx_start_close_button,
            msg="",
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.binary_manager.frame_manager.xlite_toggle_execution_button,
            msg="",
            delay=1,
            follow=True,
            bg_color=tooltip_bg_color,
            border_width=2,
            justify="left",
        )
        self.tooltip_manager.register_tooltip(
            self.blocknet_manager.frame_manager.label,
            msg=widgets_strings.tooltip_blocknet_core_label_msg,
            delay=1.0,
            border_width=2,
            follow=True,
            bg_color=tooltip_bg_color,
        )
        self.tooltip_manager.register_tooltip(
            self.blockdx_manager.frame_manager.label,
            msg=widgets_strings.tooltip_blockdx_label_msg,
            delay=1.0,
            border_width=2,
            follow=True,
            bg_color=tooltip_bg_color,
        )

    def init_grid(self) -> None:
        """Initialize the grid layout for GUI components."""
        x: int = 0
        y: int = 0
        padx_main_frame: int = 10
        pady_main_frame: int = 5
        self.grid_frames(x, y, padx_main_frame, pady_main_frame)
        self.binary_manager.frame_manager.grid_widgets(x, y)
        self.blocknet_manager.frame_manager.grid_widgets(x, y)
        self.blockdx_manager.frame_manager.grid_widgets(x, y)
        self.xlite_manager.frame_manager.grid_widgets(x, y)

    def grid_frames(self, x: int, y: int, padx_main_frame: int, pady_main_frame: int) -> None:
        """Grid layout for frames in the GUI."""
        self.binary_manager.frame_manager.master_frame.grid(
            row=x, column=y, padx=padx_main_frame, pady=pady_main_frame, sticky=MAIN_FRAMES_STICKY
        )
        # bin panel have 5 buttons per row
        self.binary_manager.frame_manager.title_frame.grid(
            row=0, column=0, columnspan=5, padx=5, pady=5, sticky=TITLE_FRAMES_STICKY
        )

        self.blocknet_manager.frame_manager.master_frame.grid(
            row=x + 1, column=y, padx=padx_main_frame, pady=pady_main_frame, sticky=MAIN_FRAMES_STICKY
        )
        self.blocknet_manager.frame_manager.title_frame.grid(
            row=0, column=0, columnspan=2, padx=5, pady=5, sticky=TITLE_FRAMES_STICKY
        )

        self.blockdx_manager.frame_manager.master_frame.grid(
            row=x + 2, column=y, padx=padx_main_frame, pady=pady_main_frame, sticky=MAIN_FRAMES_STICKY
        )
        self.blockdx_manager.frame_manager.title_frame.grid(
            row=0, column=0, columnspan=2, padx=5, pady=5, sticky=TITLE_FRAMES_STICKY
        )

        self.xlite_manager.frame_manager.master_frame.grid(
            row=x + 3, column=y, padx=padx_main_frame, pady=pady_main_frame, sticky=MAIN_FRAMES_STICKY
        )
        self.xlite_manager.frame_manager.title_frame.grid(
            row=0, column=0, columnspan=2, padx=5, pady=5, sticky=TITLE_FRAMES_STICKY
        )

    def handle_signal(self, signum: int, frame) -> None:
        """Handle signals like SIGINT and SIGTERM."""
        if getattr(self, "_closing", False):
            logger.debug(f"Signal {signum} ignored, already closing")
            return
        logger.info(f"Signal {signum} received.")
        # Deregister to avoid double call
        try:
            signal.signal(signal.SIGINT, signal.SIG_DFL)
        except (ValueError, OSError, AttributeError) as e:
            logger.debug(f"Reset SIGINT failed: {e}")
        try:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
        except (ValueError, OSError, AttributeError) as e:
            logger.debug(f"Reset SIGTERM failed: {e}")
        # Schedule on_close on main thread via after(0) if possible
        try:
            if hasattr(self, "winfo_exists"):
                try:
                    if self.winfo_exists():
                        self.after(0, self.on_close)
                        return
                except Exception as e:  # debug logged
                    logger.debug(f"Suppressed Exception: {e}", exc_info=True)
        except Exception as e:  # debug logged
            logger.debug(f"handle_signal after failed: {e}")
        self.on_close()

    def on_close(self) -> None:
        """Handle application close event — idempotent graceful shutdown."""
        if getattr(self, "_closing", False):
            logger.debug("on_close already in progress, ignoring")
            return
        self._closing = True
        logger.info("Closing application...")
        # Reset signals to DFL to avoid double handling
        try:
            signal.signal(signal.SIGINT, signal.SIG_DFL)
        except (ValueError, OSError, AttributeError) as e:
            logger.debug(f"Reset SIGINT failed: {e}")
        try:
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
        except (ValueError, OSError, AttributeError) as e:
            logger.debug(f"Reset SIGTERM failed: {e}")

        # Stop unified scheduler first
        try:
            if hasattr(self, "ui_sync") and getattr(self, "ui_sync", None):
                self.ui_sync.stop()
        except Exception as e:
            logger.debug(f"UiSync stop error: {e}")

        # Cancel all scheduled afters
        try:
            self._cancel_all_afters()
        except Exception as e:  # debug logged
            logger.debug(f"Cancel afters failed: {e}")

        # Stop file watcher and binary manager loops
        try:
            if hasattr(self, "binary_manager") and hasattr(self.binary_manager, "stop"):
                self.binary_manager.stop()
        except Exception as e:
            logger.debug(f"Watcher stop error: {e}")

        # Stop GUI manager update loops
        for mgr_name in ("blocknet_manager", "blockdx_manager", "xlite_manager"):
            try:
                mgr = getattr(self, mgr_name, None)
                if mgr and hasattr(mgr, "stop"):
                    mgr.stop()
            except Exception as e:
                logger.debug(f"{mgr_name} stop error: {e}")

        # Signal handler utilities to stop threads via Event
        for mgr_name in ("blocknet_manager", "blockdx_manager", "xlite_manager"):
            try:
                mgr = getattr(self, mgr_name, None)
                util = getattr(mgr, "utility", None) if mgr else None
                if util and hasattr(util, "stop"):
                    util.stop()
            except Exception as e:
                logger.debug(f"{mgr_name} utility stop error: {e}")

        # TEMP DISABLE xlite-reverse-proxy — keep for restore
        # Stop proxy if running
        try:
            if hasattr(self, "xlite_manager") and getattr(self.xlite_manager, "reverse_proxy", None):
                self.xlite_manager.reverse_proxy.stop()
        except Exception as e:
            logger.error(f"Proxy shutdown error: {e}")

        utils.join_daemon_threads()
        logger.info("Threads terminated.")

        # Graceful destroy, never os._exit/sys.exit inside on_close
        try:
            if hasattr(self, "winfo_exists"):
                try:
                    if not self.winfo_exists():
                        return
                except Exception:
                    return
            self.destroy()
        except Exception as e:  # TclError after destroy
            logger.debug(f"destroy failed: {e}")

    def adjust_theme(self) -> None:
        """Adjust the theme of the application based on the configuration."""
        if self.cfg and "theme" in self.cfg:
            actual: str = ctk.get_appearance_mode()
            if self.cfg["theme"] != actual:
                if actual == "Dark":
                    new_theme: str = "Light"
                else:
                    new_theme: str = "Dark"
                ctk.set_appearance_mode(new_theme)

    def switch_theme_command(self) -> None:
        """Switch the application theme to the opposite of the current theme."""
        actual: str = ctk.get_appearance_mode()
        if actual == "Dark":
            new_theme: str = "Light"
        else:
            new_theme: str = "Dark"
        ctk.set_appearance_mode(new_theme)
        utils.save_cfg_json("theme", new_theme)

    def check_processes(self) -> None:
        """
        Checks the status of all relevant processes and updates the GUI accordingly.
        """
        blocknet_processes, blockdx_processes, xlite_processes, xlite_daemon_processes = utils.processes_check()

        # Update Blocknet process status and store the PIDs
        self.blocknet_manager.blocknet_process_running = bool(blocknet_processes)
        self.blocknet_manager.utility.blocknet_pids = blocknet_processes

        # Update Block DX process status and store the PIDs
        self.blockdx_manager.process_running = bool(blockdx_processes)
        self.blockdx_manager.utility.blockdx_pids = blockdx_processes

        # Update Xlite process status and store the PIDs
        self.xlite_manager.process_running = bool(xlite_processes)
        self.xlite_manager.utility.xlite_pids = xlite_processes

        # Update Xlite-daemon process status and store the PIDs
        self.xlite_manager.daemon_process_running = bool(xlite_daemon_processes)
        self.xlite_manager.utility.xlite_daemon_pids = xlite_daemon_processes

        # Schedule the next check only if not driven by UiSyncController
        if getattr(self, "ui_sync", None) is not None and not getattr(self.ui_sync, "_closing", True):
            return
        if getattr(self, "_closing", False):
            return
        try:
            if hasattr(self, "winfo_exists") and not self.winfo_exists():
                return
        except Exception:
            return
        aid = self.after(INTERVAL_PROCESS_CHECK_MS, func=self.check_processes)
        self._check_processes_after_id = aid
        self._track_after(aid)


def run_gui() -> None:
    """Run the Blocknet AIO GUI application."""
    app = BlocknetAioGui()
    # try:
    app.init_setup()
    app.mainloop()
    # except KeyboardInterrupt:
    #     print("GUI execution terminated by user.")
    # except Exception as e:
    #     # Log the error to a file
    #     logger.basicConfig(filename='gui_errors.log', level=logging.ERROR,
    #                         format='%(asctime)s - %(levelname)s - %(message)s')
    #     logger.error("An error occurred: %s", e)
    #
    #     # Print a user-friendly error message
    #     print("An unexpected error occurred. Please check the log file 'gui_errors.log' for more information.")
    #     app.on_close()


if __name__ == "__main__":
    run_gui()
