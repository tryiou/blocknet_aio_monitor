import json
import logging
import os
import subprocess
import threading
import time
import traceback

import requests

from utilities.app_container import AppContainer
from utilities.bin_handlers.base_binutil import BaseBinUtil
from utilities.rpc_client import RPCClient

logger = logging.getLogger(__name__)


def check_vc_redist_installed(container: AppContainer):
    base_key_path = r"SOFTWARE\Classes\Installer\Dependencies\Microsoft.VS.VC_RuntimeMinimumVSU_amd64,v14"
    value_name = "DisplayName"

    display_name = check_registry_value(base_key_path, value_name)
    if display_name is not None:
        return True
    else:
        logger.info("No vc_redist found. Installing")
        install_vc_redist(container.conf_data.vc_redist_win_url)


def check_registry_value(key_path, value_name):
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
            return value
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.error(f"Error: {e}")
        return None


def install_vc_redist(url):
    try:
        installer_name = os.path.basename(url)

        with open(installer_name, "wb") as file:
            response = requests.get(url, timeout=10)
            file.write(response.content)

        command = f"{installer_name} /install /quiet /norestart"

        subprocess.run(command, shell=True, check=True)  # noqa: S602 # shell required for Windows installer
        logger.info("Visual C++ Redistributable installed successfully.")

        os.remove(installer_name)

    except Exception as e:
        logger.error(f"Error: {e}")


class XliteHandler(BaseBinUtil):
    def __init__(self, container: AppContainer | None = None):
        super().__init__("Xlite", container)
        if self.container.system == "Darwin":
            xlite_release_url = self.container.xlite_release_url
            if xlite_release_url and self.container.aio_folder:
                self.executable_path = os.path.join(self.container.aio_folder, os.path.basename(xlite_release_url))
            else:
                self.executable_path = None
            xlite_volume_name = self.container.xlite_volume_name
            if xlite_volume_name:
                self.dmg_mount_path = f"/Volumes/{xlite_volume_name}"
            else:
                self.dmg_mount_path = None
        else:
            aio_folder = self.container.aio_folder
            curpath = self.container.xlite_curpath
            bin_name = self.container.xlite_bin
            if aio_folder and curpath and bin_name:
                self.executable_path = os.path.join(aio_folder, curpath, bin_name)
            else:
                self.executable_path = None
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
                port = self.xlite_daemon_confs_local[coin]["rpcPort"]
                user = self.xlite_daemon_confs_local[coin]["rpcUsername"]
                password = self.xlite_daemon_confs_local[coin]["rpcPassword"]
                self.coins_rpc[coin] = RPCClient(rpc_user=user, rpc_password=password, rpc_port=port)

    def check_xlite_daemon_confs(self):
        while self.running and not self.valid_coins_rpc:
            self.check_xlite_daemon_confs_sequence(silent=True)
            time.sleep(1)

    def check_valid_xlite_coins_rpc(self, runonce=False):
        while self.running:
            valid = False
            if self.coins_rpc:
                for coin, rpc_server in self.coins_rpc.items():
                    if coin != "master" and coin != "TBLOCK":
                        if self.xlite_daemon_confs_local[coin]["rpcEnabled"] is True:
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

            time.sleep(1)

    def start_threads(self):
        thread = threading.Thread(target=self.check_xlite_daemon_confs)
        thread.start()
        thread = threading.Thread(target=self.check_valid_xlite_coins_rpc)
        thread.start()

    def parse_xlite_conf(self):
        data_folder = self.container.conf_data.xlite_default_paths.get(self.container.system, None)
        if data_folder is None:
            self.xlite_conf_local = {}
            return

        data_folder = os.path.expandvars(os.path.expanduser(data_folder))
        file = "app-settings.json"
        file_path = os.path.join(data_folder, file)
        meta_data = {}

        if os.path.exists(file_path):
            try:
                with open(file_path) as file:
                    meta_data = json.load(file)
                    logger.info(f"XLITE: Loaded JSON data from [{file_path}]")
            except Exception as e:
                logger.error(f"Error parsing {file_path}: {e}, repairing file")
        self.xlite_conf_local = meta_data

    def parse_xlite_daemon_conf(self, silent=False):
        daemon_data_path = self.container.conf_data.xlite_daemon_default_paths.get(self.container.system, None)
        if daemon_data_path is None:
            self.xlite_daemon_confs_local = {}
            return

        daemon_data_path = os.path.expandvars(os.path.expanduser(daemon_data_path))
        confs_folder = os.path.join(daemon_data_path, "settings")

        if not os.path.exists(confs_folder):
            self.xlite_daemon_confs_local = {}
            return

        files_in_folder = os.listdir(confs_folder)

        json_files = [file for file in files_in_folder if file.endswith(".json")]

        for json_file in json_files:
            json_file_path = os.path.join(confs_folder, json_file)
            coin = str(json_file).split("-")[1].split(".")[0]
            try:
                with open(json_file_path) as file:
                    data = json.load(file)
                self.xlite_daemon_confs_local[coin] = data
            except Exception as e:
                self.xlite_daemon_confs_local[coin] = "ERROR PARSING"
                logger.error(f"Error parsing {json_file_path}: {e}")
        if not silent:
            logger.info(
                f"XLITE-DAEMON: Parsed coins confs from [{confs_folder}] {list(self.xlite_daemon_confs_local.keys())}"
            )

    def start_xlite(self, env_vars=None):
        if env_vars is None:
            env_vars = []
        if self.container.system == "Windows":
            check_vc_redist_installed(self.container)

        if self.executable_path and not os.path.exists(self.executable_path):
            logger.info(f"Xlite executable not found at {self.executable_path}. Downloading...")
            self.download_xlite_bin()

        # Get launch options for current OS
        launch_options = self.container.conf_data.xlite_launch_options.get(self.container.system, None)

        try:
            if self.container.system == "Darwin":
                self.handle_dmg("mount")
                full_path = os.path.join(
                    self.dmg_mount_path or "", *self.container.conf_data.xlite_bin_name[self.container.system]
                )
                xlite_volume_name = self.container.xlite_volume_name
                logger.info(
                    f"volume_name: {xlite_volume_name}, mount_path: {self.dmg_mount_path}, full_path: {full_path}"
                )
                command = [full_path] + launch_options
                cwd = os.path.dirname(full_path)
            else:
                command = [self.executable_path] + launch_options
                cwd = os.path.dirname(self.executable_path or "")

            parsed_env_vars = {}
            for env_var_str in env_vars:
                if "=" in env_var_str:
                    key, value = env_var_str.split("=", 1)
                    parsed_env_vars[key] = value
                else:
                    logger.warning(f"Environment variable string '{env_var_str}' does not contain '='. Skipping.")
            self.xlite_process = self.start_process(command, cwd=cwd, env_vars=parsed_env_vars)
            self.process = self.xlite_process
            logger.info(f"Started Xlite process with PID {self.xlite_process.pid}: {command}")
        except Exception as e:
            logger.error(f"Error starting Xlite process: {e}\n{traceback.format_exc()}")
            raise

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
        # Use container's Rosetta-aware URL (supports Darwin arm64 fallback to x86_64)
        url = self.container.xlite_release_url
        if url is None:
            # Fallback to direct dict for edge cases, with alias handling
            from utilities.app_container import _get_value_from_config

            url = _get_value_from_config(
                self.container.conf_data.xlite_releases_urls, self.container.system, self.container.machine
            )
        if url is None:
            raise ValueError(f"Unsupported OS or architecture {self.container.system} {self.container.machine}")

        tmp_filename = "tmp_xl_bin"
        aio_folder = self.container.aio_folder
        if not aio_folder:
            raise ValueError("AIO folder not configured")

        if not self.executable_path:
            raise ValueError("Executable path not configured")

        self.download_binary(url, tmp_filename, self.executable_path, aio_folder)

    def unmount_dmg(self):
        if self.container.system != "Darwin":
            logger.warning(f"Call unmount_dmg with wrong OS, {self.container.system} ?")
            return
        self.handle_dmg("unmount")
