from gui.blocknet_frame_manager import BlocknetCoreFrameManager
from utilities import global_variables
from utilities.blocknet_util import BlocknetUtility


class BlocknetManager:
    def __init__(self, root_gui):
        self.frame_manager = None
        self.root_gui = root_gui
        self.version = [global_variables.blocknet_release_url.split('/')[7]]
        self.blocknet_process_running = False

        self.bootstrap_thread = None

        self.utility = BlocknetUtility(custom_path=self.root_gui.custom_path)

    async def setup(self):
        self.frame_manager = BlocknetCoreFrameManager(self)

        self.root_gui.after(0, self.update_status_blocknet_core)

    def check_config(self):
        use_xlite = bool(self.root_gui.xlite_manager.utility.xlite_daemon_confs_local)
        if use_xlite:
            xlite_daemon_conf = self.root_gui.xlite_manager.utility.xlite_daemon_confs_local
        else:
            xlite_daemon_conf = None
        self.utility.compare_and_update_local_conf(xlite_daemon_conf)

    def update_status_blocknet_core(self):
        self.frame_manager.update_blocknet_bootstrap_button()
        self.frame_manager.update_blocknet_process_status_checkbox()
        self.frame_manager.update_blocknet_custom_path_button()
        self.frame_manager.update_blocknet_conf_status_checkbox()
        self.frame_manager.update_blocknet_data_path_status_checkbox()
        self.frame_manager.update_blocknet_rpc_connection_checkbox()
        self.root_gui.after(2000, self.update_status_blocknet_core)
