import io
import platform
import tarfile
import zipfile
import asyncio
import psutil
import requests
import logging
import os
import subprocess
import time
import json
import copy

from conf_data import blockdx_releases_urls, aio_blocknet_data_path, blockdx_bin_path, blockdx_default_paths, \
    blockdx_selectedWallets_blocknet, blockdx_base_conf, blockdx_bin_name

logging.basicConfig(level=logging.DEBUG)


class BlockdxUtility:
    def __init__(self):
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

    def start_blockdx(self, retry_limit=3, retry_count=0):
        if retry_count >= retry_limit:
            logging.error("Retry limit exceeded. Unable to start Blockdx.")
            return

        # Get the current system
        system = platform.system()
        local_path = os.path.expandvars(os.path.expanduser(aio_blocknet_data_path.get(system)))

        # Construct the path to the Blockdx executable based on the current system
        if system == "Darwin":
            darwin_folders = blockdx_bin_path[system]
            blockdx_exe = os.path.join(local_path, *darwin_folders, blockdx_bin_name[system])
        else:
            # For Windows and Linux
            blockdx_exe = os.path.join(local_path, blockdx_bin_path[system], blockdx_bin_name[system])

        if not os.path.exists(blockdx_exe):
            self.downloading_bin = True
            logging.info(f"Blockdx executable not found at {blockdx_exe}. Downloading...")
            download_blockdx_bin()
            self.downloading_bin = False

        try:
            # Start the Blocknet process using subprocess
            self.blockdx_process = subprocess.Popen([blockdx_exe],
                                                    stdout=subprocess.PIPE,
                                                    stderr=subprocess.PIPE,
                                                    stdin=subprocess.PIPE,
                                                    start_new_session=True)
            # Check if the process has started
            while self.blockdx_process.pid is None:
                time.sleep(1)  # Wait for 1 second before checking again

            pid = self.blockdx_process.pid
            logging.info(f"Started Blockdx process with PID {pid}: {blockdx_exe}")
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


def get_blockdx_data_folder():
    system = platform.system()
    path = blockdx_default_paths.get(system)
    if path:
        return os.path.expandvars(os.path.expanduser(path))
    else:
        raise ValueError("Unsupported system")


def download_blockdx_bin():
    system = platform.system()
    machine = platform.machine()
    url = blockdx_releases_urls.get((system, machine))
    local_path = os.path.expandvars(os.path.expanduser(aio_blocknet_data_path.get(system)))
    if url is None:
        raise ValueError("Unsupported OS or architecture")

    response = requests.get(url)
    if response.status_code == 200:
        # Extract the archive from memory
        if url.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(response.content), "r") as zip_ref:
                local_path = os.path.join(local_path, blockdx_bin_path[system])
                zip_ref.extractall(local_path)
        elif url.endswith(".tar.gz"):
            with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tar:
                tar.extractall(local_path)
        else:
            print("Unsupported archive format.")
    else:
        print("Failed to download the Blockdx binary.")


async def main():
    blockdx_utility = BlockdxUtility()
    # blockdx_utility.compare_and_update_local_conf()


if __name__ == "__main__":
    asyncio.run(main())
