import copy
import json
import logging
import os

from utilities import global_variables
from utilities.bin_handlers.base_binutil import BaseBinUtil

# logging.basicConfig(level=logging.DEBUG)
logging.getLogger().setLevel(logging.DEBUG)

class BlockDXHandler(BaseBinUtil):
    def __init__(self):
        super().__init__("Blockdx")
        if global_variables.system == "Darwin":
            self.dmg_mount_path = f"/Volumes/{global_variables.blockdx_volume_name}"
            self.executable_path = os.path.join(global_variables.aio_folder, os.path.basename(global_variables.blockdx_url))
        else:
            self.executable_path = os.path.join(global_variables.aio_folder,
                                                global_variables.conf_data.blockdx_bin_path[global_variables.system],
                                                global_variables.conf_data.blockdx_bin_name[global_variables.system])
        self.process_running = None
        self.blockdx_process = None
        self.blockdx_conf_local = None
        self.running = True  # flag for async funcs
        self.blockdx_pids = []
        self.is_config_sync = False # Initialize is_config_sync
        self.parse_blockdx_conf()

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
            self.is_config_sync = False # Config changed, so not in sync
        else:
            logging.info("No changes detected in Blockdx config.")
            self.is_config_sync = True # No changes, so config is in sync
 
    def start_blockdx(self):
        if not os.path.exists(self.executable_path):
            logging.info(f"Blockdx executable not found at {self.executable_path}. Downloading...")
            self.download_blockdx_bin()
            if not os.path.exists(self.executable_path):
                logging.error("Failed to download Blockdx binary. Aborting start.")
                return # Abort if download failed

        try:
            if global_variables.system == "Darwin":

                self.handle_dmg( "mount")
                full_path = os.path.join(self.dmg_mount_path,
                                         *global_variables.conf_data.blockdx_bin_name[global_variables.system])
                logging.info(
                    f"volume_name: {global_variables.blockdx_volume_name}, mount_path: {self.dmg_mount_path}, full_path: {full_path}")
                command = [full_path]
                cwd = os.path.dirname(full_path)
            else:
                command = [self.executable_path]
                cwd = os.path.dirname(self.executable_path)

            self.blockdx_process = self.start_process(command, cwd=cwd)
            logging.info(f"Started Blockdx process with PID {self.blockdx_process.pid}: {command}")
        except Exception as e:
            logging.error(f"Error: {e}")

    def close_blockdx(self):
        if self.blockdx_process:
            self.graceful_terminate(timeout=10)
        else:
            self.close_blockdx_pids()

    def close_blockdx_pids(self):
        self.terminate_processes(self.blockdx_pids, "BlockDX")

    def download_blockdx_bin(self):
        url = global_variables.conf_data.blockdx_releases_urls.get((global_variables.system, global_variables.machine))
        if url is None:
            raise ValueError(f"Unsupported OS or architecture {global_variables.system} {global_variables.machine}")

        tmp_filename = "tmp_dx_bin"
        return self.download_binary( # Return the result of download_binary
            url,
            tmp_filename,
            self.executable_path,
            global_variables.aio_folder
        )
    
    def unmount_dmg(self):
        if global_variables.system != "Darwin":
            logging.warning(f"Call unmount_dmg with wrong OS, {global_variables.system} ?")
            return
        self.handle_dmg( "unmount")

def get_blockdx_data_folder():
    path = global_variables.conf_data.blockdx_default_paths.get(global_variables.system)
    if path:
        return os.path.expandvars(os.path.expanduser(path))
    else:
        raise ValueError("Unsupported system")
