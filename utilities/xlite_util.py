import asyncio
import json
import logging
import os
import subprocess
import tarfile
import threading
import time
import zipfile

import psutil
import requests

from config.conf_data import (xlite_bin_path, xlite_default_paths, xlite_daemon_default_paths, vc_redist_win_url)
from utilities import global_variables

logging.basicConfig(level=logging.DEBUG)

if global_variables.system == 'Windows':
    import winreg


    def check_vc_redist_installed():
        # Define the base key path
        base_key_path = r"SOFTWARE\Classes\Installer\Dependencies\Microsoft.VS.VC_RuntimeMinimumVSU_amd64,v14"
        value_name = "DisplayName"

        display_name = check_registry_value(base_key_path, value_name)
        if display_name is not None:
            return True
        else:
            logging.info("No vc_redist found. installing")
            install_vc_redist(vc_redist_win_url)


    def check_registry_value(key_path, value_name):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                return value
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"Error: {e}")
            return None


    def install_vc_redist(url):
        try:
            # Parse filename from URL
            installer_name = os.path.basename(url)

            # Download the installer
            with open(installer_name, 'wb') as file:
                response = requests.get(url)
                file.write(response.content)

            # Command to run the installer silently
            command = f"{installer_name} /install /quiet /norestart"

            # Run the installer silently
            subprocess.run(command, shell=True, check=True)
            print("Visual C++ Redistributable installed successfully.")

            # Remove the installer file after installation
            os.remove(installer_name)

        except Exception as e:
            print(f"Error: {e}")


class XliteRPCClient:
    def __init__(self, rpc_user, rpc_password, rpc_port):
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
        if global_variables.system == "Darwin":
            self.xlite_exe = os.path.join(global_variables.aio_folder, os.path.basename(global_variables.xlite_url))
            self.dmg_mount_path = f"/Volumes/{global_variables.xlite_volume_name}"
        else:
            self.xlite_exe = os.path.join(global_variables.aio_folder, xlite_bin_path[global_variables.system],
                                          global_variables.xlite_bin_name[global_variables.system])
        self.binary_percent_download = None
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
        self.start_threads()

    def check_xlite_conf(self):
        while self.running and not (self.xlite_conf_local and 'APP_VERSION' in self.xlite_conf_local):
            self.parse_xlite_conf()
            time.sleep(10)

    def check_xlite_daemon_confs_sequence(self, silent=True):
        self.parse_xlite_daemon_conf(silent)
        if self.xlite_daemon_confs_local:
            for coin in self.xlite_daemon_confs_local:
                port = self.xlite_daemon_confs_local[coin]['rpcPort']
                user = self.xlite_daemon_confs_local[coin]['rpcUsername']
                password = self.xlite_daemon_confs_local[coin]['rpcPassword']
                self.coins_rpc[coin] = XliteRPCClient(rpc_user=user, rpc_password=password, rpc_port=port)

    def check_xlite_daemon_confs(self):
        while self.running and not self.valid_coins_rpc:
            self.check_xlite_daemon_confs_sequence(silent=True)
            time.sleep(10)

    def check_valid_coins_rpc(self, runonce=False):
        while self.running:
            # logging.debug(f"valid_coins_rpc: {self.valid_coins_rpc}, runonce: {runonce}")
            valid = False
            if self.coins_rpc:
                for coin, rpc_server in self.coins_rpc.items():
                    if coin != "master" and coin != "TBLOCK":
                        # logging.info(self.xlite_daemon_confs_local[coin]['rpcEnabled'])
                        if self.xlite_daemon_confs_local[coin]['rpcEnabled'] is True:
                            res = rpc_server.send_rpc_request("getinfo")
                            if res is not None:
                                valid = True
                        if not valid:
                            # logging.debug(f"coin {coin} not valid")
                            break
            if valid:
                self.valid_coins_rpc = True
            else:
                self.valid_coins_rpc = False
            if runonce:
                return

            time.sleep(5)

    def start_threads(self):
        thread = threading.Thread(target=self.check_xlite_conf)
        thread.start()
        thread = threading.Thread(target=self.check_xlite_daemon_confs)
        thread.start()
        thread = threading.Thread(target=self.check_valid_coins_rpc)
        thread.start()

    def parse_xlite_conf(self):
        data_folder = os.path.expandvars(os.path.expanduser(xlite_default_paths.get(global_variables.system, None)))
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
        daemon_data_path = os.path.expandvars(
            os.path.expanduser(xlite_daemon_default_paths.get(global_variables.system, None)))
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

    def start_xlite(self, env_vars=[]):
        if global_variables.system == "Windows":
            # check vcredist
            # install_vc_redist(vc_redist_win_url)
            check_vc_redist_installed()

        for var_dict in env_vars:
            for var_name, var_value in var_dict.items():
                # logging.info(f"var_name: {var_name} var_value: {var_value}")
                os.environ[var_name] = var_value

        if not os.path.exists(self.xlite_exe):
            logging.info(f"Xlite executable not found at {self.xlite_exe}. Downloading...")
            self.download_xlite_bin()

        try:
            if global_variables.system == "Darwin":
                # mac mod
                # https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.dmg
                # Path to the application inside the DMG file

                # Check if the volume is already mounted
                if not os.path.ismount(self.dmg_mount_path):
                    # Mount the DMG file
                    os.system(f'hdiutil attach "{self.xlite_exe}"')
                else:
                    logging.info("Volume is already mounted.")
                full_path = os.path.join(self.dmg_mount_path, *global_variables.xlite_bin_name[global_variables.system])
                logging.info(
                    f"volume_name: {global_variables.xlite_volume_name}, mount_path: {self.dmg_mount_path}, full_path: {full_path}")
                self.xlite_process = subprocess.Popen([full_path],
                                                      stdout=subprocess.PIPE,
                                                      stderr=subprocess.PIPE,
                                                      stdin=subprocess.PIPE,
                                                      start_new_session=True)
            else:
                # Start the Blocknet process using subprocess
                self.xlite_process = subprocess.Popen([self.xlite_exe],
                                                      stdout=subprocess.PIPE,
                                                      stderr=subprocess.PIPE,
                                                      stdin=subprocess.PIPE,
                                                      start_new_session=True)
            # Check if the process has started
            while self.xlite_process.pid is None:
                time.sleep(1)  # Wait for 1 second before checking again

            pid = self.xlite_process.pid
            logging.info(f"Started Xlite process with PID {pid}: {self.xlite_exe}")
        except Exception as e:
            logging.error(f"Error: {e}")

    def close_xlite(self):
        # Close the Xlite subprocess if it exists
        if self.xlite_process:
            try:
                self.xlite_process.terminate()
                self.xlite_process.wait(timeout=10)  # Wait for the process to terminate with a timeout of 60 seconds
                logging.info(f"Closed Xlite")
                self.xlite_process = None
            except subprocess.TimeoutExpired:
                logging.info(f"Force terminating Xlite")
                self.kill_xlite()
                logging.info(f"Xlite has been force terminated.")
                self.xlite_process = None
            except Exception as e:
                logging.error(f"Error: {e}")
        else:
            self.close_xlite_pids()
        self.close_xlite_daemon_pids()

    def kill_xlite(self):
        # Kill the Xlite subprocess if it exists
        if self.xlite_process:
            try:
                self.xlite_process.kill()
                logging.info(f"Killed Xlite")
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
                proc.wait(timeout=10)  # Wait for the process to terminate with a timeout of 60 seconds
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

    def close_xlite_daemon_pids(self):

        # Close the Xlite-daemon processes using their PIDs
        for pid in self.xlite_daemon_pids:
            try:
                # Get the process object corresponding to the PID
                proc = psutil.Process(pid)
                proc.terminate()
                logging.info(f"Initiated termination of Xlite-daemon process with PID {pid}.")
                proc.wait(timeout=10)  # Wait for the process to terminate with a timeout of 60 seconds
                logging.info(f"Xlite-daemon process with PID {pid} has been terminated.")
            except psutil.NoSuchProcess:
                logging.warning(f"Xlite-daemon process with PID {pid} not found.")
            except psutil.TimeoutExpired:
                logging.warning(f"Force terminating Xlite-daemon process with PID {pid}.")
                if proc:
                    proc.kill()
                    proc.wait()
                    logging.info(f"Xlite-daemon process with PID {pid} has been force terminated.")
            except Exception as e:
                logging.error(f"Error: {e}")
        logging.info(f"Closed Xlite daemon")

    def download_xlite_bin(self):
        self.downloading_bin = True
        url = global_variables.xlite_releases_urls.get((global_variables.system, global_variables.machine))
        if url is None:
            raise ValueError(f"Unsupported OS or architecture {global_variables.system} {global_variables.machine}")

        # Set timeout values in seconds
        connection_timeout = 5
        read_timeout = 30
        response = requests.get(url, stream=True, timeout=(connection_timeout, read_timeout))
        response.raise_for_status()  # Raise an exception for 4xx and 5xx status codes
        if response.status_code == 200:
            file_name = os.path.basename(url)
            tmp_file_path = os.path.join(global_variables.aio_folder, "tmp_xl_bin")
            try:
                remote_file_size = int(response.headers.get('Content-Length', 0))
                # tmp_file_path = os.path.join(aio_folder, file_name + "_tmp")
                logging.info(f"Downloading {url} to {tmp_file_path}, remote size: {int(remote_file_size / 1024)} kb")
                bytes_downloaded = 0
                with open(tmp_file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):  # Iterate over response content in chunks
                        if chunk:  # Filter out keep-alive new chunks
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
                            self.binary_percent_download = (bytes_downloaded / remote_file_size) * 100
                            # print(self.binary_percent_download)
            except requests.exceptions.RequestException as e:
                logging.error(f"Error occurred during download: {str(e)}")

            self.binary_percent_download = None

            local_file_size = os.path.getsize(tmp_file_path)
            if local_file_size != remote_file_size:
                os.remove(tmp_file_path)
                raise ValueError(
                    f"Downloaded {os.path.basename(url)} size doesn't match the expected size. Deleting it")

            logging.info(f"{os.path.basename(url)} downloaded successfully.")

            # Extract the archive
            if url.endswith(".zip"):
                with zipfile.ZipFile(tmp_file_path, "r") as zip_ref:
                    local_path = os.path.join(global_variables.aio_folder, xlite_bin_path[global_variables.system])
                    zip_ref.extractall(local_path)
                logging.info("Zip file extracted successfully.")
                os.remove(tmp_file_path)
            elif url.endswith(".tar.gz"):
                with tarfile.open(tmp_file_path, "r:gz") as tar:
                    tar.extractall(global_variables.aio_folder)
                logging.info("Tar.gz file extracted successfully.")
                os.remove(tmp_file_path)
            elif url.endswith(".dmg"):
                file_path = os.path.join(global_variables.aio_folder, file_name)
                os.rename(tmp_file_path, file_path)
                logging.info("DMG file saved successfully.")
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

# if __name__ == "__main__":
# install_vc_redist(vc_redist_win_url)
