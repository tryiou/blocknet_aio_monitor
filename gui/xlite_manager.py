import logging

from gui.xlite_frame_manager import XliteFrameManager
from utilities import global_variables
from utilities.bin_handlers.xlite_handler import XliteHandler
from utilities.bin_handlers.xlite_reverse_proxy_handler import XliteReverseProxyHandler

logger = logging.getLogger(__name__)


class XliteManager:
    def __init__(self, root_gui):
        self.root_gui = root_gui

        self.frame_manager = None
        self.utility = XliteHandler()

        self.version = [global_variables.xlite_release_url.split('/')[7]]
        self.process_running = False
        self.daemon_process_running = False

    async def setup(self):
        self.frame_manager = XliteFrameManager(self)
        self.reverse_proxy = XliteReverseProxyHandler()
        self.reverse_proxy_running = False
        try:
            self.reverse_proxy.start()
        except Exception as e:
            logger.error(f"Proxy init failed: {e}")
        self.root_gui.after(0, self.update_status_xlite)

    def refresh_xlite_confs(self):
        self.utility.parse_xlite_conf()
        self.utility.parse_xlite_daemon_conf()

    def detect_new_xlite_install_and_add_to_xbridge(self):
        if not self.root_gui.disable_daemons_conf_check and self.utility.valid_coins_rpc:
            self.root_gui.blocknet_manager.utility.check_xbridge_conf(self.utility.xlite_daemon_confs_local)
            if self.root_gui.blocknet_manager.blocknet_process_running and self.root_gui.blocknet_manager.utility.valid_rpc:
                logger.debug("dxloadxbridgeConf")
                self.root_gui.blocknet_manager.utility.blocknet_rpc.send_rpc_request("dxloadxbridgeConf")
            self.root_gui.disable_daemons_conf_check = True
        if self.root_gui.disable_daemons_conf_check and not self.utility.valid_coins_rpc:
            self.root_gui.disable_daemons_conf_check = False

    def update_status_xlite(self):
        self.detect_new_xlite_install_and_add_to_xbridge()
        self.frame_manager.update_xlite_process_status_checkbox()
        self.frame_manager.update_xlite_store_password_button()
        self.frame_manager.update_xlite_daemon_process_status()
        self.frame_manager.update_xlite_valid_config_checkbox()
        self.frame_manager.update_xlite_daemon_valid_config_checkbox()
        # Update proxy status
        self.reverse_proxy_running = (
            self.reverse_proxy.port_occupied() or
            self.reverse_proxy.running_locally
        )
        self.frame_manager.update_xlite_reverse_proxy_process_status()
        self.root_gui.after(2000, self.update_status_xlite)
