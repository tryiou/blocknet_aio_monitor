import json
import logging
import os
from threading import enumerate, current_thread

import customtkinter as ctk
import psutil
from cryptography.fernet import Fernet

from utilities import global_variables


def configure_tooltip_text(tooltip, msg):
    if tooltip.get() != msg:
        tooltip.configure(message=msg)


def load_cfg_json():
    local_filename = "cfg.json"
    local_conf_path = global_variables.aio_folder
    filename = os.path.join(os.path.expandvars(os.path.expanduser(local_conf_path)), local_filename)

    # Check if the file exists
    if os.path.exists(filename):
        with open(filename, 'r') as file:
            cfg_data = json.load(file)
        logging.info(f"Configuration file loaded ok: [{filename}]")
        return cfg_data
    else:
        logging.info(f"Configuration file not found: [{filename}]")
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
    local_conf_path = global_variables.conf_data.aio_blocknet_data_path.get(global_variables.system)
    filename = os.path.join(os.path.expandvars(os.path.expanduser(local_conf_path)), local_filename)

    # Try loading the existing JSON file
    try:
        with open(filename, 'r') as file:
            cfg_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.error(f"Failed to load JSON file: [{filename}]")
        return

    # Check if the key exists in the dictionary
    if key in cfg_data:
        # Remove the key from the dictionary
        del cfg_data[key]
        with open(filename, 'w') as file:
            json.dump(cfg_data, file)
        logging.info(f"Key '{key}' was removed from configuration file: [{filename}]")
    else:
        logging.warning(f"Key '{key}' not found in configuration file: [{filename}]")


def save_cfg_json(key, data):
    local_filename = "cfg.json"
    local_conf_path = global_variables.conf_data.aio_blocknet_data_path.get(global_variables.system)
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
    logging.info(f"{key} {data} was saved to configuration file: [{filename}]")


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


def processes_check():
    """Check for running processes related to Blocknet, BlockDX, and Xlite."""

    # Initialize process lists
    process_lists: dict = {
        global_variables.blocknet_bin: [],
        global_variables.blockdx_bin: [],
        global_variables.xlite_bin: [],
        global_variables.xlite_daemon_bin: []
    }

    # Process all running processes
    for proc in psutil.process_iter(['pid', 'name', 'status']):
        pid = proc.info['pid']
        name = proc.info['name']
        status = proc.info['status']

        # Check against each target process type
        for target_name, process_list in process_lists.items():
            result_pid = handle_process(pid, name, status, target_name)
            if result_pid is not None:
                process_list.append(result_pid)
                break  # Process matched, no need to check other types

    return (
        process_lists[global_variables.blocknet_bin],
        process_lists[global_variables.blockdx_bin],
        process_lists[global_variables.xlite_bin],
        process_lists[global_variables.xlite_daemon_bin]
    )


def handle_process(pid, name, status, target_name):
    """Helper function to handle individual process logic."""
    if name == target_name:
        if status == "zombie":
            # the app was closed by user manually, clean zombie process
            process = psutil.Process(pid)
            process.wait()
            return None  # Don't add zombie processes to the list
        else:
            return pid
    return None
