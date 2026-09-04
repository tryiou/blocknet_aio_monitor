import contextlib
import logging
import os

from gui.blockdx_frame_manager import BlockDxFrameManager
from utilities.app_container import get_container
from utilities.bin_handlers.blockdx_handler import BlockDXHandler

logger = logging.getLogger(__name__)


class BlockDXManager:
    def __init__(self, root_gui):
        self.frame_manager = None
        self.root_gui = root_gui
        self.utility = BlockDXHandler()
        container = get_container()
        if container.blockdx_release_url:
            self.version = [container.blockdx_release_url.split("/")[7]]
        else:
            self.version = ["unknown"]
        self.process_running = False
        self.is_config_sync = None
        self._status_after_id: str | None = None
        self._setup_after_id: str | None = None
        self._closing: bool = False

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
        self.frame_manager = BlockDxFrameManager(self)
        self._last_snapshot: tuple | None = None
        try:
            self._setup_after_id = self.root_gui.after(0, self.update_status_blockdx)
        except Exception as e:  # debug logged
            logger.debug(f"Suppressed Exception: {e}", exc_info=True)

    def blockdx_check_config(self):
        """
        Checks and updates the local BlockDX configuration based on Blocknet settings.
        """
        blocknet_utility = self.root_gui.blocknet_manager.utility
        if not (blocknet_utility.data_folder and blocknet_utility.blocknet_conf_local):
            return  # Blocknet configuration is not available

        xbridge_conf_path = os.path.normpath(os.path.join(blocknet_utility.data_folder, "xbridge.conf"))
        rpc_user = blocknet_utility.blocknet_conf_local.get("global", {}).get("rpcuser")
        rpc_password = blocknet_utility.blocknet_conf_local.get("global", {}).get("rpcpassword")

        self.utility.compare_and_update_local_conf(xbridge_conf_path, rpc_user, rpc_password)

    def _snapshot(self) -> tuple:
        try:
            core_utility = getattr(getattr(self.root_gui, "blocknet_manager", None), "utility", None)
            return (
                getattr(self, "process_running", None),
                getattr(self, "is_config_sync", None),
                getattr(getattr(self, "utility", None), "downloading_bin", None),
                # Core-side inputs of update_blockdx_config_button_checkbox: when Core
                # stops (RPC drops) the tick must refresh instead of going stale.
                getattr(core_utility, "valid_rpc", None),
                bool(getattr(core_utility, "data_folder", None)),
                bool(getattr(core_utility, "blocknet_conf_local", None)),
            )
        except Exception:
            return (None,)

    def update_status_blockdx(self) -> None:
        """Single-shot update (no rescheduling)."""
        if getattr(self, "_closing", False):
            return
        try:
            if hasattr(self.root_gui, "winfo_exists") and not self.root_gui.winfo_exists():
                return
        except Exception as e:  # debug logged
            logger.debug(f"Suppressed Exception: {e}", exc_info=True)
            return
        self.frame_manager.update_blockdx_process_status_checkbox()
        self.frame_manager.update_blockdx_config_button_checkbox()

    def update_status_if_dirty(self) -> bool:
        """Dirty-checked wrapper."""
        try:
            cur = self._snapshot()
            if cur == getattr(self, "_last_snapshot", None):
                return False
            self._last_snapshot = cur  # type: ignore
            self.update_status_blockdx()
            return True
        except Exception as e:
            logger.debug(f"update_status_if_dirty failed: {e}")
            with contextlib.suppress(Exception):
                self.update_status_blockdx()
            return True
