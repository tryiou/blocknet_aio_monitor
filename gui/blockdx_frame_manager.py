import os

import customtkinter as ctk

import widgets_strings
from gui.layout import tokens
from gui.layout.base_frame import BaseFrameManager
from gui.layout.widgets import make_caption, make_checkbox
from utilities.app_container import get_container


class BlockDxFrameManager(BaseFrameManager):
    panel = "blockdx"

    def __init__(self, parent):
        super().__init__(parent)

        self.label = make_caption(
            self.title_frame,
            widgets_strings.blockdx_frame_title_string,
            width=tokens.BLOCKDX_LABEL_W,
        )

        self.process_status_checkbox_state = ctk.BooleanVar()
        self.process_status_checkbox_string_var = ctk.StringVar(value="")
        self.process_status_checkbox = make_checkbox(
            self.master_frame,
            variable=self.process_status_checkbox_state,
            textvariable=self.process_status_checkbox_string_var,
        )

        self.valid_config_checkbox_state = ctk.BooleanVar()
        self.valid_config_checkbox_string_var = ctk.StringVar(value="")
        self.valid_config_checkbox = make_checkbox(
            self.master_frame,
            variable=self.valid_config_checkbox_state,
            textvariable=self.valid_config_checkbox_string_var,
        )

    def update_blockdx_process_status_checkbox(self):
        # blockdx_process_status_checkbox_state
        self.process_status_checkbox_state.set(self.parent.process_running)

        # blockdx_process_status_checkbox_string_var
        var = (
            widgets_strings.blockdx_running_string
            if self.parent.process_running
            else widgets_strings.blockdx_not_running_string
        )
        self.process_status_checkbox_string_var.set(var)

    def update_blockdx_config_button_checkbox(self):
        # blockdx_valid_config_checkbox_state
        # blockdx_check_config_button
        valid_core_setup = bool(self.root_gui.blocknet_manager.utility.data_folder) and bool(
            self.root_gui.blocknet_manager.utility.blocknet_conf_local
        )
        if valid_core_setup and self.root_gui.blocknet_manager.utility.valid_rpc:
            var = (
                widgets_strings.blockdx_valid_config_string
                if self.parent.is_config_sync
                else widgets_strings.blockdx_not_valid_config_string
            )
            self.valid_config_checkbox_string_var.set(var)
        else:
            self.valid_config_checkbox_string_var.set(widgets_strings.blockdx_missing_blocknet_config_string)

        if valid_core_setup:
            xbridgeconfpath = os.path.join(self.root_gui.blocknet_manager.utility.data_folder, "xbridge.conf")
            rpc_user = self.root_gui.blocknet_manager.utility.blocknet_conf_local.get("global", {}).get("rpcuser")
            rpc_password = self.root_gui.blocknet_manager.utility.blocknet_conf_local.get("global", {}).get(
                "rpcpassword"
            )

            # blockdx_valid_config_checkbox_state
            blockdx_conf = self.parent.utility.blockdx_conf_local
            self.parent.is_config_sync = (
                bool(blockdx_conf)
                and blockdx_conf.get("user") == rpc_user
                and blockdx_conf.get("password") == rpc_password
                and blockdx_conf.get("xbridgeConfPath") == xbridgeconfpath
                and isinstance(blockdx_conf.get("selectedWallets"), list)
                and get_container().conf_data.blockdx_selectedWallets_blocknet
                in blockdx_conf.get("selectedWallets", [])
            )
            self.valid_config_checkbox_state.set(
                self.parent.is_config_sync and self.root_gui.blocknet_manager.utility.valid_rpc
            )

        else:
            self.valid_config_checkbox_state.set(False)
