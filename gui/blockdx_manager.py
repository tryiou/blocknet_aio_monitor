import os

from gui.blockdx_frame_manager import BlockDxFrameManager
from utilities import global_variables
from utilities.bin_handlers.blockdx_handler import BlockDXHandler


class BlockDXManager:
    def __init__(self, root_gui):
        self.frame_manager = None
        self.root_gui = root_gui
        self.utility = BlockDXHandler()
        self.version = [global_variables.blockdx_release_url.split('/')[7]]
        self.process_running = False
        self.is_config_sync = None

    async def setup(self):
        self.frame_manager = BlockDxFrameManager(self)
        self.root_gui.after(0, self.update_status_blockdx)

    def blockdx_check_config(self):
        """
        Checks and updates the local BlockDX configuration based on Blocknet settings.
        """
        blocknet_utility = self.root_gui.blocknet_manager.utility
        if not (blocknet_utility.data_folder and blocknet_utility.blocknet_conf_local):
            return  # Blocknet configuration is not available

        xbridge_conf_path = os.path.normpath(os.path.join(blocknet_utility.data_folder, "xbridge.conf"))
        rpc_user = blocknet_utility.blocknet_conf_local.get('global', {}).get('rpcuser')
        rpc_password = blocknet_utility.blocknet_conf_local.get('global', {}).get('rpcpassword')

        self.utility.compare_and_update_local_conf(xbridge_conf_path, rpc_user, rpc_password)

    def update_status_blockdx(self):
        self.frame_manager.update_blockdx_process_status_checkbox()
        self.frame_manager.update_blockdx_config_button_checkbox()
        self.root_gui.after(2000, self.update_status_blockdx)
