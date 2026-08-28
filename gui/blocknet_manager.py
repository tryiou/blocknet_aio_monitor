import contextlib
import logging

from gui.blocknet_frame_manager import BlocknetCoreFrameManager
from utilities.app_container import get_container
from utilities.bin_handlers.blocknet_handler import BlocknetHandler

logger = logging.getLogger(__name__)


class BlocknetManager:
    def __init__(self, root_gui):
        self.frame_manager = None
        self.root_gui = root_gui
        container = get_container()
        if container.blocknet_release_url:
            self.version = [container.blocknet_release_url.split("/")[7]]
        else:
            self.version = ["unknown"]
        self.blocknet_process_running = False

        self.bootstrap_thread = None
        self._status_after_id: str | None = None
        self._setup_after_id: str | None = None
        self._closing: bool = False

        self.utility = BlocknetHandler(custom_path=self.root_gui.custom_path)

    def stop(self) -> None:
        """Cancel scheduled updates (idempotent)."""
        self._closing = True
        for aid in [self._status_after_id, self._setup_after_id]:
            if aid is not None:
                try:
                    if hasattr(self.root_gui, "winfo_exists"):
                        try:
                            if not self.root_gui.winfo_exists():
                                continue
                        except Exception as e:  # debug logged
                            logger.debug(f"Suppressed Exception: {e}", exc_info=True)
                            continue
                    self.root_gui.after_cancel(aid)
                except Exception as e:  # debug logged
                    logger.debug(f"after_cancel failed: {e}")
        self._status_after_id = None
        self._setup_after_id = None
        # Join bootstrap thread if alive
        thr = getattr(self, "bootstrap_thread", None)
        if thr is not None:
            try:
                if thr.is_alive():
                    thr.join(timeout=0.2)
            except Exception as e:  # debug logged
                logger.debug(f"Suppressed Exception: {e}", exc_info=True)

    def setup(self) -> None:
        self.frame_manager = BlocknetCoreFrameManager(self)
        self._last_snapshot: tuple | None = None

        try:
            self._setup_after_id = self.root_gui.after(0, self.update_status_blocknet_core)
        except Exception as e:  # debug logged
            logger.debug(f"Suppressed Exception: {e}", exc_info=True)

    def check_config(self):
        use_xlite = bool(self.root_gui.xlite_manager.utility.xlite_daemon_confs_local)
        xlite_daemon_conf = self.root_gui.xlite_manager.utility.xlite_daemon_confs_local if use_xlite else None
        self.utility.compare_and_update_local_conf(xlite_daemon_conf)

    def _snapshot(self) -> tuple:
        try:
            u = self.utility
            return (
                getattr(self, "blocknet_process_running", None),
                getattr(u, "bootstrap_checking", None),
                getattr(u, "downloading_bin", None),
                getattr(u, "valid_rpc", None),
                bool(getattr(u, "data_folder", None)),
                bool(getattr(u, "blocknet_conf_local", None)),
            )
        except Exception:
            return (None,)

    def update_status_blocknet_core(self) -> None:
        """Single-shot update (no rescheduling). Use update_status_if_dirty via UiSyncController."""
        if getattr(self, "_closing", False):
            return
        try:
            if hasattr(self.root_gui, "winfo_exists") and not self.root_gui.winfo_exists():
                return
        except Exception as e:  # debug logged
            logger.debug(f"Suppressed Exception: {e}", exc_info=True)
            return
        self.frame_manager.update_blocknet_bootstrap_button()
        self.frame_manager.update_blocknet_process_status_checkbox()
        self.frame_manager.update_blocknet_custom_path_button()
        self.frame_manager.update_blocknet_conf_status_checkbox()
        self.frame_manager.update_blocknet_data_path_status_checkbox()
        self.frame_manager.update_blocknet_rpc_connection_checkbox()

    def update_status_if_dirty(self) -> bool:
        """Dirty-checked wrapper for UiSyncController."""
        try:
            cur = self._snapshot()
            if cur == getattr(self, "_last_snapshot", None):
                return False
            self._last_snapshot = cur  # type: ignore
            self.update_status_blocknet_core()
            return True
        except Exception as e:
            logger.debug(f"update_status_if_dirty failed: {e}")
            with contextlib.suppress(Exception):
                self.update_status_blocknet_core()
            return True
