import os
from threading import Thread

import customtkinter as ctk

import widgets_strings
from gui.layout import tokens
from gui.layout.base_frame import BaseFrameManager
from gui.layout.widgets import make_button, make_caption, make_checkbox, make_entry, make_label
from utilities import utils
from utilities.app_container import get_container


class BlocknetCoreFrameManager(BaseFrameManager):
    panel = "core"

    def __init__(self, parent):
        super().__init__(parent)

        self.label = make_caption(self.title_frame, widgets_strings.blocknet_frame_title_string)

        self.data_path_label = make_label(self.title_frame, text=widgets_strings.blocknet_data_path_label_string)

        self.data_path_entry_string_var = ctk.StringVar(value=self.parent.utility.data_folder)
        self.data_path_entry = make_entry(
            self.title_frame,
            textvariable=self.data_path_entry_string_var,
            width=tokens.ENTRY_W,
        )

        # Button for setting custom path
        self.custom_path_button = make_button(
            self.title_frame,
            text=widgets_strings.blocknet_set_custom_path_string,
            command=self.open_custom_path_dialog,
        )

        # Button for downloading blocknet bootstrap
        self.download_bootstrap_string_var = ctk.StringVar(value="")
        self.download_bootstrap_button = make_button(
            self.title_frame,
            image=self.root_gui.transparent_img,
            textvariable=self.download_bootstrap_string_var,
            command=self.download_bootstrap_command,
        )

        # Checkboxes
        self.data_path_status_checkbox_state = ctk.BooleanVar()
        self.data_path_status_checkbox_string_var = ctk.StringVar(value="Data Path")
        self.data_path_status_checkbox = make_checkbox(
            self.master_frame,
            variable=self.data_path_status_checkbox_state,
            textvariable=self.data_path_status_checkbox_string_var,
        )

        self.process_status_checkbox_state = ctk.BooleanVar()
        self.process_status_checkbox_string_var = ctk.StringVar(value="")
        self.process_status_checkbox = make_checkbox(
            self.master_frame,
            variable=self.process_status_checkbox_state,
            textvariable=self.process_status_checkbox_string_var,
        )

        self.conf_status_checkbox_state = ctk.BooleanVar()
        self.conf_status_checkbox_string_var = ctk.StringVar(value="")
        self.conf_status_checkbox = make_checkbox(
            self.master_frame,
            variable=self.conf_status_checkbox_state,
            textvariable=self.conf_status_checkbox_string_var,
        )

        self.rpc_connection_checkbox_state = ctk.BooleanVar()
        self.rpc_connection_checkbox_string_var = ctk.StringVar(value="")
        self.rpc_connection_checkbox = make_checkbox(
            self.master_frame,
            variable=self.rpc_connection_checkbox_state,
            textvariable=self.rpc_connection_checkbox_string_var,
        )

    def update_blocknet_bootstrap_button(self):
        bootstrap_download_in_progress = bool(self.parent.utility.bootstrap_checking)
        enabled = (
            self.parent.utility.data_folder
            and not bootstrap_download_in_progress
            and not self.parent.blocknet_process_running
        )
        if enabled:
            utils.enable_button(self.download_bootstrap_button, img=self.root_gui.install_img)
        else:
            utils.disable_button(self.download_bootstrap_button, img=self.root_gui.install_greyed_img)
        if bootstrap_download_in_progress:
            if self.parent.utility.bootstrap_percent_download:
                var = f"{self.parent.utility.bootstrap_percent_download:.1f}%"
            elif self.parent.utility.bootstrap_extracting:
                var = "Unpacking"
            else:
                var = "Loading"
        else:
            var = "Bootstrap"
        self.download_bootstrap_string_var.set(var)

    def update_blocknet_process_status_checkbox(self):
        # blocknet_process_status_checkbox_string_var
        var = (
            widgets_strings.blocknet_running_string
            if self.parent.blocknet_process_running
            else widgets_strings.blocknet_not_running_string
        )
        self.process_status_checkbox_string_var.set(var)
        # blocknet_process_status_checkbox_state
        self.process_status_checkbox_state.set(self.parent.blocknet_process_running)

    def update_blocknet_custom_path_button(self):
        # blocknet_custom_path_button
        bootstrap_download_in_progress = (
            self.parent.utility.bootstrap_checking or self.parent.utility.bootstrap_percent_download
        )
        condition = not self.parent.blocknet_process_running and not bootstrap_download_in_progress
        if condition:
            utils.enable_button(self.custom_path_button)
        else:
            utils.disable_button(self.custom_path_button)

    def update_blocknet_conf_status_checkbox(self):
        # blocknet_conf_status_checkbox_state
        conf_exist_and_parsed = bool(self.parent.utility.blocknet_conf_local and self.parent.utility.xbridge_conf_local)
        self.conf_status_checkbox_state.set(conf_exist_and_parsed)

        # blocknet_conf_status_checkbox_string_var
        var = (
            widgets_strings.blocknet_valid_config_string
            if conf_exist_and_parsed
            else widgets_strings.blocknet_not_valid_config_string
        )
        self.conf_status_checkbox_string_var.set(var)

    def update_blocknet_data_path_status_checkbox(self):
        # blocknet_data_path_status_checkbox_state
        exist = self.parent.utility.check_data_folder_existence()
        self.data_path_status_checkbox_state.set(exist)

        # blocknet_data_path_status_checkbox_string_var
        var = (
            widgets_strings.blocknet_data_path_created_string
            if exist
            else widgets_strings.blocknet_data_path_notfound_string
        )
        self.data_path_status_checkbox_string_var.set(var)

    def update_blocknet_rpc_connection_checkbox(self):
        # blocknet_rpc_connection_checkbox_state
        self.rpc_connection_checkbox_state.set(self.parent.utility.valid_rpc)

        # blocknet_rpc_connection_checkbox_string_var
        var = (
            widgets_strings.blocknet_active_rpc_string
            if self.parent.utility.valid_rpc
            else widgets_strings.blocknet_inactive_rpc_string
        )
        self.rpc_connection_checkbox_string_var.set(var)

    def on_custom_path_set(self, custom_path):
        self.parent.utility.set_custom_data_path(custom_path)
        self.data_path_entry_string_var.set(self.parent.utility.data_folder)
        self.parent.custom_path = custom_path
        utils.save_cfg_json("custom_path", custom_path)

    def open_custom_path_dialog(self):
        expanded_path = None
        print(f"custom_path: {self.root_gui.custom_path}")

        if self.root_gui.custom_path is None:
            # Get the default path based on the system
            container = get_container()
            path = container.conf_data.blocknet_default_paths.get(container.system)
            if path:
                expanded_path = os.path.expandvars(os.path.expanduser(path))
            # Check if the expanded path exists
            if expanded_path and os.path.exists(expanded_path):
                initialdir = expanded_path
            else:
                # Path doesn't exist, prune latest folder
                if expanded_path:
                    parent_dir = os.path.dirname(expanded_path)
                    initialdir = parent_dir if os.path.exists(parent_dir) else None  # fallback if parent doesn't exist
                else:
                    initialdir = None
        else:
            # Use the custom path if provided
            initialdir = self.root_gui.custom_path

        print(f"initialdir: {initialdir}")

        # Open the directory selection dialog
        custom_path = ctk.filedialog.askdirectory(
            parent=self.root_gui,
            title=widgets_strings.blocknet_custom_path_dialog_title_string,
            mustexist=False,
            initialdir=initialdir,
        )

        if custom_path:
            self.on_custom_path_set(custom_path)

    def download_bootstrap_command(self):
        utils.disable_button(self.download_bootstrap_button, img=self.root_gui.install_greyed_img)
        self.parent.bootstrap_thread = Thread(target=self.parent.utility.download_bootstrap, daemon=True)
        self.parent.bootstrap_thread.start()
