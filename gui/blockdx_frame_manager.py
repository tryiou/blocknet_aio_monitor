import os

import customtkinter as ctk

import custom_tk_mods.ctkCheckBox as ctkCheckBoxMod
import widgets_strings
from config.conf_data import blockdx_selectedWallets_blocknet
from gui.constants import panel_checkboxes_width


class BlockDxFrameManager:
    def __init__(self, parent, master_frame, title_frame):
        self.root_gui = parent.root_gui
        self.parent = parent
        self.master_frame = master_frame
        self.title_frame = title_frame

        # Label for Block-dx frame
        width = 540
        self.label = ctk.CTkLabel(self.title_frame,
                                  text=widgets_strings.blockdx_frame_title_string,
                                  anchor='w',
                                  width=width)

        # Checkboxes
        width_mod = 35
        self.process_status_checkbox_state = ctk.BooleanVar()
        self.process_status_checkbox_string_var = ctk.StringVar(value='')
        self.process_status_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                                  textvariable=self.process_status_checkbox_string_var,
                                                                  variable=self.process_status_checkbox_state,
                                                                  corner_radius=25,
                                                                  state='disabled',
                                                                  width=panel_checkboxes_width - width_mod)

        self.valid_config_checkbox_state = ctk.BooleanVar()
        self.valid_config_checkbox_string_var = ctk.StringVar(value='')
        self.valid_config_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                                textvariable=self.valid_config_checkbox_string_var,
                                                                variable=self.valid_config_checkbox_state,
                                                                corner_radius=25,
                                                                state='disabled',
                                                                width=panel_checkboxes_width - width_mod)  # , disabledforeground='black')

    def grid_widgets(self, x, y, check_boxes_sticky):
        # block-dx
        self.label.grid(row=x, column=y, columnspan=3, padx=5, pady=0)
        self.process_status_checkbox.grid(row=x + 1, column=y, padx=10, pady=5, sticky=check_boxes_sticky)
        self.valid_config_checkbox.grid(row=x + 1, column=y + 1, padx=10, pady=5, sticky=check_boxes_sticky)

    def update_blockdx_process_status_checkbox(self):
        # blockdx_process_status_checkbox_state
        self.process_status_checkbox_state.set(self.parent.process_running)

        # blockdx_process_status_checkbox_string_var
        var = widgets_strings.blockdx_running_string if self.parent.process_running else widgets_strings.blockdx_not_running_string
        self.process_status_checkbox_string_var.set(var)

    def update_blockdx_config_button_checkbox(self):
        # blockdx_valid_config_checkbox_state
        # blockdx_check_config_button
        valid_core_setup = bool(self.root_gui.blocknet_manager.utility.data_folder) and bool(
            self.root_gui.blocknet_manager.utility.blocknet_conf_local)
        if valid_core_setup and self.root_gui.blocknet_manager.utility.valid_rpc:
            var = widgets_strings.blockdx_valid_config_string if self.parent.is_config_sync else widgets_strings.blockdx_not_valid_config_string
            self.valid_config_checkbox_string_var.set(var)
        else:
            self.valid_config_checkbox_string_var.set(widgets_strings.blockdx_missing_blocknet_config_string)

        if valid_core_setup:
            xbridgeconfpath = os.path.join(self.root_gui.blocknet_manager.utility.data_folder, "xbridge.conf")
            rpc_user = self.root_gui.blocknet_manager.utility.blocknet_conf_local.get('global', {}).get('rpcuser')
            rpc_password = self.root_gui.blocknet_manager.utility.blocknet_conf_local.get('global', {}).get(
                'rpcpassword')

            # blockdx_valid_config_checkbox_state
            blockdx_conf = self.parent.utility.blockdx_conf_local
            self.parent.is_config_sync = (
                    bool(blockdx_conf) and
                    blockdx_conf.get('user') == rpc_user and
                    blockdx_conf.get('password') == rpc_password and
                    blockdx_conf.get('xbridgeConfPath') == xbridgeconfpath and
                    isinstance(blockdx_conf.get('selectedWallets'), list) and
                    blockdx_selectedWallets_blocknet in blockdx_conf.get('selectedWallets', [])
            )
            self.valid_config_checkbox_state.set(
                (self.parent.is_config_sync and self.root_gui.blocknet_manager.utility.valid_rpc))

        else:
            self.valid_config_checkbox_state.set(False)

    async def update_status_blockdx(self):
        self.update_blockdx_process_status_checkbox()
        self.update_blockdx_config_button_checkbox()
