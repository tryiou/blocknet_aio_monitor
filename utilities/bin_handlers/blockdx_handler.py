import copy
import json
import logging
import os
from typing import Optional

from utilities.app_container import AppContainer, get_container
from utilities.bin_handlers.base_binutil import BaseBinUtil

logger = logging.getLogger(__name__)


class BlockDXHandler(BaseBinUtil):
    def __init__(self, container: Optional[AppContainer] = None):
        super().__init__("Blockdx", container)
        if self.container.system == "Darwin":
            blockdx_volume_name = self.container.blockdx_volume_name
            if blockdx_volume_name:
                self.dmg_mount_path = f"/Volumes/{blockdx_volume_name}"
            else:
                self.dmg_mount_path = None
            blockdx_release_url = self.container.blockdx_release_url
            if blockdx_release_url and self.container.aio_folder:
                self.executable_path = os.path.join(self.container.aio_folder,
                                                    os.path.basename(blockdx_release_url))
            else:
                self.executable_path = None
        else:
            aio_folder = self.container.aio_folder
            curpath = self.container.blockdx_curpath
            bin_name = self.container.blockdx_bin
            if aio_folder and curpath and bin_name:
                self.executable_path = os.path.join(aio_folder, curpath, bin_name)
            else:
                self.executable_path = None
        self.process_running = None
        self.blockdx_process = None
        self.blockdx_conf_local = None
        self.running = True  # flag for async funcs
        self.blockdx_pids = []
        self.is_config_sync = False  # Initialize is_config_sync
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
                    logger.info(f"BLOCK-DX: Loaded JSON data ok: [{file_path}]")
            except Exception as e:
                logger.error(f"Error parsing [{file_path}]: {e}, repairing file")
        else:
            logger.warning(f"{file_path} doesn't exist")
            if not os.path.exists(data_folder):
                os.makedirs(data_folder)

        self.blockdx_conf_local = meta_data

    def compare_and_update_local_conf(self, xbridgeconfpath, rpc_user, rpc_password):
        xbridgeconfpath = r"{}".format(xbridgeconfpath)
        data_folder = get_blockdx_data_folder()
        if not data_folder:
            raise ValueError("BlockDX data folder not configured")
        file_path = os.path.join(data_folder, "app-meta.json")
        self.parse_blockdx_conf()
        org_data = copy.deepcopy(self.blockdx_conf_local)
        if not self.blockdx_conf_local:
            meta_data = self.container.conf_data.blockdx_base_conf
        else:
            meta_data = copy.deepcopy(self.blockdx_conf_local)

        # Update meta_data if changes are needed
        if 'user' not in meta_data or meta_data['user'] != rpc_user:
            meta_data['user'] = rpc_user
            logger.debug("Updated 'user' in meta_data")
        if 'password' not in meta_data or meta_data['password'] != rpc_password:
            meta_data['password'] = rpc_password
            logger.debug("Updated 'password' in meta_data")
        if 'xbridgeConfPath' not in meta_data or meta_data['xbridgeConfPath'] != xbridgeconfpath:
            meta_data['xbridgeConfPath'] = xbridgeconfpath
            logger.debug("Updated 'xbridgeConfPath' in meta_data")

        # Update 'selectedWallets' if needed
        if 'selectedWallets' not in meta_data:
            meta_data['selectedWallets'] = []
            meta_data['selectedWallets'].append(self.container.conf_data.blockdx_selectedWallets_blocknet)
            logger.info(
                f"Initialized 'selectedWallets' with '{self.container.conf_data.blockdx_selectedWallets_blocknet}' in meta_data")
        elif self.container.conf_data.blockdx_selectedWallets_blocknet not in meta_data['selectedWallets']:
            meta_data['selectedWallets'] = [self.container.conf_data.blockdx_selectedWallets_blocknet]
            logger.debug("Updated 'selectedWallets' in meta_data")

        # Save file if changes were made
        if org_data != meta_data:
            with open(file_path, 'w') as file:
                json.dump(meta_data, file, indent=4)
            logger.info("Updated Blockdx config with new data.")
            self.blockdx_conf_local = meta_data
            self.is_config_sync = False  # Config changed, so not in sync
        else:
            logger.info("No changes detected in Blockdx config.")
            self.is_config_sync = True  # No changes, so config is in sync

    def start_blockdx(self):
        if not self.executable_path or not os.path.exists(self.executable_path):
            logger.info(f"Blockdx executable not found at {self.executable_path}. Downloading...")
            self.download_blockdx_bin()
            if not self.executable_path or not os.path.exists(self.executable_path):
                logger.error("Failed to download Blockdx binary. Aborting start.")
                return  # Abort if download failed

        try:
            if self.container.system == "Darwin":
                self.handle_dmg("mount")
                bin_name = self.container.conf_data.blockdx_bin_name.get(self.container.system)
                if not (self.dmg_mount_path and bin_name):
                    raise ValueError("Required configuration not available for macOS")
                full_path = os.path.join(self.dmg_mount_path, bin_name)
                volume_name = self.container.blockdx_volume_name
                logger.info(
                    f"volume_name: {volume_name}, mount_path: {self.dmg_mount_path}, full_path: {full_path}")
                command = [full_path]
                cwd = os.path.dirname(full_path)
            else:
                if not self.executable_path:
                    raise ValueError("Executable path not configured")
                command = [self.executable_path]
                cwd = os.path.dirname(self.executable_path)

            self.blockdx_process = self.start_process(command, cwd=cwd)
            # also set generic process for BaseBinUtil compatibility
            self.process = self.blockdx_process
            logger.info(f"Started Blockdx process with PID {self.blockdx_process.pid}: {command}")
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            # re-raise so BinaryManager can show copy-pasteable report (issue #14)
            raise

    def close_blockdx(self):
        if self.blockdx_process:
            self.graceful_terminate(timeout=10)
        else:
            self.close_blockdx_pids()

    def close_blockdx_pids(self):
        self.terminate_processes(self.blockdx_pids, "BlockDX")

    def download_blockdx_bin(self):
        url = self.container.blockdx_release_url
        if url is None:
            raise ValueError(f"Unsupported OS or architecture {self.container.system} {self.container.machine}")

        aio_folder = self.container.aio_folder
        if not aio_folder:
            raise ValueError("AIO folder not configured")

        if not self.executable_path:
            raise ValueError("Executable path not configured")

        # Type assertion for mypy
        exe_path = self.executable_path  # type: ignore
        self.download_binary(
            url,
            os.path.basename(url),
            exe_path,
            aio_folder
        )

    def unmount_dmg(self):
        if self.container.system != "Darwin":
            logger.warning(f"Call unmount_dmg with wrong OS, {self.container.system} ?")
            return
        try:
            self.handle_dmg("unmount")
        except Exception as e:
            logger.warning(f"Error unmounting DMG: {e}")


def get_blockdx_data_folder():
    container = get_container()
    path = container.conf_data.blockdx_default_paths.get(container.system)
    if path:
        return os.path.expandvars(os.path.expanduser(path))
    else:
        raise ValueError("Unsupported system")
