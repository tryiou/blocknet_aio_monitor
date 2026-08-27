import json
import logging
import os
from threading import current_thread, enumerate

import customtkinter as ctk
import psutil
from cryptography.fernet import Fernet

from utilities.app_container import get_container
from utilities.keyring_manager import KeyringManager, KeyringMigration

logger = logging.getLogger(__name__)


def configure_tooltip_text(tooltip, msg):
    if tooltip.get() != msg:
        tooltip.configure(message=msg)


def load_cfg_json():
    local_filename = "aio_settings.json"
    old_local_filename = "cfg.json"

    container = get_container()
    local_conf_path = container.aio_folder  # define this early
    full_old_path = os.path.join(os.path.expandvars(os.path.expanduser(local_conf_path)), old_local_filename)
    full_new_path = os.path.join(os.path.expandvars(os.path.expanduser(local_conf_path)), local_filename)

    if os.path.exists(full_old_path):
        # migrate old config file
        logger.info(f"Renaming {full_old_path} to {full_new_path}")
        os.rename(full_old_path, full_new_path)

    # Check if the file exists
    if os.path.exists(full_new_path):
        with open(full_new_path) as file:
            cfg_data = json.load(file)

        # Check if migration from old format (with salt) is needed
        if cfg_data and "salt" in cfg_data:
            logger.info("Detected old format with salt key. Starting migration to keyring...")
            keyring_manager = KeyringManager(local_conf_path)
            migration = KeyringMigration(local_conf_path, keyring_manager)

            success, new_cfg_data, message, old_key = migration.migrate_from_old_format(cfg_data)
            if success:
                # Save the migrated config (may or may not include salt depending on keyring availability)
                with open(full_new_path, "w") as file:
                    json.dump(new_cfg_data, file, indent=2)
                logger.info(f"Migration successful: {message}")
                cfg_data = new_cfg_data
            else:
                logger.error(f"Migration failed: {message}")

        logger.info(f"Configuration file loaded ok: [{full_new_path}]")
        return cfg_data
    else:
        logger.info(f"Configuration file not found: [{full_new_path}]")
        return None


def terminate_all_threads():
    logger.info("Terminating all threads...")
    for thread in enumerate():
        if thread != current_thread():
            # logger.info(f"Terminating thread: {thread.name}")
            thread.join(timeout=0.25)  # Terminate thread
            logger.info(f"Thread {thread.name} terminated")


def remove_cfg_json_key(key):
    container = get_container()
    local_filename = "aio_settings.json"
    local_conf_path = container.conf_data.aio_blocknet_data_path.get(container.system)
    filename = os.path.join(os.path.expandvars(os.path.expanduser(local_conf_path)), local_filename)

    # Try loading the existing JSON file
    try:
        with open(filename) as file:
            cfg_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.error(f"Failed to load JSON file: [{filename}]")
        return

    # Check if the key exists in the dictionary
    if key in cfg_data:
        # Remove the key from the dictionary
        del cfg_data[key]
        with open(filename, "w") as file:
            json.dump(cfg_data, file)
        logger.info(f"Key '{key}' was removed from configuration file: [{filename}]")

        # If removing password-related keys, also delete encryption key from keyring
        if key in ["salt", "xl_pass"]:
            delete_encryption_key()
    else:
        logger.warning(f"Key '{key}' not found in configuration file: [{filename}]")


def save_cfg_json(key, data):
    container = get_container()
    local_filename = "aio_settings.json"
    local_conf_path = container.conf_data.aio_blocknet_data_path.get(container.system)
    filename = os.path.join(os.path.expandvars(os.path.expanduser(local_conf_path)), local_filename)

    # Try loading the existing JSON file
    try:
        with open(filename) as file:
            cfg_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        # If file doesn't exist or JSON decoding error occurs, create a new empty dictionary
        cfg_data = {}

    cfg_data.update({key: data})

    # Save to file
    with open(filename, "w") as file:
        json.dump(cfg_data, file)
    logger.info(f"{key} {data} was saved to configuration file: [{filename}]")


def save_encryption_key(key):
    """Save encryption key to keyring (or fallback storage)."""
    container = get_container()
    local_conf_path = container.conf_data.aio_blocknet_data_path.get(container.system)
    keyring_manager = KeyringManager(local_conf_path)
    success, message = keyring_manager.store_key(key)
    if success:
        logger.info(f"Encryption key saved: {message}")
    else:
        logger.error(f"Failed to save encryption key: {message}")
    return success


def load_encryption_key():
    """Load encryption key from keyring (or fallback storage)."""
    container = get_container()
    local_conf_path = container.conf_data.aio_blocknet_data_path.get(container.system)
    keyring_manager = KeyringManager(local_conf_path)
    key, message = keyring_manager.retrieve_key()
    if key:
        logger.info(f"Encryption key loaded: {message}")
        return key.encode("utf-8") if isinstance(key, str) else key
    else:
        logger.error(f"Failed to load encryption key: {message}")
        return None


def delete_encryption_key():
    """Delete encryption key from keyring and fallback storage."""
    container = get_container()
    local_conf_path = container.conf_data.aio_blocknet_data_path.get(container.system)
    keyring_manager = KeyringManager(local_conf_path)
    success, message = keyring_manager.delete_key()
    if success:
        logger.info(f"Encryption key deleted: {message}")
    else:
        logger.error(f"Failed to delete encryption key: {message}")
    return success


def generate_key():
    """Generate a new encryption key and store it in keyring."""
    key = Fernet.generate_key()
    # Store the key in keyring
    if save_encryption_key(key.decode("utf-8")):
        return key
    else:
        logger.error("Failed to store encryption key in keyring")
        return None


def encrypt_password(password, key=None):
    """Encrypt the password using the provided key or from keyring."""
    if key is None:
        key = load_encryption_key()
        if key is None:
            logger.error("No encryption key available for password encryption")
            return None

    cipher_suite = Fernet(key)
    encrypted_password = cipher_suite.encrypt(password.encode())
    return encrypted_password.decode()


def decrypt_password(encrypted_password, key=None):
    """Decrypt the encrypted password using the provided key or from keyring."""
    if key is None:
        key = load_encryption_key()
        if key is None:
            logger.error("No encryption key available for password decryption")
            return None

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
    container = get_container()
    blocknet_bin = container.blocknet_bin
    blockdx_bin = container.blockdx_bin[-1] if container.system == "Darwin" else container.blockdx_bin
    xlite_bin = container.xlite_bin[-1] if container.system == "Darwin" else container.xlite_bin
    xlite_daemon_bin = container.xlite_daemon_bin
    # Initialize process lists
    process_lists: dict = {blocknet_bin: [], blockdx_bin: [], xlite_bin: [], xlite_daemon_bin: []}

    # Process all running processes
    for proc in psutil.process_iter(["pid", "name", "status"]):
        pid = proc.info["pid"]
        name = proc.info["name"]
        status = proc.info["status"]

        # Check against each target process type
        for target_name, process_list in process_lists.items():
            result_pid = handle_process(pid, name, status, target_name)
            if result_pid is not None:
                process_list.append(result_pid)
                break  # Process matched, no need to check other types

    return (
        process_lists[blocknet_bin],
        process_lists[blockdx_bin],
        process_lists[xlite_bin],
        process_lists[xlite_daemon_bin],
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
