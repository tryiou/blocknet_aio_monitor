import json
import logging
import os
import random
import shutil
import string
import threading
import time
import zipfile

import requests
from typing import Optional

from utilities.app_container import get_container, AppContainer
from utilities.rpc_client import RPCClient

logger = logging.getLogger(__name__)


from utilities.bin_handlers.base_binutil import BaseBinUtil


class BlocknetHandler(BaseBinUtil):
    def __init__(self, custom_path: Optional[str] = None, container: Optional[AppContainer] = None):
        super().__init__("Blocknet", container)
        self.blocknet_exe = self.container.get_blocknet_executable_path()
        self.parsed_wallet_confs = {}
        self.parsed_xbridge_confs = {}
        self.bootstrap_checking = False
        self.bootstrap_extracting = False
        self.bootstrap_percent_download = None
        self.downloading_bin = False
        self.data_folder = get_blocknet_data_folder(custom_path)
        self.process_running = None
        self.blocknet_conf_local = None
        self.xbridge_conf_local = None
        self.xb_manifest = retrieve_xb_manifest()
        self.blocknet_conf_remote = retrieve_remote_blocknet_conf()
        self.blocknet_xbridge_conf_remote = retrieve_remote_blocknet_xbridge_conf()
        self.blocknet_pids = []
        self.blocknet_process = None
        self.blocknet_rpc = None
        self.valid_rpc = False
        self.running = True  # flag for async funcs
        self.parse_blocknet_conf()
        self.parse_xbridge_conf()
        self.init_blocknet_rpc()
        self.start_rpc_check_thread()

    def start_rpc_check_thread(self):
        thread = threading.Thread(target=self.check_blocknet_rpc)
        thread.start()

    def check_blocknet_rpc(self):
        while self.running:
            valid = False
            if self.blocknet_rpc:
                result = self.blocknet_rpc.send_rpc_request('getnetworkinfo')
                if result:
                    valid = True
            self.valid_rpc = valid

            time.sleep(1)

    def init_blocknet_rpc(self):
        if self.blocknet_conf_local and 'global' in self.blocknet_conf_local:
            global_conf = self.blocknet_conf_local['global']
            rpc_user = global_conf.get('rpcuser')
            rpc_password = global_conf.get('rpcpassword')
            rpc_port = int(global_conf.get('rpcport', 0))
        else:
            rpc_user = None
            rpc_password = None
            rpc_port = 0

        if rpc_user is not None and rpc_password is not None and rpc_port != 0:
            self.blocknet_rpc = RPCClient(rpc_user, rpc_password, rpc_port)
        else:
            logger.error("RPC user, password, or port not found in the configuration.")
            self.blocknet_rpc = None

    def start_blocknet(self):
        self.create_data_folder()
        if not os.path.exists(self.blocknet_exe):
            logger.info(f"Blocknet executable not found at {self.blocknet_exe}. Downloading...")
            self.download_blocknet_bin()
        try:
            command = [self.blocknet_exe, f"-datadir={self.data_folder}"]
            self.blocknet_process = self.start_process(command)
            self.process = self.blocknet_process
            logger.info(f"Started Blocknet process: {command} with data directory: {self.data_folder}")
        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
            raise

    def close_blocknet(self):
        if self.blocknet_process:
            self.graceful_terminate(timeout=60)
        else:
            self.close_blocknet_pids()

    def kill_blocknet(self):
        self.force_kill()

    def close_blocknet_pids(self):
        self.terminate_processes(self.blocknet_pids, "Blocknet")

    def check_data_folder_existence(self):
        return self.data_folder is not None and os.path.exists(self.data_folder)

    def set_custom_data_path(self, custom_path):
        if not os.path.exists(custom_path):
            os.makedirs(custom_path)
            logger.info(f"Custom data path created: {custom_path}")
        self.data_folder = custom_path
        logger.debug(f"Custom data path set: {custom_path}")
        self.parse_blocknet_conf()
        self.parse_xbridge_conf()
        self.init_blocknet_rpc()

    def parse_blocknet_conf(self):
        if not self.data_folder:
            logger.error("Data folder not configured")
            self.blocknet_conf_local = {}
            return
            
        file = "blocknet.conf"
        conf_file_path = os.path.join(self.data_folder, file)
        if os.path.exists(conf_file_path):
            self.blocknet_conf_local = parse_conf_file(file_path=conf_file_path)
            logger.info(f"BLOCKNET: Parsed ok: [{conf_file_path}]")
        else:
            self.blocknet_conf_local = {}
            logger.warning(f"{conf_file_path} file does not exist.")

    def parse_xbridge_conf(self):
        if not self.data_folder:
            logger.error("Data folder not configured")
            self.xbridge_conf_local = {}
            return
            
        conf_file_path = os.path.join(self.data_folder, "xbridge.conf")
        if os.path.exists(conf_file_path):
            self.xbridge_conf_local = parse_conf_file(file_path=conf_file_path)
            logger.info(f"BLOCKNET: Parsed ok: [{conf_file_path}]")
        else:
            self.xbridge_conf_local = {}
            logger.warning(f"{conf_file_path} file does not exist.")

    def save_blocknet_conf(self):
        if not self.data_folder:
            logger.error("Data folder not configured")
            return
        conf_file_path = os.path.join(self.data_folder, "blocknet.conf")
        save_conf_to_file(self.blocknet_conf_local, conf_file_path)

    def save_xbridge_conf(self):
        if not self.data_folder:
            logger.error("Data folder not configured")
            return
        conf_file_path = os.path.join(self.data_folder, "xbridge.conf")
        save_conf_to_file(self.xbridge_conf_local, conf_file_path)

    def check_blocknet_conf(self):
        self.parse_blocknet_conf()
        old_local_json = json.dumps(self.blocknet_conf_local, sort_keys=True)

        if self.blocknet_conf_remote is None:
            logger.error("Remote blocknet.conf not available.")
            return False

        if self.blocknet_conf_local is None:
            logger.error("Local blocknet.conf not available.")
            return False

        section_name = 'global'
        if section_name not in self.blocknet_conf_local:
            self.blocknet_conf_local[section_name] = {}

        # Process remote config options
        for section, options in self.blocknet_conf_remote.items():
            for key, value in options.items():
                if key == 'rpcuser' or key == 'rpcpassword':
                    if key not in self.blocknet_conf_local[section]:
                        self.blocknet_conf_local[section][key] = generate_random_string(32)
                    else:
                        if self.blocknet_conf_local[section][key] == '':
                            self.blocknet_conf_local[section][key] = generate_random_string(32)
                else:
                    if key == "rpcallowip":
                        self.blocknet_conf_local[section][key] = "127.0.0.1"
                    elif key not in self.blocknet_conf_local[section] or self.blocknet_conf_local[section][
                        key] != value:
                        self.blocknet_conf_local[section][key] = value

        # Handle extra options
        extra_options = self.container.conf_data.extra_option_blocknet_core_conf
        if extra_options and len(extra_options) > 0:
            # Process each option
            for option in extra_options:
                for key, value in option.items():
                    conf_value = self.blocknet_conf_local[section_name].get(key)

                    # Initialize or convert to list if needed
                    if not isinstance(conf_value, list):
                        self.blocknet_conf_local[section_name][key] = list(
                            conf_value.split(',') if conf_value else []
                        )

                    # Convert option value to string for comparison
                    str_value = str(value)

                    # Add new value if not already present
                    if str_value not in self.blocknet_conf_local[section_name][key]:
                        self.blocknet_conf_local[section_name][key].append(str_value)
                        logger.info(f"Added config option: {key}={str_value}")

        logger.info("Local blocknet.conf updated successfully.")

        new_local_json = json.dumps(self.blocknet_conf_local, sort_keys=True)

        if old_local_json != new_local_json:
            logger.info("Local blocknet.conf has been updated. Saving...")
            self.save_blocknet_conf()
            self.init_blocknet_rpc()
            return True
        else:
            logger.info("Local blocknet.conf remains the same. No need to save.")
            return False

    def _update_extra_config_options(self):
        """Helper method to handle extra config options with list value handling"""
        section_name = 'global'
        if not self.container.conf_data.extra_option_blocknet_core_conf:
            return

        # Ensure global section exists
        if section_name not in self.blocknet_conf_local:
            self.blocknet_conf_local[section_name] = {}

        # Process each option
        for option in self.container.conf_data.extra_option_blocknet_core_conf:
            for key, value in option.items():
                conf_value = self.blocknet_conf_local[section_name].get(key)

                # Initialize or convert to list if needed
                if not isinstance(conf_value, list):
                    self.blocknet_conf_local[section_name][key] = list(
                        conf_value.split(',') if conf_value else []
                    )

                # Convert option value to string for comparison
                str_value = str(value)

                # Add new value if not already present
                if str_value not in self.blocknet_conf_local[section_name][key]:
                    self.blocknet_conf_local[section_name][key].append(str_value)
                    logger.info(f"Added config option: {key}={str_value}")

    def retrieve_coin_conf(self, coin):
        if not self.xb_manifest:
            logger.error("XB manifest not available")
            return
            
        latest_version = None
        highest_version_id = None

        for entry in self.xb_manifest:
            if 'ticker' in entry and entry['ticker'] == coin.upper():
                ver_id = entry['ver_id']
                if latest_version is None or ver_id > highest_version_id:
                    latest_version = entry
                    highest_version_id = ver_id

        if latest_version:
            xbridge_conf = latest_version['xbridge_conf']
            xbridge_url = f"{self.container.conf_data.remote_blockchain_configuration_repo}/xbridge-confs/{xbridge_conf}"
            wallet_conf = latest_version['wallet_conf']
            wallet_conf_url = f"{self.container.conf_data.remote_blockchain_configuration_repo}/wallet-confs/{wallet_conf}"
            parsed_xbridge_conf = retrieve_remote_conf(xbridge_url, "xbridge-confs", xbridge_conf)
            parsed_wallet_conf = retrieve_remote_conf(wallet_conf_url, "wallet-confs", wallet_conf)
            self.parsed_xbridge_confs[coin] = parsed_xbridge_conf
            self.parsed_wallet_confs[coin] = parsed_wallet_conf
        else:
            logger.error("No entries found in the manifest. " + coin)

    def check_xbridge_conf(self, xlite_daemon_conf):
        self.parse_xbridge_conf()
        old_local_json = json.dumps(self.xbridge_conf_local, sort_keys=True)

        if self.xbridge_conf_local is None:
            self.xbridge_conf_local = {}
        
        if 'Main' not in self.xbridge_conf_local:
            self.xbridge_conf_local['Main'] = self.container.conf_data.base_xbridge_conf

        if self.blocknet_xbridge_conf_remote is None:
            logger.error("Remote xbridge.conf not available.")
            return False
        if xlite_daemon_conf:
            for coin in xlite_daemon_conf:
                if coin == "master":
                    continue
                self.retrieve_coin_conf(coin)
                if coin in self.parsed_xbridge_confs:
                    if coin not in self.xbridge_conf_local:
                        self.xbridge_conf_local[coin] = {}
                    for section, options in self.parsed_xbridge_confs[coin].items():
                        if section not in self.xbridge_conf_local:
                            self.xbridge_conf_local[section] = {}
                        for key, value in options.items():
                            if key == 'Username':
                                self.xbridge_conf_local[section][key] = str(xlite_daemon_conf[coin]['rpcUsername'])
                            elif key == 'Password':
                                self.xbridge_conf_local[section][key] = str(xlite_daemon_conf[coin]['rpcPassword'])
                            elif key == 'Port':
                                self.xbridge_conf_local[section][key] = str(xlite_daemon_conf[coin]['rpcPort'])
                            else:
                                if key not in self.xbridge_conf_local[section] or self.xbridge_conf_local[section][
                                    key] != value:
                                    self.xbridge_conf_local[section][key] = str(value)

        if not (xlite_daemon_conf and "BLOCK" in xlite_daemon_conf):
            for section, options in self.blocknet_xbridge_conf_remote.items():
                if section not in self.xbridge_conf_local:
                    self.xbridge_conf_local[section] = {}
                logger.info(f"section: {section}, options: {options}")
                for key, value in options.items():
                    if key == 'Username':
                        if (self.blocknet_conf_local and 'global' in self.blocknet_conf_local and 
                            'rpcuser' in self.blocknet_conf_local['global']):
                            self.xbridge_conf_local[section][key] = str(self.blocknet_conf_local['global']['rpcuser'])
                    elif key == 'Password':
                        if (self.blocknet_conf_local and 'global' in self.blocknet_conf_local and 
                            'rpcpassword' in self.blocknet_conf_local['global']):
                            self.xbridge_conf_local[section][key] = str(self.blocknet_conf_local['global']['rpcpassword'])
                    elif key == 'Port':
                        if (self.blocknet_conf_local and 'global' in self.blocknet_conf_local and 
                            'rpcport' in self.blocknet_conf_local['global']):
                            self.xbridge_conf_local[section][key] = str(self.blocknet_conf_local['global']['rpcport'])
                    else:
                        if key not in self.xbridge_conf_local[section] or self.xbridge_conf_local[section][
                            key] != value:
                            self.xbridge_conf_local[section][key] = str(value)

        if self.xbridge_conf_local is None:
            self.xbridge_conf_local = {}
        sections_string = ','.join(section for section in self.xbridge_conf_local.keys() if section != 'Main')

        if 'Main' in self.xbridge_conf_local:
            self.xbridge_conf_local['Main']['ExchangeWallets'] = sections_string
        else:
            self.xbridge_conf_local['Main'] = {
                'ExchangeWallets': sections_string,
                'FullLog': self.container.conf_data.base_xbridge_conf['FullLog'],
                'ShowAllOrders': self.container.conf_data.base_xbridge_conf['ShowAllOrders'],
            }

        new_local_json = json.dumps(self.xbridge_conf_local, sort_keys=True)
        if old_local_json != new_local_json:
            logger.info("Local xbridge.conf has been updated. Saving...")
            self.save_xbridge_conf()
            return True
        else:
            logger.info("Local xbridge.conf remains the same. No need to save.")
            return False

    def compare_and_update_local_conf(self, xlite_daemon_conf=None):
        self.check_blocknet_conf()
        self.check_xbridge_conf(xlite_daemon_conf)

    def create_data_folder(self):
        if self.data_folder and not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)

    def create_aio_folder(self):
        aio_folder = self.container.aio_folder
        if aio_folder and not os.path.exists(aio_folder):
            os.makedirs(aio_folder)

    def download_bootstrap(self):
        self.create_data_folder()
        self.create_aio_folder()

        self.bootstrap_checking = True
        filename = "Blocknet.zip"
        aio_folder = self.container.aio_folder
        if aio_folder is None:
            raise ValueError("AIO folder not configured")
        local_file_path = os.path.join(aio_folder, filename)
        remote_file_size = get_remote_file_size(self.container.conf_data.blocknet_bootstrap_url)
        need_to_download = True
        if os.path.exists(local_file_path):
            local_file_size = os.path.getsize(local_file_path)

            if local_file_size == remote_file_size:
                logger.info("Bootstrap file already exists on disk and matches the remote file.")
                need_to_download = False
            else:
                logger.info("Local bootstrap file exists but does not match the remote file. Re-downloading...")
                os.remove(local_file_path)
        try:
            if need_to_download:
                with open(local_file_path, 'wb') as f:
                    response = requests.get(self.container.conf_data.blocknet_bootstrap_url, stream=True,
                                            timeout=(10, 30))
                    response.raise_for_status()
                    if response.status_code == 200:
                        logger.info(
                            f"Downloading {self.container.conf_data.blocknet_bootstrap_url} to {local_file_path}, remote size: {int(remote_file_size / 1024)} kb")
                        bytes_downloaded = 0
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                bytes_downloaded += len(chunk)
                                self.bootstrap_percent_download = (bytes_downloaded / remote_file_size) * 100
                    else:
                        logger.error("Failed to download the Blocknet Bootstrap.")

                self.bootstrap_percent_download = None

                if os.path.getsize(local_file_path) != remote_file_size:
                    os.remove(local_file_path)
                    raise ValueError(f"Downloaded {filename} file size doesn't match the expected size. Deleting it")

                logger.info(f"{filename} Bootstrap downloaded successfully.")

            to_delete = ['blocks', 'chainstate', 'indexes', 'peers.dat', 'banlist.dat']
            if not self.data_folder:
                logger.error("Data folder not configured for bootstrap cleanup")
                return
            for item_name in to_delete:
                item_path = os.path.join(self.data_folder, item_name)
                if os.path.exists(item_path):
                    if os.path.isdir(item_path):
                        logger.info(f"Deleting existing folder: {item_name}...")
                        shutil.rmtree(item_path)
                        logger.info(f"{item_name} folder deleted successfully.")
                    else:
                        logger.info(f"Deleting existing file: {item_name}...")
                        os.remove(item_path)
                        logger.info(f"{item_name} deleted successfully.")
            logger.info("Extracting bootstrap...")
            with zipfile.ZipFile(local_file_path, "r") as zip_ref:
                self.bootstrap_extracting = True
                zip_ref.extractall(self.data_folder)
            self.bootstrap_extracting = False
            logger.info("Extraction completed.")

        except Exception as e:
            logger.error(f"An error occurred: {str(e)}")
            self.bootstrap_percent_download = None
        finally:
            self.bootstrap_checking = False

    def download_blocknet_bin(self):
        url = self.container.blocknet_release_url
        if url is None:
            raise ValueError(f"Unsupported OS or architecture {self.container.system} {self.container.machine}")

        aio_folder = self.container.aio_folder
        if aio_folder is None:
            raise ValueError("AIO folder not configured")

        self.download_binary(
            url,
            os.path.basename(url),
            self.blocknet_exe,
            aio_folder
        )


def get_remote_file_size(url):
    r = requests.head(url)
    r.raise_for_status()
    return int(r.headers.get('content-length', 0))


def generate_random_string(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def save_conf_to_file(conf_data, file_path):
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            for section, options in conf_data.items():
                if section != 'global':
                    f.write(f"[{section}]\n")
                for key, value in options.items():
                    if isinstance(value, list):
                        for item in value:
                            f.write(f"{key}={item}\n")
                    else:
                        f.write(f"{key}={value}\n")

        logger.info(f"Configuration data saved to {file_path} successfully")
        return True
    except Exception as e:
        logger.error(f"Error saving configuration data to {file_path}: {e}")
        return False


def retrieve_remote_conf(remote_url: str, subfolder: str, expected_filename: str):
    container = get_container()
    folder = "xb_conf"
    aio_folder = container.aio_folder
    if aio_folder is None:
        raise ValueError("AIO folder not configured")
    local_conf_file = os.path.join(aio_folder, folder, subfolder, expected_filename)

    if os.path.exists(local_conf_file):
        try:
            with open(local_conf_file, 'r') as f:
                conf_data = f.read()
            parsed_conf = parse_conf_file(input_string=conf_data)
            if parsed_conf:
                logger.info(f"REMOTE: found and parsed ok: [{local_conf_file}]")
                return parsed_conf
            else:
                logger.error(f"Failed to parse: {local_conf_file}")
        except Exception as e:
            logger.error(f"{local_conf_file} Error opening or parsing file: {e}")

    return download_remote_conf(remote_url, local_conf_file)


def download_remote_conf(url, filepath):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            conf_data = response.text
            parsed_conf = parse_conf_file(input_string=conf_data)
            if parsed_conf:
                save_conf_to_file(parsed_conf, filepath)
                logger.info(f"retrieved and parsed ok: [{filepath}]")
                return parsed_conf
            else:
                logger.error(f"Failed to parse {filepath} ")
                return None
        else:
            logger.error(
                f"Failed to retrieve remote blocknet configuration file: {url} {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving remote blocknet configuration file: {e}")
        return None


def retrieve_xb_manifest():
    container = get_container()
    folder = "xb_conf"
    filename = os.path.basename(container.conf_data.remote_manifest_url)
    aio_folder = container.aio_folder
    if aio_folder is None:
        raise ValueError("AIO folder not configured")
    local_manifest_file = os.path.join(aio_folder, folder, filename)

    try:
        response = requests.get(container.conf_data.remote_manifest_url)
        if response.status_code == 200:
            parsed_json = response.json()
            os.makedirs(os.path.dirname(local_manifest_file), exist_ok=True)
            with open(local_manifest_file, 'w') as f:
                f.write(json.dumps(parsed_json, indent=4))
            logger.info(f"REMOTE: Retrieved and parsed ok: [{local_manifest_file}]")
            return parsed_json
        else:
            logger.error(
                f"Failed to retrieve remote configuration file: {container.conf_data.remote_manifest_url} {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error retrieving remote configuration file: {e}")
        return None


def retrieve_remote_blocknet_conf():
    container = get_container()
    filename = os.path.basename(container.conf_data.remote_blocknet_conf_url)
    return retrieve_remote_conf(container.conf_data.remote_blocknet_conf_url, "wallet-confs", filename)


def retrieve_remote_blocknet_xbridge_conf():
    container = get_container()
    filename = os.path.basename(container.conf_data.remote_xbridge_conf_url)
    return retrieve_remote_conf(container.conf_data.remote_xbridge_conf_url, "xbridge-confs", filename)


def parse_conf_file(file_path=None, input_string=None):
    conf_data = {}
    current_section = 'global'

    if file_path:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key.strip() == 'addnode':
                        conf_data.setdefault(current_section.strip('[]'), {}).setdefault(key.strip(), []).append(
                            value.strip())
                    else:
                        conf_data.setdefault(current_section.strip('[]'), {})[key.strip()] = value.strip()
                else:
                    current_section = line.strip()
                    conf_data.setdefault(current_section.strip('[]'), {})

    elif input_string:
        for line in input_string.split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                if key.strip() == 'addnode':
                    conf_data.setdefault(current_section.strip('[]'), {}).setdefault(key.strip(), []).append(
                        value.strip())
                else:
                    conf_data.setdefault(current_section.strip('[]'), {})[key.strip()] = value.strip()
            else:
                current_section = line.strip()
                conf_data.setdefault(current_section.strip('[]'), {})

    return conf_data


def get_blocknet_data_folder(custom_path: Optional[str] = None):
    container = get_container()
    if custom_path:
        path = custom_path
    else:
        path = container.conf_data.blocknet_default_paths.get(container.system)
    if path:
        expanded_path = os.path.expandvars(os.path.expanduser(path))
        return os.path.normpath(expanded_path)
    else:
        logger.error(f"invalid blocknet data folder path: {path}")
