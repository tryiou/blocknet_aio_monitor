import json
import logging
import os
import subprocess
import threading
import time

import requests

from utilities import global_variables
from utilities.helper_util import UtilityHelper

logging.basicConfig(level=logging.DEBUG)

if global_variables.system == 'Windows':
    import winreg


    def check_vc_redist_installed():
        base_key_path = r"SOFTWARE\Classes\Installer\Dependencies\Microsoft.VS.VC_RuntimeMinimumVSU_amd64,v14"
        value_name = "DisplayName"

        display_name = check_registry_value(base_key_path, value_name)
        if display_name is not None:
            return True
        else:
            logging.info("No vc_redist found. Installing")
            install_vc_redist(global_variables.conf_data.vc_redist_win_url)


    def check_registry_value(key_path, value_name):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                return value
        except FileNotFoundError:
            return None
        except Exception as e:
            logging.error(f"Error: {e}")
            return None


    def install_vc_redist(url):
        try:
            installer_name = os.path.basename(url)

            with open(installer_name, 'wb') as file:
                response = requests.get(url)
                file.write(response.content)

            command = f"{installer_name} /install /quiet /norestart"

            subprocess.run(command, shell=True, check=True)
            logging.info("Visual C++ Redistributable installed successfully.")

            os.remove(installer_name)

        except Exception as e:
            logging.error(f"Error: {e}")


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
            response = requests.post(url, json=data, headers=headers, auth=auth)
            if response.status_code != 200:
                return None

            json_answer = response.json()
            if 'result' in json_answer:
                return json_answer['result']
            else:
                logging.error(f"No result in json: {json_answer}")
        except requests.RequestException as e:
            return None
        except Exception as ex:
            logging.exception(f"An unexpected error occurred while sending RPC request: {ex}")
            return None


class XliteUtility:
    def __init__(self):
        self.helper = UtilityHelper()
        if global_variables.system == "Darwin":
            self.xlite_exe = os.path.join(global_variables.aio_folder, os.path.basename(global_variables.xlite_url))
            self.dmg_mount_path = f"/Volumes/{global_variables.xlite_volume_name}"
        else:
            self.xlite_exe = os.path.join(global_variables.aio_folder,
                                          global_variables.conf_data.xlite_bin_path[global_variables.system],
                                          global_variables.conf_data.xlite_bin_name[global_variables.system])
        self.binary_percent_download = None
        self.valid_daemons_rpc_servers = None
        self.xlite_daemon_confs_local = {}
        self.coins_rpc = {}
        self.valid_coins_rpc = False
        self.process_running = None
        self.xlite_process = None
        self.xlite_daemon_process = None
        self.xlite_conf_local = {}
        self.running = True  # flag for async funcs
        self.xlite_pids = []
        self.xlite_daemon_pids = []
        self.parse_xlite_conf()
        self.parse_xlite_daemon_conf()
        self.downloading_bin = False
        self.start_threads()

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

    def check_valid_xlite_coins_rpc(self, runonce=False):
        while self.running:
            valid = False
            if self.coins_rpc:
                for coin, rpc_server in self.coins_rpc.items():
                    if coin != "master" and coin != "TBLOCK":
                        if self.xlite_daemon_confs_local[coin]['rpcEnabled'] is True:
                            res = rpc_server.send_rpc_request("getinfo")
                            if res is not None:
                                valid = True
                        if not valid:
                            break
            if valid:
                self.valid_coins_rpc = True
            else:
                self.valid_coins_rpc = False
            if runonce:
                return

            time.sleep(5)

    def start_threads(self):
        thread = threading.Thread(target=self.check_xlite_daemon_confs)
        thread.start()
        thread = threading.Thread(target=self.check_valid_xlite_coins_rpc)
        thread.start()

    def parse_xlite_conf(self):
        data_folder = os.path.expandvars(
            os.path.expanduser(global_variables.conf_data.xlite_default_paths.get(global_variables.system, None)))
        file = "app-settings.json"
        file_path = os.path.join(data_folder, file)
        meta_data = {}

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as file:
                    meta_data = json.load(file)
                    logging.info(f"XLITE: Loaded JSON data from [{file_path}]")
            except Exception as e:
                logging.error(f"Error parsing {file_path}: {e}, repairing file")
        self.xlite_conf_local = meta_data

    def parse_xlite_daemon_conf(self, silent=False):
        daemon_data_path = os.path.expandvars(
            os.path.expanduser(
                global_variables.conf_data.xlite_daemon_default_paths.get(global_variables.system, None)))
        confs_folder = os.path.join(daemon_data_path, "settings")

        if not os.path.exists(confs_folder):
            self.xlite_daemon_confs_local = {}
            return

        files_in_folder = os.listdir(confs_folder)

        json_files = [file for file in files_in_folder if file.endswith('.json')]

        for json_file in json_files:
            json_file_path = os.path.join(confs_folder, json_file)
            coin = str(json_file).split("-")[1].split(".")[0]
            try:
                with open(json_file_path, 'r') as file:
                    data = json.load(file)
                self.xlite_daemon_confs_local[coin] = data
            except Exception as e:
                self.xlite_daemon_confs_local[coin] = "ERROR PARSING"
                logging.error(f"Error parsing {json_file_path}: {e}")
        if not silent:
            logging.info(
                f"XLITE-DAEMON: Parsed coins confs from [{confs_folder}] {list(self.xlite_daemon_confs_local.keys())}")

    def start_xlite(self, env_vars=[]):
        if global_variables.system == "Windows":
            check_vc_redist_installed()

        for var_dict in env_vars:
            for var_name, var_value in var_dict.items():
                os.environ[var_name] = var_value

        if not os.path.exists(self.xlite_exe):
            logging.info(f"Xlite executable not found at {self.xlite_exe}. Downloading...")
            self.download_xlite_bin()

        try:
            if global_variables.system == "Darwin":
                self.helper.handle_dmg(self.xlite_exe, self.dmg_mount_path, "mount")
                full_path = os.path.join(self.dmg_mount_path,
                                         *global_variables.conf_data.xlite_bin_name[global_variables.system])
                logging.info(
                    f"volume_name: {global_variables.xlite_volume_name}, mount_path: {self.dmg_mount_path}, full_path: {full_path}")
                self.xlite_process = subprocess.Popen([full_path],
                                                      stdout=subprocess.PIPE,
                                                      stderr=subprocess.PIPE,
                                                      stdin=subprocess.PIPE,
                                                      start_new_session=True)
            else:
                self.xlite_process = subprocess.Popen([self.xlite_exe],
                                                      stdout=subprocess.PIPE,
                                                      stderr=subprocess.PIPE,
                                                      stdin=subprocess.PIPE,
                                                      start_new_session=True)
            while self.xlite_process.pid is None:
                time.sleep(1)

            pid = self.xlite_process.pid
            logging.info(f"Started Xlite process with PID {pid}: {self.xlite_exe}")
        except Exception as e:
            logging.error(f"Error: {e}")

    def close_xlite(self):
        if self.xlite_process:
            try:
                self.xlite_process.terminate()
                self.xlite_process.wait(timeout=10)
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
        if self.xlite_process:
            try:
                self.xlite_process.kill()
                logging.info(f"Killed Xlite")
                self.xlite_process = None
                return
            except Exception as e:
                logging.error(f"Error: {e}")

    def close_xlite_pids(self):
        self.helper.terminate_processes(self.xlite_pids, "XLite")

    def close_xlite_daemon_pids(self):
        self.helper.terminate_processes(self.xlite_daemon_pids, "Xlite-daemon")

    def download_xlite_bin(self):
        self.downloading_bin = True
        url = global_variables.conf_data.xlite_releases_urls.get((global_variables.system, global_variables.machine))
        if url is None:
            raise ValueError(f"Unsupported OS or architecture {global_variables.system} {global_variables.machine}")

        tmp_path = os.path.join(global_variables.aio_folder, "tmp_xl_bin")
        final_path = self.xlite_exe  # For DMG
        extract_to = global_variables.aio_folder  # For zip/tar.gz

        self.helper.download_file(
            url, tmp_path, final_path, extract_to,
            global_variables.system, "binary_percent_download", self
        )
        self.downloading_bin = False

    def unmount_dmg(self):
        self.helper.handle_dmg(None, self.dmg_mount_path, "unmount")
