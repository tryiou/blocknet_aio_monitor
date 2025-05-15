import logging
import os

from gui.blockdx_frame_manager import BlockDxFrameManager
from utilities import global_variables
from utilities.blockdx import BlockdxUtility


class BlockDXManager:
    def __init__(self, parent, master_frame, title_frame):
        self.frame_manager = None
        self.parent = parent
        self.title_frame = title_frame
        self.master_frame = master_frame
        self.utility = BlockdxUtility()
        self.version = [global_variables.blockdx_release_url.split('/')[7]]
        self.process_running = False
        self.is_config_sync = None

    def setup(self):
        self.frame_manager = BlockDxFrameManager(self, self.master_frame, self.title_frame)

    def blockdx_check_config(self):
        # Get required data
        if bool(self.parent.blocknet_manager.utility.data_folder and self.parent.blocknet_manager.utility.blocknet_conf_local):
            xbridgeconfpath = os.path.normpath(
                os.path.join(self.parent.blocknet_manager.utility.data_folder, "xbridge.conf"))
            logging.info(f"xbridgeconfpath: {xbridgeconfpath}")
            rpc_user = self.parent.blocknet_manager.utility.blocknet_conf_local.get('global', {}).get('rpcuser')
            rpc_password = self.parent.blocknet_manager.utility.blocknet_conf_local.get('global', {}).get(
                'rpcpassword')
            self.utility.compare_and_update_local_conf(xbridgeconfpath, rpc_user, rpc_password)
