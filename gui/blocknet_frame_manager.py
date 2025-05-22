import os
from threading import Thread

import customtkinter as ctk

import custom_tk_mods.ctkCheckBox as ctkCheckBoxMod
import widgets_strings
from gui.constants import BUTTON_WIDTH, PANEL_CHECKBOXES_WIDTH, HEADER_FRAMES_STICKY, CORNER_RADIUS, \
    CHECK_BOXES_STICKY, BLOCKNET_DATADIR_INPUT_WIDTH
from utilities import utils, global_variables


class BlocknetCoreFrameManager:
    def __init__(self, parent):
        self.root_gui = parent.root_gui
        self.parent = parent
        self.master_frame = ctk.CTkFrame(master=self.root_gui)
        self.title_frame = ctk.CTkFrame(self.master_frame)

        self.label = ctk.CTkLabel(self.title_frame,
                                  text=widgets_strings.blocknet_frame_title_string,
                                  anchor=HEADER_FRAMES_STICKY)  # , width=FRAME_WIDTH)

        self.data_path_label = ctk.CTkLabel(self.title_frame, text="Data Path: ")

        self.data_path_entry_string_var = ctk.StringVar(value=self.parent.utility.data_folder)
        self.data_path_entry = ctk.CTkEntry(self.title_frame,
                                            textvariable=self.data_path_entry_string_var,
                                            state='normal',
                                            width=BLOCKNET_DATADIR_INPUT_WIDTH)
        self.data_path_entry.configure(state='readonly')

        # Button for setting custom path
        self.custom_path_button = ctk.CTkButton(self.title_frame,
                                                text=widgets_strings.blocknet_set_custom_path_string,
                                                command=self.open_custom_path_dialog,
                                                width=BUTTON_WIDTH)

        # Button for downloading blocknet bootstrap
        self.download_bootstrap_string_var = ctk.StringVar(value="")
        self.download_bootstrap_button = ctk.CTkButton(self.title_frame,
                                                       image=self.root_gui.transparent_img,
                                                       textvariable=self.download_bootstrap_string_var,
                                                       command=self.download_bootstrap_command,
                                                       width=BUTTON_WIDTH)

        # Checkboxes
        self.data_path_status_checkbox_state = ctk.BooleanVar()
        self.data_path_status_checkbox_string_var = ctk.StringVar(value="Data Path")
        self.data_path_status_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                                    textvariable=self.data_path_status_checkbox_string_var,
                                                                    variable=self.data_path_status_checkbox_state,
                                                                    state='disabled',
                                                                    corner_radius=CORNER_RADIUS,
                                                                    width=PANEL_CHECKBOXES_WIDTH)

        self.process_status_checkbox_state = ctk.BooleanVar()
        self.process_status_checkbox_string_var = ctk.StringVar(value='')
        self.process_status_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                                  textvariable=self.process_status_checkbox_string_var,
                                                                  variable=self.process_status_checkbox_state,
                                                                  state='disabled',
                                                                  corner_radius=CORNER_RADIUS,
                                                                  width=PANEL_CHECKBOXES_WIDTH)

        self.conf_status_checkbox_state = ctk.BooleanVar()
        self.conf_status_checkbox_string_var = ctk.StringVar(value='')
        self.conf_status_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                               textvariable=self.conf_status_checkbox_string_var,
                                                               variable=self.conf_status_checkbox_state,
                                                               corner_radius=CORNER_RADIUS,
                                                               state='disabled',
                                                               width=PANEL_CHECKBOXES_WIDTH)

        self.rpc_connection_checkbox_state = ctk.BooleanVar()
        self.rpc_connection_checkbox_string_var = ctk.StringVar(value='')
        self.rpc_connection_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                                  textvariable=self.rpc_connection_checkbox_string_var,
                                                                  variable=self.rpc_connection_checkbox_state,
                                                                  corner_radius=CORNER_RADIUS,
                                                                  state='disabled',
                                                                  width=PANEL_CHECKBOXES_WIDTH)  # , disabledforeground='black')

    def grid_widgets(self, x, y):
        # Grid all widgets in this frame
        self.label.grid(row=x, column=y, columnspan=2, padx=5, pady=5, sticky="w")
        self.data_path_label.grid(row=x + 1, column=y, padx=5, pady=5, sticky="w")
        self.data_path_entry.grid(row=x + 1, column=y + 1, padx=5, pady=5, sticky="we")
        self.custom_path_button.grid(row=x + 1, column=y + 3, padx=5, pady=5, sticky="ew")
        self.download_bootstrap_button.grid(row=x, column=y + 3, padx=5, pady=5, sticky="ew")
        self.data_path_status_checkbox.grid(row=x + 2, column=y, padx=5, pady=5, sticky=CHECK_BOXES_STICKY)
        self.process_status_checkbox.grid(row=x + 3, column=y, padx=5, pady=5, sticky=CHECK_BOXES_STICKY)
        self.conf_status_checkbox.grid(row=x + 2, column=y + 1, padx=5, pady=5, sticky=CHECK_BOXES_STICKY)
        self.rpc_connection_checkbox.grid(row=x + 3, column=y + 1, padx=5, pady=5, sticky=CHECK_BOXES_STICKY)

    def update_blocknet_bootstrap_button(self):
        bootstrap_download_in_progress = bool(self.parent.utility.bootstrap_checking)
        enabled = (self.parent.utility.data_folder and not bootstrap_download_in_progress and
                   not self.parent.blocknet_process_running)
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
        var = widgets_strings.blocknet_running_string if self.parent.blocknet_process_running else widgets_strings.blocknet_not_running_string
        self.process_status_checkbox_string_var.set(var)
        # blocknet_process_status_checkbox_state
        self.process_status_checkbox_state.set(self.parent.blocknet_process_running)

    def update_blocknet_custom_path_button(self):
        # blocknet_custom_path_button
        bootstrap_download_in_progress = (
                self.parent.utility.bootstrap_checking or self.parent.utility.bootstrap_percent_download)
        condition = (not self.parent.blocknet_process_running and not bootstrap_download_in_progress)
        if condition:
            utils.enable_button(self.custom_path_button)
        else:
            utils.disable_button(self.custom_path_button)

    def update_blocknet_conf_status_checkbox(self):
        # blocknet_conf_status_checkbox_state
        conf_exist_and_parsed = bool(
            self.parent.utility.blocknet_conf_local and self.parent.utility.xbridge_conf_local)
        self.conf_status_checkbox_state.set(conf_exist_and_parsed)

        # blocknet_conf_status_checkbox_string_var
        var = widgets_strings.blocknet_valid_config_string if conf_exist_and_parsed else widgets_strings.blocknet_not_valid_config_string
        self.conf_status_checkbox_string_var.set(var)

    def update_blocknet_data_path_status_checkbox(self):
        # blocknet_data_path_status_checkbox_state
        exist = self.parent.utility.check_data_folder_existence()
        self.data_path_status_checkbox_state.set(exist)

        # blocknet_data_path_status_checkbox_string_var
        var = widgets_strings.blocknet_data_path_created_string if exist else widgets_strings.blocknet_data_path_notfound_string
        self.data_path_status_checkbox_string_var.set(var)

    def update_blocknet_rpc_connection_checkbox(self):
        # blocknet_rpc_connection_checkbox_state
        self.rpc_connection_checkbox_state.set(self.parent.utility.valid_rpc)

        # blocknet_rpc_connection_checkbox_string_var
        var = widgets_strings.blocknet_active_rpc_string if self.parent.utility.valid_rpc else widgets_strings.blocknet_inactive_rpc_string
        self.rpc_connection_checkbox_string_var.set(var)

    def on_custom_path_set(self, custom_path):
        self.parent.utility.set_custom_data_path(custom_path)
        self.data_path_entry_string_var.set(self.parent.utility.data_folder)
        self.parent.custom_path = custom_path
        utils.save_cfg_json('custom_path', custom_path)

    def open_custom_path_dialog(self):
        expanded_path = None
        print(f"custom_path: {self.root_gui.custom_path}")

        if self.root_gui.custom_path is None:
            # Get the default path based on the system
            path = global_variables.conf_data.blocknet_default_paths.get(global_variables.system)
            if path:
                expanded_path = os.path.expandvars(os.path.expanduser(path))
            # Check if the expanded path exists
            if expanded_path and os.path.exists(expanded_path):
                initialdir = expanded_path
            else:
                # Path doesn't exist, prune latest folder
                if expanded_path:
                    parent_dir = os.path.dirname(expanded_path)
                    # Check if parent directory exists
                    if os.path.exists(parent_dir):
                        initialdir = parent_dir
                    else:
                        initialdir = None  # fallback if parent doesn't exist
                else:
                    initialdir = None
        else:
            # Use the custom path if provided
            initialdir = self.root_gui.custom_path

        print(f"initialdir: {initialdir}")

        # Open the directory selection dialog
        custom_path = ctk.filedialog.askdirectory(
            parent=self.root_gui,
            title="Select Custom Path for Blocknet Core Datadir",
            mustexist=False,
            initialdir=initialdir
        )

        if custom_path:
            self.on_custom_path_set(custom_path)

    def download_bootstrap_command(self):
        utils.disable_button(self.download_bootstrap_button, img=self.root_gui.install_greyed_img)
        self.parent.bootstrap_thread = Thread(target=self.parent.utility.download_bootstrap, daemon=True)
        self.parent.bootstrap_thread.start()
