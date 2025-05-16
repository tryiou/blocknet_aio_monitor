import json
import logging
import os
from threading import enumerate, current_thread

import customtkinter as ctk
import requests
from cryptography.fernet import Fernet

from utilities import global_variables


def configure_tooltip_text(tooltip, msg):
    if tooltip.get() != msg:
        tooltip.configure(message=msg)


def load_cfg_json():
    local_filename = "cfg.json"
    local_conf_path = global_variables.aio_blocknet_data_path.get(global_variables.system)
    filename = os.path.join(os.path.expandvars(os.path.expanduser(local_conf_path)), local_filename)

    # Check if the file exists
    if os.path.exists(filename):
        with open(filename, 'r') as file:
            cfg_data = json.load(file)
        logging.info(f"Configuration file '{filename}' loaded.")
        return cfg_data
    else:
        logging.info(f"Configuration file '{filename}' not found.")
        return None


def terminate_all_threads():
    logging.info("Terminating all threads...")
    for thread in enumerate():
        if thread != current_thread():
            # logging.info(f"Terminating thread: {thread.name}")
            thread.join(timeout=0.25)  # Terminate thread
            logging.info(f"Thread {thread.name} terminated")


def remove_cfg_json_key(key):
    local_filename = "cfg.json"
    local_conf_path = global_variables.aio_blocknet_data_path.get(global_variables.system)
    filename = os.path.join(os.path.expandvars(os.path.expanduser(local_conf_path)), local_filename)

    # Try loading the existing JSON file
    try:
        with open(filename, 'r') as file:
            cfg_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error(f"Failed to load JSON file: {filename}")
        return

    # Check if the key exists in the dictionary
    if key in cfg_data:
        # Remove the key from the dictionary
        del cfg_data[key]
        with open(filename, 'w') as file:
            json.dump(cfg_data, file)
        logging.info(f"Key '{key}' was removed from configuration file: {filename}")
    else:
        logging.warning(f"Key '{key}' not found in configuration file: {filename}")


def save_cfg_json(key, data):
    local_filename = "cfg.json"
    local_conf_path = global_variables.aio_blocknet_data_path.get(global_variables.system)
    filename = os.path.join(os.path.expandvars(os.path.expanduser(local_conf_path)), local_filename)

    # Try loading the existing JSON file
    try:
        with open(filename, 'r') as file:
            cfg_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        # If file doesn't exist or JSON decoding error occurs, create a new empty dictionary
        cfg_data = {}

    # Update the data with the new key-value pair
    cfg_data[key] = data

    # Save to file
    with open(filename, 'w') as file:
        json.dump(cfg_data, file)
    logging.info(f"{key} {data} was saved to configuration file: {filename}")


def generate_key():
    """Generate a new encryption key."""
    return Fernet.generate_key()


def encrypt_password(password, key):
    """Encrypt the password using the provided key."""
    cipher_suite = Fernet(key)
    encrypted_password = cipher_suite.encrypt(password.encode())
    return encrypted_password.decode()


def decrypt_password(encrypted_password, key):
    """Decrypt the encrypted password using the provided key."""
    cipher_suite = Fernet(key)
    decrypted_password = cipher_suite.decrypt(encrypted_password.encode())
    return decrypted_password.decode()


def enable_button(button, img=None):
    if button.cget("state") == ctk.DISABLED:
        button.configure(state=ctk.NORMAL)
    if img:
        button.configure(image=img)


def disable_button(button, img=None):
    if button.cget("state") == ctk.NORMAL:
        button.configure(state=ctk.DISABLED)
    if img:
        button.configure(image=img)


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
        logging.debug(f"RPC request successful. Response: {json}")
        if 'result' in json_answer:
            return json_answer['result']
        else:
            logging.error(f"No result in json: {json_answer}")
    except requests.RequestException as e:
        logging.error(f"Error sending RPC request: {e}")
        return None
    except Exception as ex:
        logging.exception(f"An unexpected error occurred while sending RPC request: {ex}")
        return None