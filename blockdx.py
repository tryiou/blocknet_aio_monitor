import copy
import json
import logging
import subprocess
import tarfile
import time
import zipfile

import psutil
import requests

from conf_data import (blockdx_bin_path, blockdx_default_paths, blockdx_selectedWallets_blocknet, blockdx_base_conf)
from global_variables import *

logging.basicConfig(level=logging.DEBUG)


class BlockdxUtility:
    def __init__(self):
        if system == "Darwin":
            self.dmg_mount_path = f"/Volumes/{blockdx_volume_name}"
            self.blockdx_exe = os.path.join(aio_folder, os.path.basename(blockdx_url))
        else:
            self.blockdx_exe = os.path.join(aio_folder, blockdx_bin_path[system], blockdx_bin_name[system])
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
                    logging.info(f"BLOCK-DX: Loaded JSON data from {file_path}: {meta_data}")
            except Exception as e:
                logging.error(f"Error parsing {file_path}: {e}, repairing file")
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
            meta_data = blockdx_base_conf
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
            meta_data['selectedWallets'].append(blockdx_selectedWallets_blocknet)
            logging.debug(f"Initialized 'selectedWallets' with '{blockdx_selectedWallets_blocknet}' in meta_data")
        elif not isinstance(meta_data['selectedWallets'], list):
            logging.warning("'selectedWallets' is not a list. Converting to list.")
            meta_data['selectedWallets'] = [blockdx_selectedWallets_blocknet]
        elif blockdx_selectedWallets_blocknet not in meta_data['selectedWallets']:
            meta_data['selectedWallets'].append(blockdx_selectedWallets_blocknet)
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
        if os.path.ismount(self.dmg_mount_path):
            try:
                subprocess.run(["hdiutil", "detach", self.dmg_mount_path], check=True)
                logging.info("DMG unmounted successfully.")
            except subprocess.CalledProcessError as e:
                logging.error(f"Error: Failed to unmount DMG: {e}")
        else:
            logging.error("Error: DMG is not mounted.")

    def start_blockdx(self):
        if not os.path.exists(self.blockdx_exe):
            # self.downloading_bin = True
            logging.info(f"Blockdx executable not found at {self.blockdx_exe}. Downloading...")
            self.download_blockdx_bin()
            # self.downloading_bin = False

        try:
            # Start the BLOCK-DX process using subprocess
            if system == "Darwin":
                # mac mod

                # Check if the volume is already mounted
                if not os.path.ismount(self.dmg_mount_path):
                    # Mount the DMG file
                    os.system(f'hdiutil attach "{self.blockdx_exe}"')
                else:
                    logging.info("Volume is already mounted.")
                full_path = os.path.join(self.dmg_mount_path, *blockdx_bin_name[system])
                logging.info(
                    f"volume_name: {blockdx_volume_name}, mount_path: {self.dmg_mount_path}, full_path: {full_path}")
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
        # Close the blockdx processes using their PIDs
        for pid in self.blockdx_pids:
            try:
                # Get the process object corresponding to the PID
                proc = psutil.Process(pid)
                proc.terminate()
                logging.info(f"Initiated termination of blockdx process with PID {pid}.")
                proc.wait(timeout=60)  # Wait for the process to terminate with a timeout of 60 seconds
                logging.info(f"blockdx process with PID {pid} has been terminated.")
            except psutil.NoSuchProcess:
                logging.warning(f"blockdx process with PID {pid} not found.")
            except psutil.TimeoutExpired:
                logging.warning(f"Force terminating blockdx process with PID {pid}.")
                if proc:
                    proc.kill()
                    proc.wait()
                    logging.info(f"blockdx process with PID {pid} has been force terminated.")
            except Exception as e:
                logging.error(f"Error: {e}")

    def download_blockdx_bin(self):
        self.downloading_bin = True
        url = blockdx_releases_urls.get((system, machine))

        if url is None:
            raise ValueError(f"Unsupported OS or architecture {system} {machine}")

        # Set timeout values in seconds
        connection_timeout = 10
        read_timeout = 30
        response = requests.get(url, stream=True, timeout=(connection_timeout, read_timeout))
        response.raise_for_status()  # Raise an exception for 4xx and 5xx status codes
        if response.status_code == 200:
            file_name = os.path.basename(url)
            tmp_file_path = os.path.join(aio_folder, "tmp_dx_bin")
            try:
                remote_file_size = int(response.headers.get('Content-Length', 0))
                logging.info(f"Downloading {url} to {tmp_file_path}, remote size: {int(remote_file_size / 1024)} kb")
                bytes_downloaded = 0
                total = remote_file_size
                with open(tmp_file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):  # Iterate over response content in chunks
                        if chunk:  # Filter out keep-alive new chunks
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
                            self.binary_percent_download = (bytes_downloaded / total) * 100
            except requests.exceptions.RequestException as e:
                logging.error(f"Error occurred during download: {str(e)}")

            self.binary_percent_download = None

            if os.path.getsize(tmp_file_path) != remote_file_size:
                os.remove(tmp_file_path)
                raise ValueError(
                    f"Downloaded {os.path.basename(url)} size doesn't match the expected size. Deleting it")

            logging.info(f"{os.path.basename(url)} downloaded successfully.")

            # Extract the archive
            if url.endswith(".zip"):
                with zipfile.ZipFile(tmp_file_path, "r") as zip_ref:
                    local_path = os.path.join(aio_folder, blockdx_bin_path[system])
                    zip_ref.extractall(local_path)
                logging.info("Zip file extracted successfully.")
                os.remove(tmp_file_path)
            elif url.endswith(".tar.gz"):
                with tarfile.open(tmp_file_path, "r:gz") as tar:
                    tar.extractall(aio_folder)
                logging.info("Tar.gz file extracted successfully.")
                os.remove(tmp_file_path)
            elif url.endswith(".dmg"):
                file_path = os.path.join(aio_folder, file_name)
                os.rename(tmp_file_path, file_path)
                logging.info("DMG file saved successfully.")
        else:
            logging.error("Failed to download the Blockdx binary.")
        self.downloading_bin = False


def get_blockdx_data_folder():
    path = blockdx_default_paths.get(system)
    if path:
        return os.path.expandvars(os.path.expanduser(path))
    else:
        raise ValueError("Unsupported system")

# async def main():
#     blockdx_utility = BlockdxUtility()
#     # blockdx_utility.compare_and_update_local_conf()
#
#
# if __name__ == "__main__":
#     asyncio.run(main())
