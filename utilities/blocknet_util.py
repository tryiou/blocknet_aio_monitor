import json
import logging
import os
import random
import shutil
import string
import subprocess
import tarfile
import threading
import time
import zipfile
from subprocess import check_output

import psutil
import requests

# from utilities.conf_data import (remote_blocknet_conf_url, blocknet_default_paths, base_xbridge_conf, blocknet_bin_path,
#                                  blocknet_bootstrap_url, nodes_to_add, remote_xbridge_conf_url, remote_manifest_url,
#                                  remote_blockchain_configuration_repo)
from utilities import global_variables

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Disable log entries from the urllib3 module (used by requests)
urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.WARNING)


class BlocknetRPCClient:
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


class BlocknetUtility:
    def __init__(self, custom_path=None):
        self.blocknet_exe = global_variables.os.path.join(global_variables.aio_folder,
                                                          *global_variables.conf_data.blocknet_bin_path,
                                                          global_variables.blocknet_bin)
        self.binary_percent_download = None
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

            # logging.info(result)
            time.sleep(2)

    def init_blocknet_rpc(self):
        # Retrieve RPC user, password, and port from blocknet_conf_local with error handling
        if 'global' in self.blocknet_conf_local:
            global_conf = self.blocknet_conf_local['global']
            rpc_user = global_conf.get('rpcuser')
            rpc_password = global_conf.get('rpcpassword')
            rpc_port = int(global_conf.get('rpcport', 0))  # Assuming default port is 0, change as per requirement
        else:
            rpc_user = None
            rpc_password = None
            rpc_port = 0

        # Initialize BlocknetRPCClient if RPC user, password, and port are available
        if rpc_user is not None and rpc_password is not None and rpc_port != 0:
            self.blocknet_rpc = BlocknetRPCClient(rpc_user, rpc_password, rpc_port)
        else:
            # Handle the case when RPC user, password, or port is missing
            logging.error("RPC user, password, or port not found in the configuration.")
            self.blocknet_rpc = None

    def start_blocknet(self):
        self.create_data_folder()
        if not os.path.exists(self.blocknet_exe):
            logging.info(f"Blocknet executable not found at {self.blocknet_exe}. Downloading...")
            self.download_blocknet_bin()
        try:
            # Start the Blocknet process using subprocess with custom data folder argument
            self.blocknet_process = subprocess.Popen([self.blocknet_exe, f"-datadir={self.data_folder}"],
                                                     stdout=subprocess.PIPE,
                                                     stderr=subprocess.PIPE,
                                                     stdin=subprocess.PIPE,
                                                     start_new_session=True)
            logging.info(f"Started Blocknet process: {self.blocknet_exe} with data directory: {self.data_folder}")
        except Exception as e:
            logging.error(f"Error: {e}")

    def close_blocknet(self):
        # Close the Blocknet subprocess if it exists
        if self.blocknet_process:
            try:
                self.blocknet_process.terminate()
                # logging.info(f"Terminating Blocknet subprocess.")
                self.blocknet_process.wait(timeout=60)  # Wait for the process to terminate with a timeout of 60 seconds
                logging.info(f"Closed Blocknet subprocess.")
                self.blocknet_process = None
                return
            except subprocess.TimeoutExpired:
                logging.info(f"Force terminating Blocknet subprocess.")
                self.kill_blocknet()
                logging.info(f"Blocknet subprocess has been force terminated.")
                self.blocknet_process = None
                return
            except Exception as e:
                logging.error(f"Error: {e}")
        else:
            self.close_blocknet_pids()

    def kill_blocknet(self):
        # Kill the Blocknet subprocess if it exists
        if self.blocknet_process:
            try:
                self.blocknet_process.kill()
                logging.info(f"Killed Blocknet subprocess.")
                self.blocknet_process = None
                return
            except Exception as e:
                logging.error(f"Error: {e}")

    def close_blocknet_pids(self):
        # Close the Blocknet processes using their PIDs
        for pid in self.blocknet_pids:
            try:
                # Get the process object corresponding to the PID
                proc = psutil.Process(pid)
                proc.terminate()
                logging.info(f"Initiated termination of Blocknet process with PID {pid}.")
                proc.wait(timeout=60)  # Wait for the process to terminate with a timeout of 60 seconds
                logging.info(f"Blocknet process with PID {pid} has been terminated.")
            except psutil.NoSuchProcess:
                logging.warning(f"Blocknet process with PID {pid} not found.")
            except psutil.TimeoutExpired:
                logging.warning(f"Force terminating Blocknet process with PID {pid}.")
                proc.kill()
                proc.wait()
                logging.info(f"Blocknet process with PID {pid} has been force terminated.")
            except Exception as e:
                logging.error(f"Error: {e}")

    def check_data_folder_existence(self):
        return os.path.exists(self.data_folder)

    def set_custom_data_path(self, custom_path):
        if not os.path.exists(custom_path):
            os.makedirs(custom_path)  # Recursively create the folder if it doesn't exist
            logging.info(f"Custom data path created: {custom_path}")
        self.data_folder = custom_path
        logging.debug(f"Custom data path set: {custom_path}")
        self.parse_blocknet_conf()
        self.parse_xbridge_conf()
        self.init_blocknet_rpc()

    def parse_blocknet_conf(self):
        file = "blocknet.conf"
        conf_file_path = os.path.join(self.data_folder, file)
        if os.path.exists(conf_file_path):
            self.blocknet_conf_local = parse_conf_file(file_path=conf_file_path)
            logging.info(f"BLOCKNET: Parsed ok: [{conf_file_path}]")
        else:
            self.blocknet_conf_local = {}
            logging.warning(f"{conf_file_path} file does not exist.")

    def parse_xbridge_conf(self):
        conf_file_path = os.path.join(self.data_folder, "xbridge.conf")
        if os.path.exists(conf_file_path):
            self.xbridge_conf_local = parse_conf_file(file_path=conf_file_path)
            logging.info(f"BLOCKNET: Parsed ok: [{conf_file_path}]")
        else:
            self.xbridge_conf_local = {}
            logging.warning(f"{conf_file_path} file does not exist.")

    def save_blocknet_conf(self):
        conf_file_path = os.path.join(self.data_folder, "blocknet.conf")
        save_conf_to_file(self.blocknet_conf_local, conf_file_path)

    def save_xbridge_conf(self):
        conf_file_path = os.path.join(self.data_folder, "xbridge.conf")
        save_conf_to_file(self.xbridge_conf_local, conf_file_path)

    def check_blocknet_conf(self):
        self.parse_blocknet_conf()
        # logging.info(f"Current remote configuration:\n{self.blocknet_conf_remote}")
        # logging.info(f"Current local configuration:\n{self.blocknet_conf_local}")

        old_local_json = json.dumps(self.blocknet_conf_local, sort_keys=True)

        if self.blocknet_conf_remote is None:
            logging.error("Remote blocknet.conf not available.")
            return False

        if self.blocknet_conf_local is None:
            logging.error("Local blocknet.conf not available.")
            return False

        section_name = 'global'
        if section_name not in self.blocknet_conf_local:
            self.blocknet_conf_local[section_name] = {}

        if 'rpcthreads' not in self.blocknet_conf_local[section_name] or int(
                self.blocknet_conf_local[section_name]['rpcthreads']) < 32:
            self.blocknet_conf_local[section_name]['rpcthreads'] = 32

        if 'rpcworkqueue' not in self.blocknet_conf_local[section_name] or int(
                self.blocknet_conf_local[section_name]['rpcworkqueue']) < 64:
            self.blocknet_conf_local[section_name]['rpcworkqueue'] = 64

        if 'rpcxbridgetimeout' not in self.blocknet_conf_local[section_name] or int(
                self.blocknet_conf_local[section_name]['rpcxbridgetimeout']) < 120:
            self.blocknet_conf_local[section_name]['rpcxbridgetimeout'] = 120

        addnode_value = self.blocknet_conf_local[section_name].get('addnode', [])
        if not isinstance(addnode_value, list):
            addnode_value = [addnode_value]

        # Add the nodes to the end of the file if not already existing
        for node in global_variables.conf_data.nodes_to_add:
            if node not in addnode_value:
                addnode_value.append(node)
                logging.info(f"Added new node: {node}")

        self.blocknet_conf_local[section_name]['addnode'] = addnode_value

        for section, options in self.blocknet_conf_remote.items():
            # if section not in self.blocknet_conf_local:
            #     self.blocknet_conf_local[section] = {}

            for key, value in options.items():
                if key == 'rpcuser' or key == 'rpcpassword':
                    if key not in self.blocknet_conf_local[section]:
                        self.blocknet_conf_local[section][key] = generate_random_string(32)
                        # logging.info(f"Generated {key} value: {self.blocknet_conf_local[section][key]}")
                    else:
                        if self.blocknet_conf_local[section][key] == '':
                            self.blocknet_conf_local[section][key] = generate_random_string(32)
                            # logging.info(
                            #     f"Value for {key} is empty. Generated new value: {self.blocknet_conf_local[section][key]}")
                            # CHECK IF VALUE IS NOT EMPTY STRING ELSE GENERATE NEW VALUE
                else:
                    if key == "rpcallowip":
                        self.blocknet_conf_local[section][key] = "127.0.0.1"
                    elif key not in self.blocknet_conf_local[section] or self.blocknet_conf_local[section][
                        key] != value:
                        self.blocknet_conf_local[section][key] = value
                        # logging.debug(f"Updated {key} value: {value}")

        logging.info("Local blocknet.conf updated successfully.")

        new_local_json = json.dumps(self.blocknet_conf_local, sort_keys=True)

        # logging.info(f"Old local configuration:\n{old_local_json}")
        # logging.info(f"Updated local configuration:\n{new_local_json}")
        # logging.info(new_local_json)
        if old_local_json != new_local_json:
            logging.info("Local blocknet.conf has been updated. Saving...")
            self.save_blocknet_conf()
            self.init_blocknet_rpc()
            return True
        else:
            logging.info("Local blocknet.conf remains the same. No need to save.")
            return False

    def retrieve_coin_conf(self, coin):
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
            xbridge_url = f"{global_variables.conf_data.remote_blockchain_configuration_repo}/xbridge-confs/{xbridge_conf}"
            wallet_conf = latest_version['wallet_conf']
            wallet_conf_url = f"{global_variables.conf_data.remote_blockchain_configuration_repo}/wallet-confs/{wallet_conf}"
            # download_remote_conf()
            parsed_xbridge_conf = retrieve_remote_conf(xbridge_url, "xbridge-confs", xbridge_conf)
            parsed_wallet_conf = retrieve_remote_conf(wallet_conf_url, "wallet-confs", wallet_conf)
            self.parsed_xbridge_confs[coin] = parsed_xbridge_conf
            self.parsed_wallet_confs[coin] = parsed_wallet_conf
            # logging.info(parsed_xbridge_conf)
            # logging.info(parsed_wallet_conf)
            # Do whatever you need to do with the highest version entry
        else:
            logging.error("No entries found in the manifest. " + coin)

    def check_xbridge_conf(self, xlite_daemon_conf):
        self.parse_xbridge_conf()
        # logging.info(f"Current local configuration:\n{self.xbridge_conf_local}")
        # logging.info(f"Current remote configuration:\n{self.xbridge_conf_remote}")

        old_local_json = json.dumps(self.xbridge_conf_local, sort_keys=True)

        if 'Main' not in self.xbridge_conf_local:
            # We want this on 'top' of file, add it if missing
            self.xbridge_conf_local['Main'] = global_variables.conf_data.base_xbridge_conf

        if self.blocknet_xbridge_conf_remote is None:
            logging.error("Remote xbridge.conf not available.")
            return False

        if self.xbridge_conf_local is None:
            logging.error("Local xbridge.conf not available.")
            return False
        # section = 'global'
        if xlite_daemon_conf:
            # XLITE SESSION DETECTED, USE XLITE RPC PARAMS
            for coin in xlite_daemon_conf:
                if coin == "master":
                    continue
                self.retrieve_coin_conf(coin)
                if coin in self.parsed_xbridge_confs:
                    if coin not in self.xbridge_conf_local:
                        self.xbridge_conf_local[coin] = {}
                    # logging.warning(self.parsed_xbridge_confs[coin])
                    for section, options in self.parsed_xbridge_confs[coin].items():
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
                                    # logging.warning(f"value: {value}")
                                    # exit()
                                    self.xbridge_conf_local[section][key] = str(value)

        if not (xlite_daemon_conf and "BLOCK" in xlite_daemon_conf):
            # NO XLITE SESSION DETECTED, SET XBRIDGE TO USE BLOCKNET CORE RPC
            for section, options in self.blocknet_xbridge_conf_remote.items():
                if section not in self.xbridge_conf_local:
                    self.xbridge_conf_local[section] = {}
                logging.info(f"section: {section}, options: {options}")
                for key, value in options.items():
                    if key == 'Username':
                        self.xbridge_conf_local[section][key] = str(self.blocknet_conf_local['global']['rpcuser'])
                    elif key == 'Password':
                        self.xbridge_conf_local[section][key] = str(self.blocknet_conf_local['global']['rpcpassword'])
                    elif key == 'Port':
                        self.xbridge_conf_local[section][key] = str(self.blocknet_conf_local['global']['rpcport'])
                    else:
                        if key not in self.xbridge_conf_local[section] or self.xbridge_conf_local[section][
                            key] != value:
                            self.xbridge_conf_local[section][key] = str(value)

        # Prepare the string of sections (excluding 'Main')
        sections_string = ','.join(section for section in self.xbridge_conf_local.keys() if section != 'Main')

        # Update the 'ExchangeWallets' value with the sections string
        if 'Main' in self.xbridge_conf_local:
            self.xbridge_conf_local['Main']['ExchangeWallets'] = sections_string
        else:
            self.xbridge_conf_local['Main'] = {
                'ExchangeWallets': sections_string,
                'FullLog': global_variables.conf_data.base_xbridge_conf['FullLog'],
                'ShowAllOrders': global_variables.conf_data.base_xbridge_conf['ShowAllOrders'],
            }

        new_local_json = json.dumps(self.xbridge_conf_local, sort_keys=True)
        if old_local_json != new_local_json:
            logging.info("Local xbridge.conf has been updated. Saving...")
            self.save_xbridge_conf()
            return True
        else:
            logging.info("Local xbridge.conf remains the same. No need to save.")
            return False

    def compare_and_update_local_conf(self, xlite_daemon_conf=None):
        self.check_blocknet_conf()
        self.check_xbridge_conf(xlite_daemon_conf)

    def create_data_folder(self):
        if self.data_folder and not os.path.exists(self.data_folder):
            os.makedirs(self.data_folder)

    def create_aio_folder(self):
        if global_variables.aio_folder and not os.path.exists(global_variables.aio_folder):
            os.makedirs(global_variables.aio_folder)

    def download_bootstrap(self):
        self.create_data_folder()
        self.create_aio_folder()

        self.bootstrap_checking = True
        filename = "Blocknet.zip"
        local_file_path = os.path.join(global_variables.aio_folder, filename)
        remote_file_size = get_remote_file_size(global_variables.conf_data.blocknet_bootstrap_url)
        # Check if the file already exists on disk
        need_to_download = True
        if os.path.exists(local_file_path):
            # Compare the size of the local file with the remote file
            local_file_size = os.path.getsize(local_file_path)

            if local_file_size == remote_file_size:
                logging.info("Bootstrap file already exists on disk and matches the remote file.")
                need_to_download = False
            else:
                logging.info("Local bootstrap file exists but does not match the remote file. Re-downloading...")
                os.remove(local_file_path)  # Remove the local file and proceed with download
        try:
            if need_to_download:
                with open(local_file_path, 'wb') as f:
                    # Set timeout values in seconds
                    connection_timeout = 10
                    read_timeout = 30
                    response = requests.get(global_variables.conf_data.blocknet_bootstrap_url, stream=True,
                                            timeout=(connection_timeout, read_timeout))
                    response.raise_for_status()
                    if response.status_code == 200:
                        try:
                            logging.info(
                                f"Downloading {global_variables.conf_data.blocknet_bootstrap_url} to {local_file_path}, remote size: {int(remote_file_size / 1024)} kb")
                            bytes_downloaded = 0
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    bytes_downloaded += len(chunk)
                                    self.bootstrap_percent_download = (bytes_downloaded / remote_file_size) * 100
                        except requests.exceptions.RequestException as e:
                            logging.error(f"Error occurred during download: {str(e)}")
                    else:
                        logging.error("Failed to download the Blocknet Bootstrap.")

                self.bootstrap_percent_download = None

                if os.path.getsize(local_file_path) != remote_file_size:
                    os.remove(local_file_path)
                    raise ValueError(f"Downloaded {filename} file size doesn't match the expected size. Deleting it")

                logging.info(f"{filename} Bootstrap downloaded successfully.")

            to_delete = ['blocks', 'chainstate', 'indexes', 'peers.dat', 'banlist.dat']
            for item_name in to_delete:
                item_path = os.path.join(self.data_folder, item_name)
                if os.path.exists(item_path):
                    if os.path.isdir(item_path):
                        logging.info(f"Deleting existing folder: {item_name}...")
                        shutil.rmtree(item_path)
                        logging.info(f"{item_name} folder deleted successfully.")
                    else:
                        logging.info(f"Deleting existing file: {item_name}...")
                        os.remove(item_path)
                        logging.info(f"{item_name} deleted successfully.")
            logging.info("Extracting bootstrap...")
            with zipfile.ZipFile(local_file_path, "r") as zip_ref:
                self.bootstrap_extracting = True
                zip_ref.extractall(self.data_folder)
            self.bootstrap_extracting = False
            logging.info("Extraction completed.")

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            self.bootstrap_percent_download = None
        finally:
            self.bootstrap_checking = False

    def download_blocknet_bin(self):
        self.downloading_bin = True
        url = global_variables.conf_data.blocknet_releases_urls.get((global_variables.system, global_variables.machine))
        if url is None:
            raise ValueError(f"Unsupported OS or architecture {global_variables.system} {global_variables.machine}")

        # Set timeout values in seconds
        connection_timeout = 10
        read_timeout = 30
        response = requests.get(url, stream=True, timeout=(connection_timeout, read_timeout))
        response.raise_for_status()
        if response.status_code == 200:
            local_file_path = os.path.join(global_variables.aio_folder, os.path.basename(url))
            try:
                remote_file_size = int(response.headers.get('Content-Length', 0))
                logging.info(f"Downloading {url} to {local_file_path}, remote size: {int(remote_file_size / 1024)} kb")
                bytes_downloaded = 0
                with open(local_file_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):  # Iterate over response content in chunks
                        if chunk:  # Filter out keep-alive new chunks
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
                            self.binary_percent_download = (bytes_downloaded / remote_file_size) * 100
            except requests.exceptions.RequestException as e:
                logging.error(f"Error occurred during download: {str(e)}")

            self.binary_percent_download = None

            if os.path.getsize(local_file_path) != remote_file_size:
                os.remove(local_file_path)
                raise ValueError(
                    f"Downloaded {os.path.basename(url)} size doesn't match the expected size. Deleting it")

            logging.info(f"{os.path.basename(url)} downloaded successfully.")

            if url.endswith(".zip"):
                with zipfile.ZipFile(local_file_path, "r") as zip_ref:
                    zip_ref.extractall(global_variables.aio_folder)
                logging.info("Zip file extracted successfully.")
                os.remove(local_file_path)
            elif url.endswith(".tar.gz"):
                with tarfile.open(local_file_path, "r:gz") as tar:
                    tar.extractall(global_variables.aio_folder)
                logging.info("Tar.gz file extracted successfully.")
                os.remove(local_file_path)
        else:
            print("Failed to download the Blocknet binary.")
        self.downloading_bin = False


def get_remote_file_size(url):
    """
    Fetches the size of a remote file specified by its URL.
    """
    r = requests.head(url)
    r.raise_for_status()
    return int(r.headers.get('content-length', 0))


def get_pid(name):
    return map(int, check_output(["pidof", name]).split())


def get_blocknet_data_folder(custom_path=None):
    if custom_path:
        path = custom_path
    else:
        path = global_variables.conf_data.blocknet_default_paths.get(global_variables.system)
    if path:
        expanded_path = os.path.expandvars(os.path.expanduser(path))
        # logging.info(f"\n path {norm_path} \n")
        return os.path.normpath(expanded_path)  # Normalize path separators
    else:
        logging.error(f"invalid blocknet data folder path: {path}")


def generate_random_string(length):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def save_conf_to_file(conf_data, file_path):
    try:
        # Create missing directories if needed
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            for section, options in conf_data.items():
                if section != 'global':
                    f.write(f"[{section}]\n")
                for key, value in options.items():
                    if key == "addnode":
                        for node in value:
                            f.write(f"addnode={node}\n")
                    else:
                        f.write(f"{key}={value}\n")

        logging.info(f"Configuration data saved to {file_path} successfully")
        return True
    except Exception as e:
        logging.error(f"Error saving configuration data to {file_path}: {e}")
        return False


def retrieve_remote_conf(remote_url, subfolder, expected_filename):
    folder = "xb_conf"
    local_conf_file = os.path.join(global_variables.aio_folder, folder, subfolder, expected_filename)

    if os.path.exists(local_conf_file):
        try:
            with open(local_conf_file, 'r') as f:
                conf_data = f.read()
            parsed_conf = parse_conf_file(input_string=conf_data)
            if parsed_conf:
                logging.info(f"REMOTE: found and parsed ok: [{local_conf_file}]")
                return parsed_conf
            else:
                logging.error(f"Failed to parse: {local_conf_file}")
        except Exception as e:
            logging.error(f"{local_conf_file} Error opening or parsing file: {e}")

    return download_remote_conf(remote_url, local_conf_file)


def download_remote_conf(url, filepath):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            conf_data = response.text
            parsed_conf = parse_conf_file(input_string=conf_data)
            if parsed_conf:
                # Save the remote configuration to a local file
                save_conf_to_file(parsed_conf, filepath)
                logging.info(f"retrieved and parsed ok: [{filepath}]")
                return parsed_conf
            else:
                logging.error(f"Failed to parse {filepath} ")
                return None
        else:
            logging.error(
                f"Failed to retrieve remote blocknet configuration file: {url} {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error retrieving remote blocknet configuration file: {e}")
        return None


def retrieve_xb_manifest():
    # remote_manifest_url
    folder = "xb_conf"
    filename = os.path.basename(global_variables.conf_data.remote_manifest_url)
    local_manifest_file = os.path.join(global_variables.aio_folder, folder, filename)

    # if os.path.exists(local_manifest_file):
    #     try:
    #         with open(local_manifest_file, 'r') as f:
    #             json_data = f.read()
    #         parsed_json = json.loads(json_data)
    #         logging.info(f"REMOTE: Found and parsed successfully: {local_manifest_file}")
    #         return parsed_json
    #     except Exception as e:
    #         logging.error(f"{local_manifest_file} Error opening or parsing file: {e}")

    try:
        response = requests.get(global_variables.conf_data.remote_manifest_url)
        if response.status_code == 200:
            parsed_json = response.json()
            os.makedirs(os.path.dirname(local_manifest_file), exist_ok=True)
            with open(local_manifest_file, 'w') as f:
                f.write(json.dumps(parsed_json, indent=4))  # Save the JSON data to local file
            logging.info(f"REMOTE: Retrieved and parsed ok: [{local_manifest_file}]")
            return parsed_json
        else:
            logging.error(
                f"Failed to retrieve remote configuration file: {global_variables.conf_data.remote_manifest_url} {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error retrieving remote configuration file: {e}")
        return None


def retrieve_remote_blocknet_conf():
    filename = os.path.basename(global_variables.conf_data.remote_blocknet_conf_url)
    return retrieve_remote_conf(global_variables.conf_data.remote_blocknet_conf_url, "wallet-confs", filename)


def retrieve_remote_blocknet_xbridge_conf():
    filename = os.path.basename(global_variables.conf_data.remote_xbridge_conf_url)
    return retrieve_remote_conf(global_variables.conf_data.remote_xbridge_conf_url, "xbridge-confs", filename)


def parse_conf_file(file_path=None, input_string=None):
    conf_data = {}
    current_section = 'global'  # Set a default section

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
                conf_data.setdefault(current_section.strip('[]'), {})
                key, value = line.split('=', 1)
                conf_data[current_section.strip('[]')][key.strip()] = value.strip()
            else:
                current_section = line.strip()
                conf_data.setdefault(current_section.strip('[]'), {})

    return conf_data

# if __name__ == "__main__":
#     a = BlocknetUtility()
#     a.retrieve_coin_conf('BTC')
