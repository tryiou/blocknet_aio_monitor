import logging
import os
import shutil
import time
from threading import Thread

from gui.binary_frame_manager import BinaryFrameManager
from utilities import utils, global_variables


class BinaryManager:
    def __init__(self, root_gui, master_frame, title_frame):
        self.root_gui = root_gui
        self.title_frame = title_frame
        self.master_frame = master_frame
        self.frame_manager = None

        self.last_aio_folder_check_time = None

        self.disable_start_blocknet_button = False
        self.disable_start_xlite_button = False
        self.disable_start_blockdx_button = False

        self.download_blocknet_thread = None
        self.download_blockdx_thread = None
        self.download_xlite_thread = None

    async def setup(self):
        self.frame_manager = BinaryFrameManager(self, self.master_frame, self.title_frame)

    def _start_or_close_binary(self, process_running, stop_func, start_func, button, disable_flag):
        img = self.root_gui.stop_greyed_img if process_running else self.root_gui.start_greyed_img
        utils.disable_button(button, img=img)
        setattr(self, disable_flag,
                True)  # Disable the button flag
        if process_running:
            Thread(target=stop_func).start()
        else:
            Thread(target=start_func).start()
        self.root_gui.after(self.root_gui.time_disable_button, self._enable_binary_start_button, disable_flag)

    def _enable_binary_start_button(self, disable_flag):
        setattr(self, disable_flag, False)

    def start_or_close_blocknet(self):
        if not self.root_gui.blocknet_manager.blocknet_process_running:
            self.root_gui.blocknet_manager.check_config()
        self._start_or_close_binary(
            process_running=self.root_gui.blocknet_manager.blocknet_process_running,
            stop_func=self.root_gui.blocknet_manager.utility.close_blocknet,
            start_func=self.root_gui.blocknet_manager.utility.start_blocknet,
            button=self.frame_manager.blocknet_start_close_button,
            disable_flag='disable_start_blocknet_button'
        )

    def start_or_close_blockdx(self):
        if not self.root_gui.blockdx_manager.process_running:
            self.root_gui.blockdx_manager.blockdx_check_config()
        self._start_or_close_binary(
            process_running=self.root_gui.blockdx_manager.process_running,
            stop_func=self.root_gui.blockdx_manager.utility.close_blockdx,
            start_func=self.root_gui.blockdx_manager.utility.start_blockdx,
            button=self.frame_manager.blockdx_start_close_button,
            disable_flag='disable_start_blockdx_button'
        )

    def start_or_close_xlite(self):
        if not self.root_gui.xlite_manager.process_running:
            if self.root_gui.stored_password:
                env_vars = [{"CC_WALLET_PASS": self.root_gui.stored_password}, {"CC_WALLET_AUTOLOGIN": 'true'}]
            else:
                env_vars = []
        self._start_or_close_binary(
            process_running=self.root_gui.xlite_manager.process_running,
            stop_func=self.root_gui.xlite_manager.utility.close_xlite,
            start_func=lambda: self.root_gui.xlite_manager.utility.start_xlite(env_vars=env_vars),
            button=self.frame_manager.xlite_start_close_button,
            disable_flag='disable_start_xlite_button'
        )

    def install_delete_blocknet_command(self):
        blocknet_boolvar = self.frame_manager.blocknet_installed_boolvar.get()
        if blocknet_boolvar:
            self.delete_blocknet_command()
        else:
            self.download_blocknet_command()

    def download_blocknet_command(self):
        utils.disable_button(self.frame_manager.install_delete_blocknet_button, img=self.root_gui.install_greyed_img)
        self.download_blocknet_thread = Thread(target=self.root_gui.blocknet_manager.utility.download_blocknet_bin,
                                               daemon=True)
        self.download_blocknet_thread.start()

    def delete_blocknet_command(self):
        blocknet_pruned_version = self.root_gui.blocknet_manager.blocknet_version[0].replace('v', '')
        for item in os.listdir(global_variables.aio_folder):
            item_path = os.path.join(global_variables.aio_folder, item)
            if os.path.isdir(item_path):
                # if a wrong version is found, delete it.
                if 'blocknet-' in item:
                    if blocknet_pruned_version in item:
                        logging.info(f"deleting {item_path}")
                        shutil.rmtree(item_path)

    def install_delete_blockdx_command(self):
        blockdx_boolvar = self.frame_manager.blockdx_installed_boolvar.get()
        if blockdx_boolvar:
            self.delete_blockdx_command()
        else:
            self.download_blockdx_command()

    def download_blockdx_command(self):
        utils.disable_button(self.frame_manager.install_delete_blockdx_button, img=self.root_gui.install_greyed_img)
        self.download_blockdx_thread = Thread(target=self.root_gui.blockdx_manager.utility.download_blockdx_bin,
                                              daemon=True)
        self.download_blockdx_thread.start()

    def delete_blockdx_command(self):
        blockdx_pruned_version = self.root_gui.blockdx_manager.version[0].replace('v', '')
        for item in os.listdir(global_variables.aio_folder):
            item_path = os.path.join(global_variables.aio_folder, item)
            if global_variables.system == 'Darwin':
                blockdx_filename = os.path.basename(global_variables.blockdx_release_url)
                if os.path.isfile(item_path):
                    if blockdx_filename in item_path:
                        self.root_gui.blockdx_manager.unmount_dmg()
                        os.remove(item_path)
            else:
                if os.path.isdir(item_path):
                    if 'BLOCK-DX-' in item:
                        if blockdx_pruned_version in item:
                            logging.info(f"deleting {item_path}")
                            shutil.rmtree(item_path)

    def install_delete_xlite_command(self):
        xlite_boolvar = self.frame_manager.xlite_installed_boolvar.get()
        if xlite_boolvar:
            self.delete_xlite_command()
        else:
            self.download_xlite_command()

    def download_xlite_command(self):
        utils.disable_button(self.frame_manager.install_delete_xlite_button, img=self.root_gui.install_greyed_img)
        self.download_xlite_thread = Thread(target=self.root_gui.xlite_manager.utility.download_xlite_bin, daemon=True)
        self.download_xlite_thread.start()

    def delete_xlite_command(self):

        xlite_pruned_version = self.root_gui.xlite_version[0].replace('v', '')
        for item in os.listdir(global_variables.aio_folder):
            item_path = os.path.join(global_variables.aio_folder, item)
            if global_variables.system == 'Darwin':
                xlite_filename = os.path.basename(global_variables.xlite_release_url)
                if os.path.isfile(item_path):
                    if xlite_filename in item_path:
                        self.root_gui.xlite_manager.utility.unmount_dmg()
                        os.remove(item_path)
            else:
                if os.path.isdir(item_path):
                    if 'XLite-' in item:
                        if xlite_pruned_version in item:
                            logging.info(f"deleting {item_path}")
                            shutil.rmtree(item_path)

    def enable_blocknet_start_button(self):
        self.disable_start_blocknet_button = False

    def enable_blockdx_start_button(self):
        self.disable_start_blockdx_button = False

    def enable_xlite_start_button(self):
        self.disable_start_xlite_button = False

    def bins_should_check_aio_folder(self, max_delay=5):
        current_time = time.time()
        if not self.last_aio_folder_check_time or current_time - self.last_aio_folder_check_time >= max_delay:
            self.last_aio_folder_check_time = current_time
            return True
        return False
