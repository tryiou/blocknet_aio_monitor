import contextlib
import logging
import threading

from gui.xlite_frame_manager import XliteFrameManager
from utilities.app_container import get_container
from utilities.bin_handlers.xlite_handler import XliteHandler
from utilities.bin_handlers.xlite_reverse_proxy_handler import (
    XliteReverseProxyHandler,  # noqa: F401 — kept for restore (TEMP DISABLE)
)

logger = logging.getLogger(__name__)


class XliteManager:
    def __init__(self, root_gui):
        self.root_gui = root_gui

        self.frame_manager = None
        self.utility = XliteHandler()

        container = get_container()
        if container.xlite_release_url:
            self.version = [container.xlite_release_url.split("/")[7]]
        else:
            self.version = ["unknown"]
        self.process_running = False
        self.daemon_process_running = False
        self._status_after_id: str | None = None
        self._setup_after_id: str | None = None
        self._closing: bool = False
        self._last_snapshot: tuple | None = None
        self._dxload_pending: bool = False

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

    def setup(self) -> None:
        self.frame_manager = XliteFrameManager(self)
        # TEMP DISABLE xlite-reverse-proxy — keep handler for restore
        self.reverse_proxy = None  # was: XliteReverseProxyHandler()
        self.reverse_proxy_running = False
        # TEMP DISABLE: self.reverse_proxy = XliteReverseProxyHandler()
        # TEMP DISABLE: try: self.reverse_proxy.start() except Exception as e: logger.error(f"Proxy init failed: {e}")
        try:
            self._setup_after_id = self.root_gui.after(0, self.update_status_xlite)
        except Exception as e:  # debug logged
            logger.debug(f"Suppressed Exception: {e}", exc_info=True)

    def refresh_xlite_confs(self):
        self.utility.parse_xlite_conf()
        self.utility.parse_xlite_daemon_conf()

    def detect_new_xlite_install_and_add_to_xbridge(self):
        with self.utility._lock:
            valid = self.utility.valid_coins_rpc
        if not self.root_gui.disable_daemons_conf_check and valid:
            with self.utility._lock:
                snapshot = dict(self.utility.xlite_daemon_confs_local)
            self.root_gui.blocknet_manager.utility.check_xbridge_conf(snapshot)
            if (
                self.root_gui.blocknet_manager.blocknet_process_running
                and self.root_gui.blocknet_manager.utility.valid_rpc
            ) and not self._dxload_pending:
                self._dxload_pending = True

                def _do_dxload():
                    try:
                        logger.debug("dxloadxbridgeConf")
                        self.root_gui.blocknet_manager.utility.blocknet_rpc.send_rpc_request("dxloadxbridgeConf")
                    except Exception as e:
                        logger.debug(f"dxloadxbridgeConf failed: {e}")
                    finally:
                        self._dxload_pending = False

                try:
                    threading.Thread(target=_do_dxload, daemon=True, name="XliteDxLoad").start()
                except Exception as e:
                    logger.debug(f"Failed to start dxload thread: {e}")
                    self._dxload_pending = False
            self.root_gui.disable_daemons_conf_check = True
        with self.utility._lock:
            valid2 = self.utility.valid_coins_rpc
        if self.root_gui.disable_daemons_conf_check and not valid2:
            self.root_gui.disable_daemons_conf_check = False

    def _snapshot(self) -> tuple:
        try:
            with self.utility._lock:
                valid = self.utility.valid_coins_rpc
                daemon_confs = (
                    dict(self.utility.xlite_daemon_confs_local)
                    if isinstance(self.utility.xlite_daemon_confs_local, dict)
                    else None
                )
            return (
                getattr(self, "process_running", None),
                getattr(self, "daemon_process_running", None),
                valid,
                getattr(self.utility, "downloading_bin", None),
                tuple(sorted(daemon_confs.keys())) if isinstance(daemon_confs, dict) else None,
                getattr(getattr(self, "root_gui", None), "stored_password", None),
                getattr(getattr(self, "root_gui", None), "xbridge_block_source", None),
            )
        except Exception:
            return (None,)

    def update_status_xlite(self) -> None:
        """Single-shot update (no rescheduling)."""
        if getattr(self, "_closing", False):
            return
        try:
            if hasattr(self.root_gui, "winfo_exists") and not self.root_gui.winfo_exists():
                return
        except Exception as e:  # debug logged
            logger.debug(f"Suppressed Exception: {e}", exc_info=True)
            return
        self.detect_new_xlite_install_and_add_to_xbridge()
        self.frame_manager.update_xlite_process_status_checkbox()
        self.frame_manager.update_xlite_store_password_button()
        self.frame_manager.update_xlite_daemon_process_status()
        self.frame_manager.update_xlite_valid_config_checkbox()
        self.frame_manager.update_xlite_daemon_valid_config_checkbox()
        self.frame_manager.update_xbridge_block_source_widget()
        # TEMP DISABLE xlite-reverse-proxy polling — keep for restore:
        # self.reverse_proxy_running = self.reverse_proxy.port_occupied() or self.reverse_proxy.running_locally
        self.reverse_proxy_running = False
        # Keep UI sync for hidden widget (grid hidden) so tests stay green; remove if fully disabling
        self.frame_manager.update_xlite_reverse_proxy_process_status()

    def update_status_if_dirty(self) -> bool:
        try:
            cur = self._snapshot()
            if cur == getattr(self, "_last_snapshot", None):
                return False
            self._last_snapshot = cur  # type: ignore
            self.update_status_xlite()
            return True
        except Exception as e:
            logger.debug(f"update_status_if_dirty failed: {e}")
            with contextlib.suppress(Exception):
                self.update_status_xlite()
            return True
