import logging
import threading

import customtkinter as ctk

import utilities.utils
import widgets_strings
from gui.layout import tokens
from gui.layout.base_frame import BaseFrameManager
from gui.layout.widgets import (
    make_button,
    make_caption,
    make_checkbox,
    make_icon_button,
    make_label,
    make_optionmenu,
)
from gui.xbridge_bot_manager import XBridgeBotManager
from utilities.timing import INTERVAL_BOTS_RETRY_MS, MAX_BOTS_RETRY

logger = logging.getLogger(__name__)


class BinaryFrameManager(BaseFrameManager):
    panel = "binary"

    def __init__(self, parent):
        super().__init__(parent)

        self.xbridge_bot_manager = XBridgeBotManager()
        self.header_label = make_caption(
            self.title_frame,
            widgets_strings.binaries_control_panel_string,
            width=tokens.HEADER_W,
        )
        self.button_switch_theme = make_icon_button(
            self.title_frame,
            image=self.root_gui.theme_img,
            command=self.root_gui.switch_theme_command,
        )

        # Bins labels
        self.blocknet_label = make_label(self.master_frame, text=widgets_strings.binaries_blocknet_core_label_string)
        self.blockdx_label = make_label(self.master_frame, text=widgets_strings.binaries_blockdx_label_string)
        self.xlite_label = make_label(self.master_frame, text=widgets_strings.binaries_xlite_label_string)
        self.bots_label = make_label(self.master_frame, text=widgets_strings.binaries_bots_label_string)

        # Bins option_menus
        self.blocknet_version_optionmenu = make_optionmenu(
            self.master_frame, values=self.root_gui.blocknet_manager.version, state="disabled"
        )
        self.blockdx_version_optionmenu = make_optionmenu(
            self.master_frame, values=self.root_gui.blockdx_manager.version, state="disabled"
        )
        self.xlite_version_optionmenu = make_optionmenu(
            self.master_frame, values=self.root_gui.xlite_manager.version, state="disabled"
        )
        # Branch persistence: defer remote fetch off UI thread
        _saved = self.xbridge_bot_manager.get_saved_branch()
        _initial_values = [_saved]
        _initial = _saved
        self.bots_version_optionmenu = make_optionmenu(
            self.master_frame,
            values=_initial_values,
            state="normal",
            command=self.on_bots_branch_selected,
        )
        self.bots_version_optionmenu.set(_initial)
        # Deferred fetch of remote branches (non-blocking)
        self._defer_branch_fetch()
        # Checkboxes BoolVars
        self.blocknet_installed_boolvar = ctk.BooleanVar(value=False)
        self.blockdx_installed_boolvar = ctk.BooleanVar(value=False)
        self.xlite_installed_boolvar = ctk.BooleanVar(value=False)
        self.bots_installed_boolvar = ctk.BooleanVar(value=False)

        # Bins checkboxes
        self.blocknet_found_checkbox = make_checkbox(
            self.master_frame,
            variable=self.blocknet_installed_boolvar,
            width=tokens.ICON_W,
        )
        self.blockdx_found_checkbox = make_checkbox(
            self.master_frame,
            variable=self.blockdx_installed_boolvar,
        )
        self.xlite_found_checkbox = make_checkbox(
            self.master_frame,
            variable=self.xlite_installed_boolvar,
        )
        self.bots_found_checkbox = make_checkbox(
            self.master_frame,
            variable=self.bots_installed_boolvar,
        )
        # install/delete buttons
        self.install_delete_blocknet_string_var = ctk.StringVar(value="")
        self.install_delete_blocknet_button = make_button(
            self.master_frame,
            state="normal",
            image=self.root_gui.transparent_img,
            command=self.parent.install_delete_blocknet_command,
            width=tokens.BIN_BUTTON_W,
            textvariable=self.install_delete_blocknet_string_var,
            corner_radius=tokens.CORNER_R,
        )
        self.install_delete_blockdx_string_var = ctk.StringVar(value="")
        self.install_delete_blockdx_button = make_button(
            self.master_frame,
            state="normal",
            image=self.root_gui.transparent_img,
            command=self.parent.install_delete_blockdx_command,
            textvariable=self.install_delete_blockdx_string_var,
            width=tokens.BIN_BUTTON_W,
            corner_radius=tokens.CORNER_R,
        )
        self.install_delete_xlite_string_var = ctk.StringVar(value="")
        self.install_delete_xlite_button = make_button(
            self.master_frame,
            state="normal",
            image=self.root_gui.transparent_img,
            command=self.parent.install_delete_xlite_command,
            textvariable=self.install_delete_xlite_string_var,
            width=tokens.BIN_BUTTON_W,
            corner_radius=tokens.CORNER_R,
        )
        self.install_delete_bots_button = make_button(
            self.master_frame,
            state="normal",
            text="",
            image=self.root_gui.transparent_img,
            command=self.install_update_bots_command,
            width=tokens.BIN_BUTTON_W,
            corner_radius=tokens.CORNER_R,
        )
        # start/close buttons
        self.blocknet_start_close_button_string_var = ctk.StringVar(value="")
        self.blocknet_start_close_button = make_button(
            self.master_frame,
            image=self.root_gui.transparent_img,
            width=tokens.BIN_BUTTON_W,
            text="",
            command=self.parent.start_or_close_blocknet,
            corner_radius=tokens.CORNER_R,
        )
        self.blockdx_start_close_button_string_var = ctk.StringVar(value="")
        self.blockdx_start_close_button = make_button(
            self.master_frame,
            image=self.root_gui.transparent_img,
            width=tokens.BIN_BUTTON_W,
            text="",
            command=self.parent.start_or_close_blockdx,
            corner_radius=tokens.CORNER_R,
        )
        self.xlite_toggle_execution_string_var = ctk.StringVar(value="")
        self.xlite_toggle_execution_button = make_button(
            self.master_frame,
            image=self.root_gui.transparent_img,
            width=tokens.BIN_BUTTON_W,
            text="",
            command=self.parent.start_or_close_xlite,
            corner_radius=tokens.CORNER_R,
        )
        self.bots_toggle_execution_button = make_button(
            self.master_frame,
            image=self.root_gui.transparent_img,
            text="",
            command=self.toggle_bots_execution_command,
            width=tokens.BIN_BUTTON_W,
            corner_radius=tokens.CORNER_R,
        )

        # Bots buttons

    def _defer_branch_fetch(self) -> None:
        """Fetch remote branches in background thread, update UI on main thread."""

        def _fetch():
            try:
                branches = self.xbridge_bot_manager.get_available_branches()
            except Exception as e:
                logger.debug(f"Branch fetch failed: {e}")
                branches = None
            if branches is None:
                return

            def _apply():
                try:
                    if hasattr(self.root_gui, "winfo_exists") and not self.root_gui.winfo_exists():
                        return
                    if getattr(self.root_gui, "_closing", False):
                        return
                    resolved = self.xbridge_bot_manager.resolve_startup_branch(branches)
                    self.bots_version_optionmenu.configure(values=branches)
                    self.bots_version_optionmenu.set(resolved)
                except Exception as e:
                    logger.debug(f"Branch apply failed: {e}")

            try:
                if hasattr(self.root_gui, "after"):
                    self.root_gui.after(0, _apply)
                else:
                    _apply()
            except Exception as e:
                logger.debug(f"Branch after failed: {e}")

        try:
            # Schedule fetch off main thread via after(0 Thread)
            if hasattr(self.root_gui, "after"):
                self.root_gui.after(0, lambda: threading.Thread(target=_fetch, daemon=True).start())
            else:
                threading.Thread(target=_fetch, daemon=True).start()
        except Exception as e:
            logger.debug(f"Defer branch fetch failed: {e}")
            threading.Thread(target=_fetch, daemon=True).start()

    def on_bots_branch_selected(self, choice: str) -> None:
        """Persist user branch choice immediately."""
        try:
            self.xbridge_bot_manager.save_branch(choice)
        except Exception as e:  # debug logged
            logger.debug("Suppressed Exception: %s", e, exc_info=True)

    def install_update_bots_command(self):
        """Handle install/update button click - left click installs/updates, right click deletes"""
        if self.xbridge_bot_manager and self.bots_version_optionmenu.get():
            utilities.utils.disable_button(self.install_delete_bots_button, self.root_gui.install_greyed_img)
            utilities.utils.disable_button(self.bots_toggle_execution_button, self.root_gui.start_greyed_img)
            self.xbridge_bot_manager.install_or_update(self.bots_version_optionmenu.get())

    def toggle_bots_execution_command(self):
        """Handle execution toggle button click"""
        branch = self.bots_version_optionmenu.get()
        if self.xbridge_bot_manager and branch:
            utilities.utils.disable_button(self.install_delete_bots_button, self.root_gui.install_greyed_img)
            utilities.utils.disable_button(self.bots_toggle_execution_button, self.root_gui.start_greyed_img)
            self.xbridge_bot_manager.toggle_execution(branch)
            # Let UiSyncController handle bounded retry; keep fallback for non-controller use
            try:
                rm = getattr(self.xbridge_bot_manager, "repo_management", None)
                if rm is None or not getattr(rm, "venv", None):
                    self.run_after_setup()
            except Exception as e:
                logger.debug(f"toggle post-check failed: {e}")

    def run_after_setup(self, _retries: int = 0, max_retries: int = MAX_BOTS_RETRY):
        # Bound recursion and check closing/venv to avoid infinite loop
        try:
            if getattr(self.root_gui, "_closing", False) is True:
                return
            if getattr(getattr(self, "parent", None), "_closing", False) is True:
                return
            if hasattr(self.root_gui, "winfo_exists") and not self.root_gui.winfo_exists():
                return
        except Exception as e:  # debug logged
            logger.debug(f"Suppressed Exception: {e}", exc_info=True)
            return
        if self.xbridge_bot_manager.repo_management and self.xbridge_bot_manager.repo_management.venv:
            try:
                self.xbridge_bot_manager.toggle_execution()
            except Exception as e:  # debug logged
                logger.debug("Suppressed Exception: %s", e, exc_info=True)
            return
        if _retries >= max_retries:
            logger.debug(f"run_after_setup max retries {max_retries} reached, giving up")
            return
        # If UiSyncController is active, let it handle retries (bounded via controller)
        try:
            if (
                hasattr(self.root_gui, "ui_sync")
                and getattr(self.root_gui, "ui_sync", None)
                and getattr(self.root_gui.ui_sync, "_closing", False) is False
            ):
                return
        except Exception as e:
            logger.debug(f"UiSync check failed: {e}")
        try:
            self.root_gui.after(INTERVAL_BOTS_RETRY_MS, lambda: self.run_after_setup(_retries + 1, max_retries))
        except Exception as e:  # debug logged
            logger.debug("Suppressed Exception: %s", e, exc_info=True)
