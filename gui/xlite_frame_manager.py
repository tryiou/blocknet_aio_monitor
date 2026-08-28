import logging
import os

import customtkinter as ctk

import custom_tk_mods.ctkCheckBox as ctkCheckBoxMod
import widgets_strings
from custom_tk_mods import ctkInputDialogMod
from gui.constants import (
    BUTTON_WIDTH,
    CHECK_BOXES_STICKY,
    CORNER_RADIUS,
    HEADER_FRAMES_STICKY,
    PANEL_CHECKBOXES_WIDTH,
    XLITE_FRAME_WIDTH,
)
from utilities import utils

logger = logging.getLogger(__name__)


class XliteFrameManager:
    def __init__(self, parent):
        self.root_gui = parent.root_gui
        self.parent = parent
        self.master_frame = ctk.CTkFrame(master=self.root_gui)
        self.title_frame = ctk.CTkFrame(self.master_frame)

        self.xlite_label = ctk.CTkLabel(
            self.title_frame,
            text=widgets_strings.xlite_frame_title_string,
            anchor=HEADER_FRAMES_STICKY,
            width=XLITE_FRAME_WIDTH,
        )
        # Checkboxes
        self.process_status_checkbox_state = ctk.BooleanVar()
        self.process_status_checkbox_string_var = ctk.StringVar(value="")
        self.process_status_checkbox = ctkCheckBoxMod.CTkCheckBox(
            self.master_frame,
            textvariable=self.process_status_checkbox_string_var,
            variable=self.process_status_checkbox_state,
            corner_radius=CORNER_RADIUS,
            state="disabled",
            width=PANEL_CHECKBOXES_WIDTH,
        )

        self.daemon_process_status_checkbox_state = ctk.BooleanVar()
        self.daemon_process_status_checkbox_string_var = ctk.StringVar(value="")
        self.daemon_process_status_checkbox = ctkCheckBoxMod.CTkCheckBox(
            self.master_frame,
            textvariable=self.daemon_process_status_checkbox_string_var,
            variable=self.daemon_process_status_checkbox_state,
            corner_radius=CORNER_RADIUS,
            state="disabled",
            width=PANEL_CHECKBOXES_WIDTH,
        )

        self.reverse_proxy_process_status_checkbox_state = ctk.BooleanVar()
        self.reverse_proxy_status_str = ctk.StringVar(value=widgets_strings.xlite_reverse_proxy_not_running_string)
        self.reverse_proxy_process_status_checkbox = ctkCheckBoxMod.CTkCheckBox(
            self.master_frame,
            textvariable=self.reverse_proxy_status_str,
            variable=self.reverse_proxy_process_status_checkbox_state,
            corner_radius=CORNER_RADIUS,
            state="disabled",
            width=PANEL_CHECKBOXES_WIDTH,
        )
        self.valid_config_checkbox_state = ctk.BooleanVar()
        self.valid_config_checkbox_string_var = ctk.StringVar(value="")
        self.valid_config_checkbox = ctkCheckBoxMod.CTkCheckBox(
            self.master_frame,
            textvariable=self.valid_config_checkbox_string_var,
            variable=self.valid_config_checkbox_state,
            corner_radius=CORNER_RADIUS,
            state="disabled",
            width=PANEL_CHECKBOXES_WIDTH,
        )

        self.daemon_valid_config_checkbox_state = ctk.BooleanVar()
        self.daemon_valid_config_checkbox_string_var = ctk.StringVar(value="")
        self.daemon_valid_config_checkbox = ctkCheckBoxMod.CTkCheckBox(
            self.master_frame,
            textvariable=self.daemon_valid_config_checkbox_string_var,
            variable=self.daemon_valid_config_checkbox_state,
            corner_radius=CORNER_RADIUS,
            state="disabled",
            width=PANEL_CHECKBOXES_WIDTH,
        )

        # Create the Button widget with a text variable
        self.store_password_button_string_var = ctk.StringVar(value="")
        self.store_password_button = ctk.CTkButton(
            self.title_frame, textvariable=self.store_password_button_string_var, width=BUTTON_WIDTH
        )

        # Bind left-click event
        self.store_password_button.bind("<Button-1>", lambda event: self.xlite_store_password_button_mouse_click(event))

        # Bind right-click event
        self.store_password_button.bind("<Button-3>", lambda event: self.xlite_store_password_button_mouse_click(event))

        # Set button command for normal button clicks
        self.store_password_button.configure(command=self.xlite_store_password_button_mouse_click)

    def xlite_store_password_button_mouse_click(self, event=None):
        # Function to handle storing password
        # Check if the right mouse button was clicked
        if event and event.num == 3:
            # wipe_stored_password
            logger.info("Right click detected")
            # Prevent the right-click event from propagating further
            utils.remove_cfg_json_key("xl_pass")
            # Note: remove_cfg_json_key will also delete encryption key from keyring
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
            # store_salted_pass
            logger.info("Left click detected")
            fg_color = self.master_frame.cget("fg_color")
            password = ctkInputDialogMod.CTkInputDialog(
                title="Store XLite Password", text="Enter XLite password:", show="*", fg_color=fg_color
            ).get_input()
            if password:
                # Generate key and store in keyring
                encryption_key = utils.generate_key()
                if encryption_key is None:
                    logger.error("Failed to generate encryption key")
                    return "break"

                # Encrypt password using keyring
                salted_pass = utils.encrypt_password(password)
                if salted_pass is None:
                    logger.error("Failed to encrypt password")
                    return "break"

                # Store only encrypted password in JSON (key is in keyring)
                utils.save_cfg_json(key="xl_pass", data=salted_pass)
                # Store the password in a variable
                self.root_gui.stored_password = password
                # Eager UI refresh — instant feedback
                try:
                    self.update_xlite_store_password_button()
                except Exception as e:  # debug logged
                    logger.debug(f"Eager password button update failed: {e}")
            else:
                logger.info("No password entered.")
            # Perform actions for left-click (if needed)
            return "break"

    def grid_widgets(self, x, y):
        # xlite
        self.xlite_label.grid(row=x, column=y, padx=5, pady=5)
        self.process_status_checkbox.grid(row=x + 1, column=y, padx=5, pady=5, sticky=CHECK_BOXES_STICKY)
        self.daemon_process_status_checkbox.grid(row=x + 2, column=y, padx=5, pady=5, sticky=CHECK_BOXES_STICKY)
        self.valid_config_checkbox.grid(row=x + 1, column=y + 1, padx=5, pady=5, sticky=CHECK_BOXES_STICKY)
        self.daemon_valid_config_checkbox.grid(row=x + 2, column=y + 1, padx=5, pady=5, sticky=CHECK_BOXES_STICKY)
        # TEMP DISABLE xlite-reverse-proxy widget — keep for restore:
        # self.reverse_proxy_process_status_checkbox.grid(
        #     row=x + 3, column=y, padx=5, pady=5, sticky=CHECK_BOXES_STICKY
        # )
        self.store_password_button.grid(row=x, column=y + 3, padx=2, pady=2, sticky="e")

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
        if self.parent.reverse_proxy_running:
            self.reverse_proxy_status_str.set(widgets_strings.xlite_reverse_proxy_running_string)
            self.reverse_proxy_process_status_checkbox_state.set(True)
        else:
            self.reverse_proxy_status_str.set(widgets_strings.xlite_reverse_proxy_not_running_string)
            self.reverse_proxy_process_status_checkbox_state.set(False)
