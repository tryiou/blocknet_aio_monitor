import asyncio
import shutil
import threading
import logging
import subprocess
import os
import platform

import psutil
import requests
import random
import string
import json
import io
import zipfile
import tarfile
from subprocess import check_output

from conf_data import remote_blocknet_conf_url, aio_blocknet_data_path, blocknet_default_paths, base_xbridge_conf, \
    blocknet_bin_name, blocknet_bin_path, blocknet_releases_urls, blocknet_bootstrap_url

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Disable log entries from the urllib3 module (used by requests)
urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.WARNING)

system = platform.system()
machine = platform.machine()
blocknet_bin = blocknet_bin_name.get(system, None)
aio_data_path = os.path.expandvars(os.path.expanduser(aio_blocknet_data_path.get(system)))


class BlocknetRPCClient:
    def __init__(self, rpc_user, rpc_password, rpc_port):
        self.rpc_user = rpc_user
        self.rpc_password = rpc_password
        self.rpc_port = rpc_port

    def send_rpc_request(self, method, params=None):
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
        self.checking_bootstrap = False
        self.bootstrap_percent_download = None
        self.downloading_bin = False
        self.data_folder = get_blocknet_data_folder(custom_path)
        self.process_running = None
        self.blocknet_conf_local = None
        self.xbridge_conf_local = None
        self.blocknet_conf_remote = retrieve_remote_blocknet_conf()
        self.xbridge_conf_remote = retrieve_remote_xbridge_conf()
        self.blocknet_pids = []
        self.blocknet_process = None
        self.blocknet_rpc = None
        self.valid_rpc = False
        self.running = True  # flag for async funcs
        self.parse_blocknet_conf()
        self.parse_xbridge_conf()
        self.init_blocknet_rpc()
        self.start_async_tasks()

    def start_async_tasks(self):
        def async_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(
                asyncio.gather(self.check_blocknet_rpc()))  # self.check_blocknet_process(),
            loop.close()

        thread = threading.Thread(target=async_loop)
        thread.start()

    async def check_blocknet_rpc(self):
        while self.running:
            if self.blocknet_rpc:
                result = self.blocknet_rpc.send_rpc_request('getnetworkinfo')
                if result:
                    self.valid_rpc = True
                else:
                    self.valid_rpc = False
            else:
                self.valid_rpc = False
                # logging.error("Blocknet RPC client is not initialized.")
            # logging.debug(f"valid_rpc: {self.valid_rpc}")
            await asyncio.sleep(1)

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

    def start_blocknet(self, retry_limit=3, retry_count=0):
        if retry_count >= retry_limit:
            logging.error("Retry limit exceeded. Unable to start Blocknet.")
            return
        blocknet_exe = os.path.join(aio_data_path, *blocknet_bin_path, blocknet_bin)

        if not os.path.exists(blocknet_exe):
            self.downloading_bin = True
            logging.info(f"Blocknet executable not found at {blocknet_exe}. Downloading...")
            download_blocknet_bin()
            self.downloading_bin = False
        try:
            # Start the Blocknet process using subprocess with custom data folder argument
            self.blocknet_process = subprocess.Popen([blocknet_exe, f"-datadir={self.data_folder}"],
                                                     stdout=subprocess.PIPE,
                                                     stderr=subprocess.PIPE,
                                                     stdin=subprocess.PIPE,
                                                     start_new_session=True)
            logging.info(f"Started Blocknet process: {blocknet_exe} with data directory: {self.data_folder}")
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
            logging.info(f"BLOCKNET: Parsed {conf_file_path} file successfully: {self.blocknet_conf_local}")
        else:
            self.blocknet_conf_local = {}
            logging.warning(f"{conf_file_path} file does not exist.")

    def parse_xbridge_conf(self):
        conf_file_path = os.path.join(self.data_folder, "xbridge.conf")
        if os.path.exists(conf_file_path):
            self.xbridge_conf_local = parse_conf_file(file_path=conf_file_path)
            logging.info(f"BLOCKNET: Parsed {conf_file_path} file successfully: {self.xbridge_conf_local}")
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

        for section, options in self.blocknet_conf_remote.items():
            if section not in self.blocknet_conf_local:
                self.blocknet_conf_local[section] = {}

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
                    if key not in self.blocknet_conf_local[section] or self.blocknet_conf_local[section][key] != value:
                        self.blocknet_conf_local[section][key] = value
                        # logging.debug(f"Updated {key} value: {value}")

        logging.info("Local blocknet.conf updated successfully.")

        new_local_json = json.dumps(self.blocknet_conf_local, sort_keys=True)

        # logging.info(f"Old local configuration:\n{old_local_json}")
        # logging.info(f"Updated local configuration:\n{new_local_json}")

        if old_local_json != new_local_json:
            logging.info("Local blocknet.conf has been updated. Saving...")
            self.save_blocknet_conf()
            self.init_blocknet_rpc()
            return True
        else:
            logging.info("Local blocknet.conf remains the same. No need to save.")
            return False

    def check_xbridge_conf(self):
        self.parse_xbridge_conf()
        logging.info(f"Current local configuration:\n{self.xbridge_conf_local}")
        # logging.info(f"Current remote configuration:\n{self.xbridge_conf_remote}")

        old_local_json = json.dumps(self.xbridge_conf_local, sort_keys=True)

        if 'Main' not in self.xbridge_conf_local:
            # We want this on 'top' of file, add it if missing

            self.xbridge_conf_local['Main'] = base_xbridge_conf

        if self.xbridge_conf_remote is None:
            logging.error("Remote xbridge.conf not available.")
            return False

        if self.xbridge_conf_local is None:
            logging.error("Local xbridge.conf not available.")
            return False

        for section, options in self.xbridge_conf_remote.items():
            if section not in self.xbridge_conf_local:
                self.xbridge_conf_local[section] = {}

            for key, value in options.items():
                if key == 'Username':
                    self.xbridge_conf_local[section][key] = self.blocknet_conf_local['global']['rpcuser']
                elif key == 'Password':
                    self.xbridge_conf_local[section][key] = self.blocknet_conf_local['global']['rpcpassword']
                else:
                    if key not in self.xbridge_conf_local[section] or self.xbridge_conf_local[section][key] != value:
                        self.xbridge_conf_local[section][key] = value

        # Prepare the string of sections (excluding 'Main')
        sections_string = ','.join(section for section in self.xbridge_conf_local.keys() if section != 'Main')

        # Update the 'ExchangeWallets' value with the sections string
        if 'Main' in self.xbridge_conf_local:
            self.xbridge_conf_local['Main']['ExchangeWallets'] = sections_string
        else:
            self.xbridge_conf_local['Main'] = {
                'ExchangeWallets': sections_string,
                'FullLog': base_xbridge_conf['FullLog'],
                'ShowAllOrders': base_xbridge_conf['ShowAllOrders'],
            }

        logging.info("Local xbridge.conf updated successfully.")

        new_local_json = json.dumps(self.xbridge_conf_local, sort_keys=True)

        # logging.info(f"Old local xbridge.conf:\n{old_local_json}")
        # logging.info(f"Updated local xbridge.conf:\n{new_local_json}")

        if old_local_json != new_local_json:
            logging.info("Local xbridge.conf has been updated. Saving...")
            self.save_xbridge_conf()
            return True
        else:
            logging.info("Local xbridge.conf remains the same. No need to save.")
            return False

    def compare_and_update_local_conf(self):
        self.check_blocknet_conf()
        self.check_xbridge_conf()

    def download_bootstrap(self):
        if not self.data_folder:
            logging.error("No valid data folder provided to install bootstrap")
            return None
        if not aio_data_path:
            logging.error("No path provided for temporary storage")
            return None

        self.checking_bootstrap = True
        filename = "Blocknet.zip"
        temp_file_path = os.path.join(aio_data_path, filename)
        remote_file_size = get_remote_file_size(blocknet_bootstrap_url)
        # Check if the file already exists on disk
        need_to_download = True
        if os.path.exists(temp_file_path):
            # Compare the size of the local file with the remote file
            local_file_size = os.path.getsize(temp_file_path)
            print(local_file_size)

            if local_file_size == remote_file_size:
                logging.info("Bootstrap file already exists on disk and matches the remote file.")
                need_to_download = False
            else:
                logging.info("Local bootstrap file exists but does not match the remote file. Re-downloading...")
                os.remove(temp_file_path)  # Remove the local file and proceed with download

        try:
            if need_to_download:
                logging.info("Downloading Blocknet bootstrap...")
                with open(temp_file_path, 'wb') as f:

                    r = requests.get(blocknet_bootstrap_url, stream=True)
                    r.raise_for_status()
                    bytes_downloaded = 0
                    total = remote_file_size
                    for chunk in r.iter_content(chunk_size=8192 * 2):
                        if chunk:
                            f.write(chunk)
                            bytes_downloaded += len(chunk)
                            self.bootstrap_percent_download = (bytes_downloaded / total) * 100
                self.bootstrap_percent_download = None
                local_file_size = os.path.getsize(temp_file_path)
                if local_file_size != remote_file_size:
                    raise ValueError("Downloaded bootstrap file size doesn't match the expected size.")
                logging.info("Bootstrap downloaded successfully.")

            folders_to_check = ['blocks', 'chainstate', 'indexes']
            for folder_name in folders_to_check:
                folder_path = os.path.join(self.data_folder, folder_name)
                if os.path.exists(folder_path) and os.path.isdir(folder_path):
                    logging.info(f"Deleting existing {folder_name} folder...")
                    shutil.rmtree(folder_path)
                    logging.info(f"{folder_name} folder deleted successfully.")

            logging.info("Extracting bootstrap...")
            with zipfile.ZipFile(temp_file_path, "r") as zip_ref:
                zip_ref.extractall(self.data_folder)
            logging.info("Extraction completed.")

        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            self.bootstrap_percent_download = None
        finally:
            self.checking_bootstrap = False


def get_remote_file_size(url):
    """
    Fetches the size of a remote file specified by its URL.
    """
    r = requests.head(url)
    r.raise_for_status()
    return int(r.headers.get('content-length', 0))


def download_blocknet_bin():
    url = blocknet_releases_urls.get((system, machine))
    if url is None:
        raise ValueError(f"Unsupported OS or architecture {system} {machine}")

    response = requests.get(url)
    if response.status_code == 200:
        # Extract the archive from memory
        if url.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(response.content), "r") as zip_ref:
                zip_ref.extractall(aio_data_path)
        elif url.endswith(".tar.gz"):
            with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tar:
                tar.extractall(aio_data_path)
        else:
            print("Unsupported archive format.")
    else:
        print("Failed to download the Blocknet binary.")


def get_pid(name):
    return map(int, check_output(["pidof", name]).split())


def get_blocknet_data_folder(custom_path=None):
    if custom_path:
        path = custom_path
    else:
        path = blocknet_default_paths.get(system)
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
                    f.write(f"{key}={value}\n")
        logging.info(f"Configuration data saved to {file_path} successfully")
        return True
    except Exception as e:
        logging.error(f"Error saving configuration data to {file_path}: {e}")
        return False


def retrieve_remote_blocknet_conf():
    filename = "remote_blocknet.conf"
    local_conf_file = os.path.join(aio_data_path, filename)
    # Check if the local configuration file exists
    if os.path.exists(local_conf_file):
        # Try to open and parse the local configuration file
        try:
            with open(local_conf_file, 'r') as f:
                conf_data = f.read()
            parsed_conf = parse_conf_file(input_string=conf_data)
            if parsed_conf:
                logging.info(f"REMOTE: found and parsed successfully: {local_conf_file}")
                return parsed_conf
            else:
                logging.error(f"Failed to parse: {local_conf_file}")
                # If parsing fails, proceed to retrieve remote configuration
        except Exception as e:
            logging.error(f"{local_conf_file} Error opening or parsing file: {e}")
            # If opening or parsing fails, proceed to retrieve remote configuration

    # If local configuration retrieval fails or the local file does not exist,
    # retrieve the remote configuration from GitHub
    try:
        response = requests.get(remote_blocknet_conf_url)
        if response.status_code == 200:
            conf_data = response.text
            parsed_conf = parse_conf_file(input_string=conf_data)
            if parsed_conf:
                # Save the remote configuration to a local file
                save_conf_to_file(parsed_conf, local_conf_file)
                logging.info(f"retrieved and parsed successfully: {local_conf_file} ")
                return parsed_conf
            else:
                logging.error(f"Failed to parse: {local_conf_file} ")
                return None
        else:
            logging.error(
                f"Failed to retrieve remote blocknet configuration file: {remote_blocknet_conf_url} {response.status_code}")
            return None
    except requests.RequestException as e:
        logging.error(f"Error retrieving remote blocknet configuration file: {e}")
        return None


def retrieve_remote_xbridge_conf():
    from conf_data import remote_xbridge_conf_url
    filename = "remote_xbridge.conf"
    local_conf_file = os.path.join(aio_data_path, filename)
    # Check if the local configuration file exists
    if os.path.exists(local_conf_file):
        # Try to open and parse the local configuration file
        try:
            with open(local_conf_file, 'r') as f:
                conf_data = f.read()
            parsed_conf = parse_conf_file(input_string=conf_data)
            if parsed_conf:
                logging.info(f"REMOTE: Found and parsed successfully: {local_conf_file} ")
                return parsed_conf
            else:
                logging.error(f"Failed to parse {local_conf_file} ")
                # If parsing fails, proceed to retrieve remote configuration
        except Exception as e:
            logging.error(f"{local_conf_file} Error opening or parsing file: {e}")
            # If opening or parsing fails, proceed to retrieve remote configuration

    # If local configuration retrieval fails or the local file does not exist,
    # retrieve the remote configuration from GitHub
    try:
        response = requests.get(remote_xbridge_conf_url)
        if response.status_code == 200:
            conf_data = response.text
            parsed_conf = parse_conf_file(input_string=conf_data)
            if parsed_conf:
                # Save the remote configuration to a local file
                save_conf_to_file(parsed_conf, local_conf_file)
                logging.info(f"REMOTE: retrieved and parsed successfully: {local_conf_file} ")
                return parsed_conf
            else:
                logging.error(f"Failed to parse remote file: {local_conf_file}")
                return None
        else:
            logging.error(
                f"Failed to retrieve remote xbridge configuration file: {remote_xbridge_conf_url} {response.status_code}")
            return None
    except requests.RequestException as e:
        logging.error(f"Error retrieving remote xbridge configuration file: {e}")
        return None


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


if __name__ == "__main__":
    a = BlocknetUtility()
    a.download_bootstrap()
