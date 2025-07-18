import json
import logging
import os
import subprocess
import threading
import time
import traceback

import requests

from utilities import global_variables
from utilities.bin_handlers.base_binutil import BaseBinUtil

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





class XliteHandler(BaseBinUtil):
    def __init__(self):
        super().__init__("Xlite")
        if global_variables.system == "Darwin":
            self.executable_path = os.path.join(global_variables.aio_folder, os.path.basename(global_variables.xlite_url))
            self.dmg_mount_path = f"/Volumes/{global_variables.xlite_volume_name}"
        else:
            self.executable_path = os.path.join(global_variables.aio_folder,
                                                global_variables.conf_data.xlite_bin_path[global_variables.system],
                                                global_variables.conf_data.xlite_bin_name[global_variables.system])
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

        if not os.path.exists(self.executable_path):
            logging.info(f"Xlite executable not found at {self.executable_path}. Downloading...")
            self.download_xlite_bin()

        # Get launch options for current OS
        launch_options = global_variables.conf_data.xlite_launch_options.get(global_variables.system, None)

        try:
            if global_variables.system == "Darwin":
                self.handle_dmg( "mount")
                full_path = os.path.join(self.dmg_mount_path,
                                         *global_variables.conf_data.xlite_bin_name[global_variables.system])
                logging.info(
                    f"volume_name: {global_variables.xlite_volume_name}, mount_path: {self.dmg_mount_path}, full_path: {full_path}")
                command = [full_path] + launch_options 
                cwd = os.path.dirname(full_path)
            else:
                command = [self.executable_path] + launch_options
                cwd = os.path.dirname(self.executable_path)

            parsed_env_vars = {}
            for env_var_str in env_vars:
                if '=' in env_var_str:
                    key, value = env_var_str.split('=', 1)
                    parsed_env_vars[key] = value
                else:
                    logging.warning(f"Environment variable string '{env_var_str}' does not contain '='. Skipping.")
            self.xlite_process = self.start_process(command, cwd=cwd, env_vars=parsed_env_vars)
            logging.info(f"Started Xlite process with PID {self.xlite_process.pid}: {command}")
        except Exception as e:
            logging.error(f"Error starting Xlite process: {e}\n{traceback.format_exc()}")
            # logging.error(f"Error AA: {e}")

    def close_xlite(self):
        if self.xlite_process:
            self.graceful_terminate(timeout=10)
        else:
            self.close_xlite_pids()
        self.close_xlite_daemon_pids()

    def close_xlite_pids(self):
        self.terminate_processes(self.xlite_pids, "XLite")

    def close_xlite_daemon_pids(self):
        self.terminate_processes(self.xlite_daemon_pids, "Xlite-daemon")

    def download_xlite_bin(self):
        url = global_variables.conf_data.xlite_releases_urls.get((global_variables.system, global_variables.machine))
        if url is None:
            raise ValueError(f"Unsupported OS or architecture {global_variables.system} {global_variables.machine}")

        tmp_filename = "tmp_xl_bin"
        self.download_binary(
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
