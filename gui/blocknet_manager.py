from gui.blocknet_frame_manager import BlocknetCoreFrameManager
from utilities import global_variables
from utilities.blocknet_core import BlocknetUtility


class BlocknetManager:
    def __init__(self, parent, master_frame, title_frame):
        self.frame_manager = None
        self.parent = parent
        self.title_frame = title_frame
        self.master_frame = master_frame
        self.blocknet_version = [global_variables.blocknet_release_url.split('/')[7]]
        self.blocknet_process_running = False

        self.bootstrap_thread = None

        self.utility = BlocknetUtility(custom_path=self.parent.custom_path)

    async def setup(self):
        self.frame_manager = BlocknetCoreFrameManager(self, self.master_frame, self.title_frame)

    def check_config(self):
        use_xlite = bool(self.parent.xlite_manager.utility.xlite_daemon_confs_local)
        if use_xlite:
            xlite_daemon_conf = self.parent.xlite_manager.utility.xlite_daemon_confs_local
        else:
            xlite_daemon_conf = None
        self.utility.compare_and_update_local_conf(xlite_daemon_conf)
