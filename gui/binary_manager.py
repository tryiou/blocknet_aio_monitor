import logging
import os
import shutil
import time
from threading import Thread

from gui.binary_frame_manager import BinaryFrameManager
from utilities import utils, global_variables


class BinaryManager:
    def __init__(self, parent, master_frame, title_frame):
        self.parent = parent
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

    def setup(self):
        self.frame_manager = BinaryFrameManager(self, self.master_frame, self.title_frame)

    def start_or_close_xlite(self):
        img = self.parent.stop_greyed_img if self.parent.xlite_manager.process_running else self.parent.start_greyed_img
        utils.disable_button(self.frame_manager.xlite_start_close_button, img=img)
        self.disable_start_xlite_button = True
        if self.parent.xlite_manager.process_running:
            self.parent.xlite_t1 = Thread(target=self.parent.xlite_manager.utility.close_xlite)
            self.parent.xlite_t1.start()
        else:
            utils.disable_button(self.frame_manager.xlite_start_close_button, img=self.parent.start_greyed_img)
            if self.parent.stored_password:
                env_vars = [{"CC_WALLET_PASS": self.parent.stored_password}, {"CC_WALLET_AUTOLOGIN": 'true'}]
            else:
                env_vars = []
            self.parent.xlite_t2 = Thread(
                target=lambda: self.parent.xlite_manager.utility.start_xlite(env_vars=env_vars))
            self.parent.xlite_t2.start()
        self.parent.after(self.parent.time_disable_button, self.enable_xlite_start_button)

    def start_or_close_blocknet(self):
        img = self.parent.stop_greyed_img if self.parent.blocknet_manager.blocknet_process_running else self.parent.start_greyed_img
        utils.disable_button(self.frame_manager.blocknet_start_close_button, img=img)
        self.disable_start_blocknet_button = True
        if self.parent.blocknet_manager.blocknet_process_running:
            self.parent.blocknet_t1 = Thread(target=self.parent.blocknet_manager.utility.close_blocknet)
            self.parent.blocknet_t1.start()
        else:
            self.parent.blocknet_manager.check_config()
            self.parent.blocknet_t2 = Thread(target=self.parent.blocknet_manager.utility.start_blocknet)
            self.parent.blocknet_t2.start()
        self.parent.after(self.parent.time_disable_button, self.enable_blocknet_start_button)

    def start_or_close_blockdx(self):
        img = self.parent.stop_greyed_img if self.parent.blockdx_manager.process_running else self.parent.start_greyed_img
        utils.disable_button(self.frame_manager.blockdx_start_close_button, img=img)
        self.disable_start_blockdx_button = True
        if self.parent.blockdx_manager.process_running:
            self.parent.blockdx_t1 = Thread(target=self.parent.blockdx_manager.utility.close_blockdx)
            self.parent.blockdx_t1.start()
        else:
            self.parent.blockdx_manager.blockdx_check_config()
            self.parent.blockdx_t2 = Thread(target=self.parent.blockdx_manager.utility.start_blockdx)
            self.parent.blockdx_t2.start()
        self.parent.after(self.parent.time_disable_button, self.enable_blockdx_start_button)

    def install_delete_blocknet_command(self):
        blocknet_boolvar = self.frame_manager.blocknet_installed_boolvar.get()
        if blocknet_boolvar:
            self.delete_blocknet_command()
        else:
            self.download_blocknet_command()

    def download_blocknet_command(self):
        utils.disable_button(self.frame_manager.install_delete_blocknet_button, img=self.parent.install_greyed_img)
        self.download_blocknet_thread = Thread(target=self.parent.blocknet_manager.utility.download_blocknet_bin,
                                               daemon=True)
        self.download_blocknet_thread.start()

    def delete_blocknet_command(self):
        blocknet_pruned_version = self.parent.blocknet_manager.blocknet_version[0].replace('v', '')
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
        utils.disable_button(self.frame_manager.install_delete_blockdx_button, img=self.parent.install_greyed_img)
        self.download_blockdx_thread = Thread(target=self.parent.blockdx_manager.utility.download_blockdx_bin,
                                              daemon=True)
        self.download_blockdx_thread.start()

    def delete_blockdx_command(self):
        blockdx_pruned_version = self.parent.version[0].replace('v', '')
        for item in os.listdir(global_variables.aio_folder):
            item_path = os.path.join(global_variables.aio_folder, item)
            if global_variables.system == 'Darwin':
                blockdx_filename = os.path.basename(global_variables.blockdx_release_url)
                if os.path.isfile(item_path):
                    if blockdx_filename in item_path:
                        self.parent.blockdx_manager.unmount_dmg()
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
        utils.disable_button(self.frame_manager.install_delete_xlite_button, img=self.parent.install_greyed_img)
        self.download_xlite_thread = Thread(target=self.parent.xlite_manager.utility.download_xlite_bin, daemon=True)
        self.download_xlite_thread.start()

    def delete_xlite_command(self):

        xlite_pruned_version = self.parent.xlite_version[0].replace('v', '')
        for item in os.listdir(global_variables.aio_folder):
            item_path = os.path.join(global_variables.aio_folder, item)
            if global_variables.system == 'Darwin':
                xlite_filename = os.path.basename(global_variables.xlite_release_url)
                if os.path.isfile(item_path):
                    if xlite_filename in item_path:
                        self.parent.xlite_manager.utility.unmount_dmg()
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
