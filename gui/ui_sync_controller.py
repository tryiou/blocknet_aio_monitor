import logging

from utilities.timing import (
    INTERVAL_PROCESS_CHECK_MS,
    INTERVAL_UI_POLL_MS,
    MAX_BOTS_RETRY,
)

logger = logging.getLogger(__name__)


class UiSyncController:
    """Single scheduler unifying periodic UI updates with dirty-check.

    Ticks every INTERVAL_UI_POLL_MS (1000ms). Guarded by _closing and
    winfo_exists. Uses modulo counter for 5000ms check_processes.
    Delegates to *_if_dirty wrappers when available, falling back to
    direct update methods. Bots venv retry is bounded by MAX_BOTS_RETRY.
    """

    def __init__(self, root_gui, interval_ms: int | None = None) -> None:
        self.root_gui = root_gui
        self.interval: int = interval_ms if interval_ms is not None else INTERVAL_UI_POLL_MS
        self._after_id: str | None = None
        self._closing: bool = False
        self._counter: int = 0
        self._bots_retries: int = 0

    def start(self) -> None:
        """Start periodic tick (idempotent)."""
        if self._closing:
            # allow restart after stop only via fresh instance; but handle
            self._closing = False
        self._counter = 0
        self._bots_retries = 0
        self._schedule_next()

    def stop(self) -> None:
        """Stop periodic tick and cancel pending after (idempotent)."""
        self._closing = True
        if self._after_id is not None:
            try:
                if hasattr(self.root_gui, "winfo_exists"):
                    try:
                        if not self.root_gui.winfo_exists():
                            self._after_id = None
                            return
                    except Exception:
                        self._after_id = None
                        return
                self.root_gui.after_cancel(self._after_id)
            except Exception as e:  # debug logged
                logger.debug(f"UiSyncController after_cancel failed: {e}")
            self._after_id = None

    def _schedule_next(self) -> None:
        if getattr(self, "_closing", False):
            return
        try:
            if hasattr(self.root_gui, "winfo_exists") and not self.root_gui.winfo_exists():
                return
        except Exception:
            return
        try:
            self._after_id = self.root_gui.after(self.interval, self._tick)
        except Exception as e:  # debug logged
            logger.debug(f"UiSyncController schedule failed: {e}")

    def _tick(self) -> None:
        if getattr(self, "_closing", False):
            return
        try:
            if hasattr(self.root_gui, "winfo_exists") and not self.root_gui.winfo_exists():
                return
        except Exception:
            return
        self._counter += 1
        try:
            # Binary manager updates
            bm = getattr(self.root_gui, "binary_manager", None)
            if bm is not None:
                # AIO fallback poll every 2 ticks (2000ms) when observer missing
                try:
                    if getattr(bm, "observer", None) is None and self._counter % 2 == 0:  # noqa: SIM102
                        if hasattr(bm, "check_and_update_aio_folder"):
                            bm.check_and_update_aio_folder()
                except Exception as e:
                    logger.debug(f"UiSync poll folder failed: {e}")
                # update_all and bots with dirty-check wrappers
                try:
                    if hasattr(bm, "update_all_if_dirty"):
                        bm.update_all_if_dirty()
                    elif hasattr(bm, "update_all_binary_buttons"):
                        bm.update_all_binary_buttons()
                except Exception as e:
                    logger.debug(f"UiSync update_all failed: {e}", exc_info=True)
                try:
                    if hasattr(bm, "update_bots_if_dirty"):
                        bm.update_bots_if_dirty()
                    elif hasattr(bm, "update_xbridge_bots_buttons"):
                        bm.update_xbridge_bots_buttons()
                except Exception as e:
                    logger.debug(f"UiSync update_bots failed: {e}", exc_info=True)
                self._handle_bots_retry(bm)

            # Blocknet
            m = getattr(self.root_gui, "blocknet_manager", None)
            if m is not None:
                try:
                    if hasattr(m, "update_status_if_dirty"):
                        m.update_status_if_dirty()
                    elif hasattr(m, "update_status_blocknet_core"):
                        m.update_status_blocknet_core()
                except Exception as e:
                    logger.debug(f"UiSync blocknet update failed: {e}", exc_info=True)

            # BlockDX
            m = getattr(self.root_gui, "blockdx_manager", None)
            if m is not None:
                try:
                    if hasattr(m, "update_status_if_dirty"):
                        m.update_status_if_dirty()
                    elif hasattr(m, "update_status_blockdx"):
                        m.update_status_blockdx()
                except Exception as e:
                    logger.debug(f"UiSync blockdx update failed: {e}", exc_info=True)

            # Xlite
            m = getattr(self.root_gui, "xlite_manager", None)
            if m is not None:
                try:
                    if hasattr(m, "update_status_if_dirty"):
                        m.update_status_if_dirty()
                    elif hasattr(m, "update_status_xlite"):
                        m.update_status_xlite()
                except Exception as e:
                    logger.debug(f"UiSync xlite update failed: {e}", exc_info=True)

            # check_processes every INTERVAL_PROCESS_CHECK_MS (5000) via modulo
            divisor = max(1, INTERVAL_PROCESS_CHECK_MS // self.interval)
            if self._counter % divisor == 0:
                try:
                    if hasattr(self.root_gui, "check_processes"):
                        self.root_gui.check_processes()
                except Exception as e:
                    logger.debug(f"UiSync check_processes failed: {e}", exc_info=True)

        finally:
            if not getattr(self, "_closing", False):
                self._schedule_next()

    def _handle_bots_retry(self, binary_manager) -> None:
        """Bounded retry for bots venv — wait until venv ready, do not spam toggle."""
        try:
            fm = getattr(binary_manager, "frame_manager", None)
            if fm is None:
                return
            bot_mgr = getattr(fm, "xbridge_bot_manager", None)
            if bot_mgr is None:
                return
            repo_mgmt = getattr(bot_mgr, "repo_management", None)
            # Need venv to run bots; if missing, just wait (do not auto-toggle)
            # Installer or deferred_start will create venv; we only reset counter when ready.
            if repo_mgmt is None or not getattr(repo_mgmt, "venv", None):
                # If installer is running, wait silently
                installer = getattr(bot_mgr, "installer_thread", None)
                if installer is not None and hasattr(installer, "is_alive") and installer.is_alive():
                    return
                # No venv yet — count retries but log only once and at cap to avoid spam
                if self._bots_retries < MAX_BOTS_RETRY:
                    self._bots_retries += 1
                    if self._bots_retries == 1 or self._bots_retries == MAX_BOTS_RETRY:
                        logger.debug(f"Bots venv not ready, waiting ({self._bots_retries}/{MAX_BOTS_RETRY})")
                return
            else:
                # venv exists -> reset counter
                self._bots_retries = 0
        except Exception as e:
            logger.debug(f"UiSync bots retry handling failed: {e}")
