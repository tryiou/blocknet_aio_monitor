import asyncio
import io
import platform
import tarfile
import threading
import zipfile
import psutil
import requests
import logging
import os
import subprocess
import time
import json
from contextlib import contextmanager
from conf_data import (xlite_releases_urls, xlite_bin_path, xlite_bin_name, aio_blocknet_data_path,
                       xlite_default_paths, xlite_daemon_default_paths)

logging.basicConfig(level=logging.DEBUG)

system = platform.system()
machine = platform.machine()

url = xlite_releases_urls.get((system, machine))
if system == "Darwin":
    volume_name = ' '.join(os.path.splitext(os.path.basename(url))[0].split('-')[:-1])


class XliteRPCClient:
    def __init__(self, rpc_user, rpc_password, rpc_port):
        if system == "Darwin":
            self.dmg_mount_path = f"/Volumes/{volume_name}"
        self.rpc_user = rpc_user
        self.rpc_password = rpc_password
        self.rpc_port = rpc_port

    def send_rpc_request(self, method=None, params=None):
        url = f"http://localhost:{self.rpc_port}"
        headers = {'content-type': 'application/json'}
        auth = (self.rpc_user, self.rpc_password)
        data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params if params is not None else [],
            "id": 1,
        }
        try:
            # logging.debug(
            # f"Sending RPC request to URL: {url}, Method: {data['method']}, Params: {data['params']}, Auth: {auth}")
            response = requests.post(url, json=data, headers=headers, auth=auth)
            # Check status code explicitly
            if response.status_code != 200:
                # logging.error(f"Error sending RPC request: HTTP status code {response.status_code}")
                return None

            json_answer = response.json()
            # logging.debug(f"RPC request successful. Response: {json}")
            if 'result' in json_answer:
                return json_answer['result']
            else:
                logging.error(f"No result in json: {json_answer}")
        except requests.RequestException as e:
            # logging.error(f"Error sending RPC request: {e}")
            return None
        except Exception as ex:
            logging.exception(f"An unexpected error occurred while sending RPC request: {ex}")
            return None


class XliteUtility:
    def __init__(self):
        self.dmg_mount_path = None
        self.valid_daemons_rpc_servers = None
        self.xlite_daemon_confs_local = {}
        self.coins_rpc = {}
        self.valid_coins_rpc = False
        self.process_running = None
        self.xlite_process = None
        self.xlite_daemon_process = None
        self.xlite_conf_local = {}
        self.xlite_daemon_confs_local = {}
        self.running = True  # flag for async funcs
        self.xlite_pids = []
        self.xlite_daemon_pids = []
        self.parse_xlite_conf()
        self.parse_xlite_daemon_conf()
        self.downloading_bin = False
        self.start_async_tasks()

    async def check_xlite_conf(self):
        while self.running and not (self.xlite_conf_local and 'APP_VERSION' in self.xlite_conf_local):
            self.parse_xlite_conf()
            # logging.debug("check_xlite_conf")
            await asyncio.sleep(1)

    def check_xlite_daemon_confs_sequence(self, silent=True):
        self.parse_xlite_daemon_conf(silent)
        if self.xlite_daemon_confs_local:
            for coin in self.xlite_daemon_confs_local:
                port = self.xlite_daemon_confs_local[coin]['rpcPort']
                user = self.xlite_daemon_confs_local[coin]['rpcUsername']
                password = self.xlite_daemon_confs_local[coin]['rpcPassword']
                self.coins_rpc[coin] = XliteRPCClient(rpc_user=user, rpc_password=password, rpc_port=port)

    async def check_xlite_daemon_confs(self):
        while self.running and not self.valid_coins_rpc:
            await asyncio.sleep(3)
            self.check_xlite_daemon_confs_sequence(silent=True)
            await self.check_valid_coins_rpc(runonce=True)

    async def check_valid_coins_rpc(self, runonce=False):
        while self.running:
            if self.coins_rpc:
                for coin, rpc_server in self.coins_rpc.items():
                    valid = False
                    if coin != "master" and coin != "TBLOCK":
                        # logging.info(self.xlite_daemon_confs_local[coin]['rpcEnabled'])
                        if self.xlite_daemon_confs_local[coin]['rpcEnabled'] is True:
                            res = rpc_server.send_rpc_request("getinfo")
                            # logging.info(f"coin {coin} result:{res}")
                            if res is not None:
                                valid = True
                        if not valid:
                            break
                if valid:
                    self.valid_coins_rpc = True
                else:
                    self.valid_coins_rpc = False
            else:
                self.valid_coins_rpc = False
            if runonce:
                return
            # logging.info(f"valid_master_rpc: {self.valid_master_rpc}")
            await asyncio.sleep(5)

    def start_async_tasks(self):
        def xlite_async_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                asyncio.gather(
                    self.check_xlite_conf(),
                    self.check_xlite_daemon_confs(),
                    self.check_valid_coins_rpc()
                )  # self.check_blocknet_process(),
            )
            loop.close()

        thread = threading.Thread(target=xlite_async_loop)
        thread.start()

    def parse_xlite_conf(self):
        data_folder = os.path.expandvars(os.path.expanduser(xlite_default_paths.get(system, None)))
        file = "app-settings.json"
        file_path = os.path.join(data_folder, file)
        meta_data = {}

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as file:
                    meta_data = json.load(file)
                    logging.info(f"XLITE: Loaded JSON data from {file_path}: {meta_data}")
            except Exception as e:
                logging.error(f"Error parsing {file_path}: {e}, repairing file")
        else:
            # logging.warning(f"{file_path} doesn't exist")
            pass
        self.xlite_conf_local = meta_data

    def parse_xlite_daemon_conf(self, silent=False):
        # Assuming daemon_data_path and confs_folder are defined earlier in your code
        daemon_data_path = os.path.expandvars(os.path.expanduser(xlite_daemon_default_paths.get(system, None)))
        confs_folder = os.path.join(daemon_data_path, "settings")

        # List all files in the confs_folder
        if not os.path.exists(confs_folder):
            # logging.warning(f"{confs_folder} doesn't exist")
            self.xlite_daemon_confs_local = {}
            return

        files_in_folder = os.listdir(confs_folder)

        # Filter out only JSON files
        json_files = [file for file in files_in_folder if file.endswith('.json')]

        # Parse each JSON file
        for json_file in json_files:
            json_file_path = os.path.join(confs_folder, json_file)
            coin = str(json_file).split("-")[1].split(".")[0]
            try:
                with open(json_file_path, 'r') as file:
                    data = json.load(file)
                    # Do something with the parsed JSON data
                # logging.debug(f"Parsed data from {coin} {json_file}: {data}")
                self.xlite_daemon_confs_local[coin] = data
            except Exception as e:
                self.xlite_daemon_confs_local[coin] = "ERROR PARSING"
                logging.error(f"Error parsing {json_file_path}: {e}")
        if not silent:
            logging.info(f"XLITE-DAEMON: Parsed every coins conf {self.xlite_daemon_confs_local}")

    def start_xlite(self, retry_limit=3, retry_count=0, env_vars=[]):
        for var_dict in env_vars:
            for var_name, var_value in var_dict.items():
                # logging.info(f"var_name: {var_name} var_value: {var_value}")
                os.environ[var_name] = var_value

        if retry_count >= retry_limit:
            logging.error("Retry limit exceeded. Unable to start Xlite.")
            return

        local_path = os.path.expandvars(os.path.expanduser(aio_blocknet_data_path.get(system)))

        if system == "Darwin":
            xlite_dmg_name = os.path.basename(url)
            xlite_exe = os.path.join(local_path, xlite_dmg_name)
        else:
            xlite_exe = os.path.join(local_path, xlite_bin_path[system], xlite_bin_name[system])

        if not os.path.exists(xlite_exe):
            logging.info(f"Xlite executable not found at {xlite_exe}. Downloading...")
            self.download_xlite_bin()

        try:
            if system == "Darwin":
                # mac mod
                # https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.dmg
                # Path to the application inside the DMG file

                # Check if the volume is already mounted
                if not os.path.ismount(self.dmg_mount_path):
                    # Mount the DMG file
                    os.system(f'hdiutil attach "{xlite_exe}"')
                else:
                    logging.info("Volume is already mounted.")
                full_path = os.path.join(self.dmg_mount_path, *xlite_bin_name[system])
                logging.info(
                    f"volume_name: {volume_name}, mount_path: {self.dmg_mount_path}, full_path: {full_path}")
                self.xlite_process = subprocess.Popen([full_path],
                                                      stdout=subprocess.PIPE,
                                                      stderr=subprocess.PIPE,
                                                      stdin=subprocess.PIPE,
                                                      start_new_session=True)
            else:
                # Start the Blocknet process using subprocess
                self.xlite_process = subprocess.Popen([xlite_exe],
                                                      stdout=subprocess.PIPE,
                                                      stderr=subprocess.PIPE,
                                                      stdin=subprocess.PIPE,
                                                      start_new_session=True)
            # Check if the process has started
            while self.xlite_process.pid is None:
                time.sleep(1)  # Wait for 1 second before checking again

            pid = self.xlite_process.pid
            logging.info(f"Started Xlite process with PID {pid}: {xlite_exe}")
        except Exception as e:
            logging.error(f"Error: {e}")

    def close_xlite(self):
        # Close the Xlite subprocess if it exists
        if self.xlite_process:
            try:
                self.xlite_process.terminate()
                # logging.info(f"Terminating Xlite subprocess.")
                self.xlite_process.wait(timeout=60)  # Wait for the process to terminate with a timeout of 60 seconds
                logging.info(f"Closed Xlite subprocess.")
                self.xlite_process = None
                return
            except subprocess.TimeoutExpired:
                logging.info(f"Force terminating Xlite subprocess.")
                self.kill_xlite()
                logging.info(f"Xlite subprocess has been force terminated.")
                self.xlite_process = None
                return
            except Exception as e:
                logging.error(f"Error: {e}")
        else:
            self.close_xlite_pids()

    def kill_xlite(self):
        # Kill the Xlite subprocess if it exists
        if self.xlite_process:
            try:
                self.xlite_process.kill()
                logging.info(f"Killed Xlite subprocess.")
                self.xlite_process = None
                return
            except Exception as e:
                logging.error(f"Error: {e}")

    def close_xlite_pids(self):
        # Close the Xlite processes using their PIDs
        for pid in self.xlite_pids:
            try:
                # Get the process object corresponding to the PID
                proc = psutil.Process(pid)
                proc.terminate()
                logging.info(f"Initiated termination of Xlite process with PID {pid}.")
                proc.wait(timeout=60)  # Wait for the process to terminate with a timeout of 60 seconds
                logging.info(f"Xlite process with PID {pid} has been terminated.")
            except psutil.NoSuchProcess:
                logging.warning(f"Xlite process with PID {pid} not found.")
            except psutil.TimeoutExpired:
                logging.warning(f"Force terminating Xlite process with PID {pid}.")
                if proc:
                    proc.kill()
                    proc.wait()
                    logging.info(f"Xlite process with PID {pid} has been force terminated.")
            except Exception as e:
                logging.error(f"Error: {e}")

    def download_xlite_bin(self):
        self.downloading_bin = True
        url = xlite_releases_urls.get((system, machine))
        local_path = os.path.expandvars(os.path.expanduser(aio_blocknet_data_path.get(system)))
        if url is None:
            raise ValueError(f"Unsupported OS or architecture {system} {machine}")

        response = requests.get(url)
        if response.status_code == 200:
            # Extract the archive from memory
            if url.endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(response.content), "r") as zip_ref:
                    local_path = os.path.join(local_path, xlite_bin_path[system])
                    zip_ref.extractall(local_path)
            elif url.endswith(".tar.gz"):
                with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tar:
                    tar.extractall(local_path)
            elif url.endswith(".dmg"):
                local_file_path = os.path.join(local_path, os.path.basename(url))
                with open(local_file_path, "wb") as f:
                    f.write(response.content)
                print("DMG file saved successfully.")
            else:
                print("Unsupported archive format.")
        else:
            print("Failed to download the Xlite binary.")
        self.downloading_bin = False

    def unmount_dmg(self):
        if os.path.ismount(self.dmg_mount_path):
            try:
                subprocess.run(["hdiutil", "detach", self.dmg_mount_path], check=True)
                logging.info("DMG unmounted successfully.")
            except subprocess.CalledProcessError as e:
                logging.error(f"Error: Failed to unmount DMG: {e}")
        else:
            logging.error("Error: DMG is not mounted.")
