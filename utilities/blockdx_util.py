import copy
import json
import logging
import os
import subprocess
import time

from utilities import global_variables
from utilities.helper_util import UtilityHelper

logging.basicConfig(level=logging.DEBUG)


class BlockdxUtility:
    def __init__(self):
        self.helper = UtilityHelper()
        if global_variables.system == "Darwin":
            self.dmg_mount_path = f"/Volumes/{global_variables.blockdx_volume_name}"
            self.blockdx_exe = os.path.join(global_variables.aio_folder, os.path.basename(global_variables.blockdx_url))
        else:
            self.blockdx_exe = os.path.join(global_variables.aio_folder,
                                            global_variables.conf_data.blockdx_bin_path[global_variables.system],
                                            global_variables.conf_data.blockdx_bin_name[global_variables.system])
        self.binary_percent_download = None
        self.process_running = None
        self.blockdx_process = None
        self.blockdx_conf_local = None
        self.running = True  # flag for async funcs
        self.blockdx_pids = []
        self.parse_blockdx_conf()
        self.downloading_bin = False

    def parse_blockdx_conf(self):
        data_folder = get_blockdx_data_folder()
        file = "app-meta.json"
        file_path = os.path.join(data_folder, file)
        meta_data = {}

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as file:
                    meta_data = json.load(file)
                    logging.info(f"BLOCK-DX: Loaded JSON data ok: [{file_path}]")
            except Exception as e:
                logging.error(f"Error parsing [{file_path}]: {e}, repairing file")
        else:
            logging.warning(f"{file_path} doesn't exist")
            if not os.path.exists(data_folder):
                os.makedirs(data_folder)

        self.blockdx_conf_local = meta_data

    def compare_and_update_local_conf(self, xbridgeconfpath, rpc_user, rpc_password):
        xbridgeconfpath = r"{}".format(xbridgeconfpath)
        data_folder = get_blockdx_data_folder()
        file_path = os.path.join(data_folder, "app-meta.json")
        self.parse_blockdx_conf()
        org_data = copy.deepcopy(self.blockdx_conf_local)
        if not self.blockdx_conf_local:
            meta_data = global_variables.conf_data.blockdx_base_conf
        else:
            meta_data = copy.deepcopy(self.blockdx_conf_local)

        # Update meta_data if changes are needed
        if 'user' not in meta_data or meta_data['user'] != rpc_user:
            meta_data['user'] = rpc_user
            logging.debug("Updated 'user' in meta_data")
        if 'password' not in meta_data or meta_data['password'] != rpc_password:
            meta_data['password'] = rpc_password
            logging.debug("Updated 'password' in meta_data")
        if 'xbridgeConfPath' not in meta_data or meta_data['xbridgeConfPath'] != xbridgeconfpath:
            meta_data['xbridgeConfPath'] = xbridgeconfpath
            logging.debug("Updated 'xbridgeConfPath' in meta_data")

        # Update 'selectedWallets' if needed
        if 'selectedWallets' not in meta_data:
            meta_data['selectedWallets'] = []
            meta_data['selectedWallets'].append(global_variables.conf_data.blockdx_selectedWallets_blocknet)
            logging.debug(
                f"Initialized 'selectedWallets' with '{global_variables.conf_data.blockdx_selectedWallets_blocknet}' in meta_data")
        elif not isinstance(meta_data['selectedWallets'], list):
            logging.warning("'selectedWallets' is not a list. Converting to list.")
            meta_data['selectedWallets'] = [global_variables.conf_data.blockdx_selectedWallets_blocknet]
        elif global_variables.conf_data.blockdx_selectedWallets_blocknet not in meta_data['selectedWallets']:
            meta_data['selectedWallets'].append(global_variables.conf_data.blockdx_selectedWallets_blocknet)
            logging.debug("Updated 'selectedWallets' in meta_data")

        # Save file if changes were made
        if org_data != meta_data:
            with open(file_path, 'w') as file:
                json.dump(meta_data, file, indent=4)
            logging.info("Updated Blockdx config with new data.")
            self.blockdx_conf_local = meta_data
        else:
            logging.info("No changes detected in Blockdx config.")

    def unmount_dmg(self):
        self.helper.handle_dmg(None, self.dmg_mount_path, "unmount")

    def start_blockdx(self):
        if not os.path.exists(self.blockdx_exe):
            # self.downloading_bin = True
            logging.info(f"Blockdx executable not found at {self.blockdx_exe}. Downloading...")
            self.download_blockdx_bin()
            # self.downloading_bin = False

        try:
            # Start the BLOCK-DX process using subprocess
            if global_variables.system == "Darwin":
                # mac mod
                self.helper.handle_dmg(self.blockdx_exe, self.dmg_mount_path, "mount")
                full_path = os.path.join(self.dmg_mount_path,
                                         *global_variables.conf_data.blockdx_bin_name[global_variables.system])
                logging.info(
                    f"volume_name: {global_variables.blockdx_volume_name}, mount_path: {self.dmg_mount_path}, full_path: {full_path}")
                self.blockdx_process = subprocess.Popen([full_path],
                                                        stdout=subprocess.PIPE,
                                                        stderr=subprocess.PIPE,
                                                        stdin=subprocess.PIPE,
                                                        start_new_session=True)
            else:
                self.blockdx_process = subprocess.Popen([self.blockdx_exe],
                                                        stdout=subprocess.PIPE,
                                                        stderr=subprocess.PIPE,
                                                        stdin=subprocess.PIPE,
                                                        start_new_session=True)
            # Check if the process has started
            while self.blockdx_process.pid is None:
                time.sleep(1)  # Wait for 1 second before checking again

            pid = self.blockdx_process.pid
            logging.info(f"Started Blockdx process with PID {pid}: {self.blockdx_exe}")
        except Exception as e:
            logging.error(f"Error: {e}")

    def close_blockdx(self):
        # Close the blockdx subprocess if it exists
        if self.blockdx_process:
            try:
                self.blockdx_process.terminate()
                # logging.info(f"Terminating blockdx subprocess.")
                self.blockdx_process.wait(timeout=60)  # Wait for the process to terminate with a timeout of 60 seconds
                logging.info(f"Closed blockdx subprocess.")
                self.blockdx_process = None
                return
            except subprocess.TimeoutExpired:
                logging.info(f"Force terminating blockdx subprocess.")
                self.kill_blockdx()
                logging.info(f"blockdx subprocess has been force terminated.")
                self.blockdx_process = None
                return
            except Exception as e:
                logging.error(f"Error: {e}")
        else:
            self.close_blockdx_pids()

    def kill_blockdx(self):
        # Kill the blockdx subprocess if it exists
        if self.blockdx_process:
            try:
                self.blockdx_process.kill()
                logging.info(f"Killed blockdx subprocess.")
                self.blockdx_process = None
                return
            except Exception as e:
                logging.error(f"Error: {e}")

    def close_blockdx_pids(self):
        self.helper.terminate_processes(self.blockdx_pids, "BlockDX")

    def download_blockdx_bin(self):
        self.downloading_bin = True
        url = global_variables.conf_data.blockdx_releases_urls.get((global_variables.system, global_variables.machine))

        if url is None:
            raise ValueError(f"Unsupported OS or architecture {global_variables.system} {global_variables.machine}")

        tmp_path = os.path.join(global_variables.aio_folder, "tmp_dx_bin")
        final_path = self.blockdx_exe  # For DMG
        extract_to = global_variables.aio_folder  # For zip/tar.gz

        self.helper.download_file(
            url, tmp_path, final_path, extract_to,
            global_variables.system, "binary_percent_download", self
        )
        self.downloading_bin = False


def get_blockdx_data_folder():
    path = global_variables.conf_data.blockdx_default_paths.get(global_variables.system)
    if path:
        return os.path.expandvars(os.path.expanduser(path))
    else:
        raise ValueError("Unsupported system")
