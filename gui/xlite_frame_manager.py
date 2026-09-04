import logging
import os

import customtkinter as ctk

import widgets_strings
from custom_tk_mods import ctkInputDialogMod
from gui.layout import tokens
from gui.layout.base_frame import BaseFrameManager
from gui.layout.widgets import SegmentedPills, make_button, make_caption, make_checkbox, make_label
from utilities import utils
from utilities.bin_handlers.blocknet_handler import BlocknetHandler

logger = logging.getLogger(__name__)


class XliteFrameManager(BaseFrameManager):
    panel = "xlite"

    def __init__(self, parent):
        super().__init__(parent)
        # Pin the title to the golden width: caption + pills + button content is
        # narrower than the sibling titles; the pin keeps identical checkbox
        # columns in every panel (replaces legacy XLITE_TITLE_WIDTH).
        self.title_frame.configure(width=tokens.TITLE_W)

        self.xlite_label = make_caption(self.title_frame, widgets_strings.xlite_frame_title_string)
        # Checkboxes
        self.process_status_checkbox_state = ctk.BooleanVar()
        self.process_status_checkbox_string_var = ctk.StringVar(value="")
        self.process_status_checkbox = make_checkbox(
            self.master_frame,
            variable=self.process_status_checkbox_state,
            textvariable=self.process_status_checkbox_string_var,
        )

        self.daemon_process_status_checkbox_state = ctk.BooleanVar()
        self.daemon_process_status_checkbox_string_var = ctk.StringVar(value="")
        self.daemon_process_status_checkbox = make_checkbox(
            self.master_frame,
            variable=self.daemon_process_status_checkbox_state,
            textvariable=self.daemon_process_status_checkbox_string_var,
        )

        self.valid_config_checkbox_state = ctk.BooleanVar()
        self.valid_config_checkbox_string_var = ctk.StringVar(value="")
        self.valid_config_checkbox = make_checkbox(
            self.master_frame,
            variable=self.valid_config_checkbox_state,
            textvariable=self.valid_config_checkbox_string_var,
        )

        self.daemon_valid_config_checkbox_state = ctk.BooleanVar()
        self.daemon_valid_config_checkbox_string_var = ctk.StringVar(value="")
        self.daemon_valid_config_checkbox = make_checkbox(
            self.master_frame,
            variable=self.daemon_valid_config_checkbox_state,
            textvariable=self.daemon_valid_config_checkbox_string_var,
        )

        # Create the Button widget with a text variable
        self.store_password_button_string_var = ctk.StringVar(value="")
        self.store_password_button = make_button(self.title_frame, textvariable=self.store_password_button_string_var)

        # Bind left-click event
        self.store_password_button.bind("<Button-1>", lambda event: self.xlite_store_password_button_mouse_click(event))

        # Bind right-click event
        self.store_password_button.bind("<Button-3>", lambda event: self.xlite_store_password_button_mouse_click(event))

        # Set button command for normal button clicks
        self.store_password_button.configure(command=self.xlite_store_password_button_mouse_click)

        # XBridge BLOCK source selector: which wallet feeds the xbridge.conf BLOCK section.
        self.xbridge_block_source_var = ctk.StringVar(value=self._initial_xbridge_block_source())
        self.xbridge_block_source_label = make_label(
            self.title_frame, text=widgets_strings.xbridge_block_source_label_string
        )
        self.xbridge_block_pills = SegmentedPills(
            self.title_frame,
            values=[
                widgets_strings.xbridge_block_source_core_string,
                widgets_strings.xbridge_block_source_xlite_string,
            ],
            variable=self.xbridge_block_source_var,
            command=self.on_xbridge_block_source_changed,
        )
        # Spec-referenced alias: renderer grids this attr in the title middle slot.
        self.xbridge_block_segmented = self.xbridge_block_pills.widget

    def _paint_xbridge_pills(self) -> None:
        """Repaint per-state pill text (kept for the existing test/poll call sites)."""
        self.xbridge_block_pills.repaint()

    def _initial_xbridge_block_source(self) -> str:
        """Display value at startup: stored pref, else auto (same BLOCK-settings test as the handler)."""
        stored = getattr(self.root_gui, "xbridge_block_source", None)
        if stored == "core":
            return widgets_strings.xbridge_block_source_core_string
        if stored == "xlite":
            return widgets_strings.xbridge_block_source_xlite_string
        try:
            with self.parent.utility._lock:
                raw = self.parent.utility.xlite_daemon_confs_local
            if BlocknetHandler._daemon_has_block_settings(raw):
                return widgets_strings.xbridge_block_source_xlite_string
        except Exception as e:  # debug logged
            logger.debug(f"xbridge_block_source auto-resolve failed: {e}")
        return widgets_strings.xbridge_block_source_core_string

    def on_xbridge_block_source_changed(self, value: str) -> None:
        """Persist the user pick (like theme); the 1s poll applies it via the normal check path."""
        if value == widgets_strings.xbridge_block_source_core_string:
            source = "core"
        elif value == widgets_strings.xbridge_block_source_xlite_string:
            source = "xlite"
        else:
            logger.warning(f"Ignoring unknown XBridge BLOCK source selection: {value!r}")
            return
        utils.save_cfg_json("xbridge_block_source", source)
        self.root_gui.xbridge_block_source = source
        self.root_gui.disable_daemons_conf_check = False
        # Dirty the UiSync snapshot: update_status_xlite only runs on snapshot change,
        # and neither the flag nor the pref is part of it — without this the pick would never apply.
        self.parent._last_snapshot = None
        self._paint_xbridge_pills()
        logger.info(f"XBridge BLOCK source set to {source} — will apply on next conf check")

    def update_xbridge_block_source_widget(self) -> None:
        """Sync enabled state; auto selection tracks daemon BLOCK while no explicit pref stored."""
        try:
            with self.parent.utility._lock:
                raw = self.parent.utility.xlite_daemon_confs_local
                snapshot = dict(raw) if isinstance(raw, dict) else {}
            daemon_has_block = BlocknetHandler._daemon_has_block_settings(snapshot)
        except Exception as e:  # debug logged
            logger.debug(f"xbridge_block_source widget update failed: {e}")
            return
        try:
            # No choice to make while the daemon holds no BLOCK: Core is the sole source.
            self.xbridge_block_segmented.configure(state="disabled" if not daemon_has_block else "normal")
            if getattr(self.root_gui, "xbridge_block_source", None) not in ("core", "xlite"):
                auto_display = (
                    widgets_strings.xbridge_block_source_xlite_string
                    if daemon_has_block
                    else widgets_strings.xbridge_block_source_core_string
                )
                if self.xbridge_block_pills.get() != auto_display:
                    self.xbridge_block_pills.set(auto_display)
        except Exception as e:  # debug logged
            logger.debug(f"xbridge_block_source widget update failed: {e}")

    def xlite_store_password_button_mouse_click(self, event=None):
        # Single-route file store: millisecond I/O, runs synchronously on the GUI thread.
        # Check if the right mouse button was clicked
        if event and event.num == 3:
            # wipe_stored_password
            logger.info("Right click detected")
            # Prevent the right-click event from propagating further
            if utils.wipe_stored_password():
                self.root_gui.stored_password = None
                # Delete CC_WALLET_PASS variable
                if "CC_WALLET_PASS" in os.environ:
                    os.environ.pop("CC_WALLET_PASS")
                # Delete CC_WALLET_AUTOLOGIN variable
                if "CC_WALLET_AUTOLOGIN" in os.environ:
                    os.environ.pop("CC_WALLET_AUTOLOGIN")
            # Eager UI refresh — instant feedback, not waiting for poll
            try:
                self.update_xlite_store_password_button()
            except Exception as e:  # debug logged
                logger.debug(f"Eager password button update failed: {e}")
            return "break"

        # For left-click event
        if event and event.num == 1:
            # ask_user_pass
            logger.info("Left click detected")
            fg_color = self.master_frame.cget("fg_color")
            password = ctkInputDialogMod.CTkInputDialog(
                title=widgets_strings.xlite_store_password_dialog_title_string,
                text=widgets_strings.xlite_store_password_dialog_text_string,
                show="*",
                fg_color=fg_color,
            ).get_input()
            if password:
                if utils.store_password(password):
                    # Store the password in a variable
                    self.root_gui.stored_password = password
                else:
                    logger.error("Failed to store password")
                # Eager UI refresh — instant feedback
                try:
                    self.update_xlite_store_password_button()
                except Exception as e:  # debug logged
                    logger.debug(f"Eager password button update failed: {e}")
            else:
                logger.info("No password entered.")
            # Perform actions for left-click (if needed)
            return "break"

    def update_xlite_process_status_checkbox(self):
        # xlite_process_status_checkbox_state
        self.process_status_checkbox_state.set(self.parent.process_running)

        # xlite_process_status_checkbox_string_var
        var = (
            widgets_strings.xlite_running_string
            if self.parent.process_running
            else widgets_strings.xlite_not_running_string
        )
        self.process_status_checkbox_string_var.set(var)

    def update_xlite_store_password_button(self):
        # xlite_store_password_button
        var = (
            widgets_strings.xlite_stored_password_string
            if self.root_gui.stored_password
            else widgets_strings.xlite_store_password_string
        )
        self.store_password_button_string_var.set(var)

    def update_xlite_daemon_process_status(self):
        # xlite_daemon_process_status_checkbox_state
        self.daemon_process_status_checkbox_state.set(self.parent.daemon_process_running)

        # xlite_daemon_process_status_checkbox_string_var
        var = (
            widgets_strings.xlite_daemon_running_string
            if self.parent.daemon_process_running
            else widgets_strings.xlite_daemon_not_running_string
        )
        self.daemon_process_status_checkbox_string_var.set(var)

    def update_xlite_valid_config_checkbox(self):
        # xlite_valid_config_checkbox_state
        valid_config = bool(self.parent.utility.xlite_conf_local)
        self.valid_config_checkbox_state.set(valid_config)
        # self.xlite_valid_config_checkbox_string_var
        var = (
            widgets_strings.xlite_valid_config_string if valid_config else widgets_strings.xlite_not_valid_config_string
        )
        self.valid_config_checkbox_string_var.set(var)

    def update_xlite_daemon_valid_config_checkbox(self):
        # xlite_daemon_valid_config_checkbox_state
        valid_config = bool(
            self.parent.utility.xlite_daemon_confs_local and "master" in self.parent.utility.xlite_daemon_confs_local
        )
        self.daemon_valid_config_checkbox_state.set(valid_config)
        # self.xlite_daemon_valid_config_checkbox_string_var

        var = (
            widgets_strings.xlite_daemon_valid_config_string
            if valid_config
            else widgets_strings.xlite_daemon_not_valid_config_string
        )
        self.daemon_valid_config_checkbox_string_var.set(var)

    def update_xlite_reverse_proxy_process_status(self):
        """No-op keeper: reverse-proxy panel removed; XliteManager still polls this hook."""
