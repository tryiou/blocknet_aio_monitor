import logging
import os

from gui.blockdx_frame_manager import BlockDxFrameManager
from utilities import global_variables
from utilities.blockdx_util import BlockdxUtility


class BlockDXManager:
    def __init__(self, root_gui, master_frame, title_frame):
        self.frame_manager = None
        self.root_gui = root_gui
        self.title_frame = title_frame
        self.master_frame = master_frame
        self.utility = BlockdxUtility()
        self.version = [global_variables.blockdx_release_url.split('/')[7]]
        self.process_running = False
        self.is_config_sync = None

    async def setup(self):
        self.frame_manager = BlockDxFrameManager(self, self.master_frame, self.title_frame)
        self.root_gui.after(0, self.update_status_blockdx)

    def blockdx_check_config(self):
        # Get required data
        if bool(self.root_gui.blocknet_manager.utility.data_folder and self.root_gui.blocknet_manager.utility.blocknet_conf_local):
            xbridgeconfpath = os.path.normpath(
                os.path.join(self.root_gui.blocknet_manager.utility.data_folder, "xbridge.conf"))
            logging.info(f"xbridgeconfpath: {xbridgeconfpath}")
            rpc_user = self.root_gui.blocknet_manager.utility.blocknet_conf_local.get('global', {}).get('rpcuser')
            rpc_password = self.root_gui.blocknet_manager.utility.blocknet_conf_local.get('global', {}).get(
                'rpcpassword')
            self.utility.compare_and_update_local_conf(xbridgeconfpath, rpc_user, rpc_password)

    def update_status_blockdx(self):
        self.frame_manager.update_blockdx_process_status_checkbox()
        self.frame_manager.update_blockdx_config_button_checkbox()
        self.root_gui.after(1000, self.update_status_blockdx)
