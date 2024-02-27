import asyncio
# import cProfile
import logging
import os
import platform
import signal
import sys
import time
import tkinter as tk
from tkinter import filedialog
import json
import psutil
from threading import Thread

from blockdx import BlockdxUtility
from blocknet_core import BlocknetUtility
from conf_data import blockdx_selectedWallets_blocknet, aio_blocknet_data_path, blocknet_bin_name, blockdx_bin_name

asyncio_logger = logging.getLogger('asyncio')
asyncio_logger.setLevel(logging.WARNING)


class BlocknetGUI:
    def __init__(self, root):

        self.cfg = load_cfg_json()
        custom_path = None
        if self.cfg and 'custom_path' in self.cfg:
            custom_path = self.cfg['custom_path']

        self.blocknet_utility = BlocknetUtility(custom_path=custom_path)
        self.blockdx_utility = BlockdxUtility()
        # blocknet_core

        self.disable_start_blockdx_button = False
        self.blockdx_valid_config_checkbox_string_var = None
        self.blockdx_valid_config_checkbox_state = None
        self.blockdx_start_close_button_string_var = None
        self.blocknet_conf_status_checkbox_string_var = None
        self.blocknet_conf_status_checkbox_state = None
        self.blockdx_process_status_checkbox_string_var = None
        self.blockdx_process_status_checkbox_state = None
        self.blocknet_start_close_button_string_var = None
        self.blocknet_process_status_checkbox_string_var = None
        self.blocknet_process_status_checkbox_state = None
        self.blocknet_data_path_status_checkbox_string_var = None
        self.blocknet_data_path_status_checkbox_state = None
        self.blocknet_rpc_connection_checkbox_state = None
        self.blocknet_rpc_connection_checkbox_string_var = None
        self.blockdx_process_running = False
        self.blocknet_process_running = False
        self.blockdx_check_config_button = None
        self.blockdx_valid_config_checkbox = None
        self.blockdx_start_close_button = None
        self.blockdx_process_status_checkbox = None
        self.blocknet_rpc_connection_checkbox = None
        self.blocknet_check_config_button = None
        self.blocknet_start_close_button = None
        self.blocknet_custom_path_button = None
        self.blocknet_conf_status_checkbox = None
        self.blocknet_process_status_checkbox = None
        self.blocknet_data_path_status_checkbox = None
        self.blocknet_data_path_entry = None
        self.blocknet_data_path_label = None
        self.blocknet_core_label = None
        self.block_dx_label = None
        self.data_path_frame = None

        self.root = root

        self.root.title("Blocknet AIO monitor")

        # Create frames for Blocknet Core and Block-dx management
        self.blocknet_core_frame = tk.Frame(root, borderwidth=2, relief="groove")
        self.blocknet_core_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        self.block_dx_frame = tk.Frame(root, borderwidth=2, relief="groove")
        self.block_dx_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        # Call functions to setup management sections
        self.setup_blocknet_core()
        self.setup_block_dx()

        # Update status for both Blocknet Core and Block-dx
        self.update_status()

        # Update process & pids for both Blocknet Core and Block-dx
        self.update_processes()

        # Bind the close event to the on_close method
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def handle_signal(self, signum, frame):
        print("Signal {} received.".format(signum))
        # sys.exit(1)
        self.on_close()

    def on_close(self):
        self.blocknet_utility.running = False
        self.blockdx_utility.running = False
        self.root.destroy()

    def setup_blocknet_core(self):
        # Add widgets for Blocknet Core management inside the blocknet_core_frame
        # Label for Blocknet Core frame
        self.blocknet_core_label = tk.Label(self.blocknet_core_frame, text="Blocknet Core Management:")
        self.blocknet_core_label.grid(row=0, column=0, columnspan=3, padx=10, pady=5, sticky="w")

        # Frame for Data Path label and entry
        self.data_path_frame = tk.Frame(self.blocknet_core_frame)
        self.data_path_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="w")

        # Label for Data Path
        self.blocknet_data_path_label = tk.Label(self.data_path_frame, text="Data Path: ")
        self.blocknet_data_path_label.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        # Entry for Data Path
        self.blocknet_data_path_entry = tk.Entry(self.data_path_frame, width=40, state='normal')
        self.blocknet_data_path_entry.grid(row=0, column=1, padx=(0, 10), pady=5, sticky="ew")

        # Configure column to resize automatically
        self.data_path_frame.columnconfigure(1, weight=1)

        # Insert data and configure the Entry widget
        self.blocknet_data_path_entry.insert(0, self.blocknet_utility.data_folder)
        self.blocknet_data_path_entry.config(state='readonly')

        # Checkboxes
        self.blocknet_data_path_status_checkbox_state = tk.BooleanVar()
        self.blocknet_data_path_status_checkbox_string_var = tk.StringVar(value="Data Path")
        self.blocknet_data_path_status_checkbox = tk.Checkbutton(self.data_path_frame,
                                                                 textvariable=self.blocknet_data_path_status_checkbox_string_var,
                                                                 variable=self.blocknet_data_path_status_checkbox_state,
                                                                 state='disabled', disabledforeground='black')
        self.blocknet_data_path_status_checkbox.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self.blocknet_process_status_checkbox_state = tk.BooleanVar()
        self.blocknet_process_status_checkbox_string_var = tk.StringVar(value="Blocknet Process is running")
        self.blocknet_process_status_checkbox = tk.Checkbutton(self.data_path_frame,
                                                               textvariable=self.blocknet_process_status_checkbox_string_var,
                                                               variable=self.blocknet_process_status_checkbox_state,
                                                               state='disabled', disabledforeground='black')
        self.blocknet_process_status_checkbox.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self.blocknet_conf_status_checkbox_state = tk.BooleanVar()
        self.blocknet_conf_status_checkbox_string_var = tk.StringVar(
            value="blocknet.conf/xbridge.conf found and parsed")
        self.blocknet_conf_status_checkbox = tk.Checkbutton(self.data_path_frame,
                                                            textvariable=self.blocknet_conf_status_checkbox_string_var,
                                                            variable=self.blocknet_conf_status_checkbox_state,
                                                            state='disabled',
                                                            disabledforeground='black')
        self.blocknet_conf_status_checkbox.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self.blocknet_rpc_connection_checkbox_state = tk.BooleanVar()
        self.blocknet_rpc_connection_checkbox_string_var = tk.StringVar(value="RPC Connection")
        self.blocknet_rpc_connection_checkbox = tk.Checkbutton(self.data_path_frame,
                                                               textvariable=self.blocknet_rpc_connection_checkbox_string_var,
                                                               variable=self.blocknet_rpc_connection_checkbox_state,
                                                               state='disabled',
                                                               disabledforeground='black')
        self.blocknet_rpc_connection_checkbox.grid(row=4, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        # Button for setting custom path
        self.blocknet_custom_path_button = tk.Button(self.data_path_frame, text="Set Custom Path",
                                                     command=self.open_custom_path_dialog, width=15)
        self.blocknet_custom_path_button.grid(row=0, column=3, padx=10, pady=5, sticky="e")

        # Button for starting or closing Blocknet
        self.blocknet_start_close_button_string_var = tk.StringVar(value="Start")
        self.blocknet_start_close_button = tk.Button(self.data_path_frame,
                                                     textvariable=self.blocknet_start_close_button_string_var,
                                                     command=self.start_or_close_blocknet, width=15)
        self.blocknet_start_close_button.grid(row=1, column=3, padx=10, pady=5, sticky="e")

        # Button for checking config
        self.blocknet_check_config_button = tk.Button(self.data_path_frame, text="Check Config",
                                                      command=self.blocknet_check_config,
                                                      width=15)
        self.blocknet_check_config_button.grid(row=2, column=3, padx=10, pady=5, sticky="e")

    def blocknet_check_config(self):
        disable_button(self.blocknet_check_config_button)
        self.blocknet_utility.compare_and_update_local_conf()
        enable_button(self.blocknet_check_config_button)

    def setup_block_dx(self):
        # Add widgets for Block-dx management inside the block_dx_frame
        # Label for Block-dx frame
        self.block_dx_label = tk.Label(self.block_dx_frame, text="Block-dx Management:")
        self.block_dx_label.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        # Checkboxes
        self.blockdx_process_status_checkbox_state = tk.BooleanVar()
        self.blockdx_process_status_checkbox_string_var = tk.StringVar(value="Blockdx Process is running")
        self.blockdx_process_status_checkbox = tk.Checkbutton(self.block_dx_frame,
                                                              textvariable=self.blockdx_process_status_checkbox_string_var,
                                                              variable=self.blockdx_process_status_checkbox_state,
                                                              state='disabled', disabledforeground='black')
        self.blockdx_process_status_checkbox.config(wraplength=400)
        self.blockdx_process_status_checkbox.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self.blockdx_valid_config_checkbox_state = tk.BooleanVar()
        self.blockdx_valid_config_checkbox_string_var = tk.StringVar(value="Blockdx config is synchronized")
        self.blockdx_valid_config_checkbox = tk.Checkbutton(self.block_dx_frame,
                                                            textvariable=self.blockdx_valid_config_checkbox_string_var,
                                                            variable=self.blockdx_valid_config_checkbox_state,
                                                            disabledforeground='black', state='disabled')
        self.blockdx_valid_config_checkbox.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        # Button for starting or closing Block-dx
        self.blockdx_start_close_button_string_var = tk.StringVar(value="Start")
        self.blockdx_start_close_button = tk.Button(self.block_dx_frame,
                                                    textvariable=self.blockdx_start_close_button_string_var,
                                                    command=self.start_or_close_blockdx, width=15)
        self.blockdx_start_close_button.grid(row=0, column=1, padx=10, pady=5, sticky="e")

        # Button for checking config
        self.blockdx_check_config_button = tk.Button(self.block_dx_frame, text="Check Config",
                                                     command=self.blockdx_check_config,
                                                     width=15, state='disabled')
        self.blockdx_check_config_button.grid(row=1, column=1, padx=10, pady=5, sticky="e")

        # Configure column 1 to expand
        self.block_dx_frame.grid_columnconfigure(1, weight=1)

    def blockdx_check_config(self):
        disable_button(self.blockdx_check_config_button)
        # Get required data
        if bool(self.blocknet_utility.data_folder and self.blocknet_utility.blocknet_conf_local):
            xbridgeconfpath = os.path.normpath(os.path.join(self.blocknet_utility.data_folder, "xbridge.conf"))
            logging.info(f"xbridgeconfpath: {xbridgeconfpath}")
            rpc_user = self.blocknet_utility.blocknet_conf_local.get('global', {}).get('rpcuser')
            rpc_password = self.blocknet_utility.blocknet_conf_local.get('global', {}).get('rpcpassword')
            self.blockdx_utility.compare_and_update_local_conf(xbridgeconfpath, rpc_user, rpc_password)
        enable_button(self.blockdx_check_config_button)

    def open_custom_path_dialog(self):
        custom_path = filedialog.askdirectory(title="Select Custom Data Path")
        if custom_path:
            self.on_custom_path_set(custom_path)

    def on_custom_path_set(self, custom_path):
        self.blocknet_utility.set_custom_data_path(custom_path)
        self.blocknet_data_path_entry.config(state='normal')
        self.blocknet_data_path_entry.delete(0, 'end')
        self.blocknet_data_path_entry.insert(0, custom_path)
        self.blocknet_data_path_entry.config(state='readonly')

        # Adjust the width of the Entry widget based on the length of the text
        text_length = len(custom_path)
        self.blocknet_data_path_entry.config(width=text_length)
        save_cfg_json('custom_path', custom_path)

    def start_or_close_blocknet(self):
        disable_button(self.blocknet_start_close_button)
        if self.blocknet_process_running:
            self.blocknet_utility.close_blocknet()
        else:
            my_thread = Thread(target=self.blocknet_utility.start_blocknet,
                               kwargs={'gui_button': self.blocknet_start_close_button})
            my_thread.start()
        self.root.after(2000, lambda: enable_button(self.blocknet_start_close_button))

    def enable_button(self):
        self.disable_start_blockdx_button = False

    def start_or_close_blockdx(self):
        disable_button(self.blockdx_start_close_button)
        self.disable_start_blockdx_button = True
        if self.blockdx_process_running:
            self.blockdx_utility.close_blockdx()
        else:
            my_thread = Thread(target=self.blockdx_utility.start_blockdx,
                               kwargs={'gui_button': self.blockdx_start_close_button})
            my_thread.start()
        self.root.after(2000, self.enable_button)

    async def update_status_blocknet_core(self):
        self.blocknet_start_close_button_string_var.set("Downloading..." if self.blocknet_utility.downloading_bin else (
            "Close" if self.blocknet_process_running else "Start"))
        self.blocknet_process_status_checkbox_string_var.set(
            f"Blocknet Process is running, PIDs: {self.blocknet_utility.blocknet_pids}" if self.blocknet_process_running else "Blocknet Process is not running")
        self.blocknet_process_status_checkbox_state.set(self.blocknet_process_running)
        self.blocknet_custom_path_button.config(state='normal' if not self.blocknet_process_running else 'disabled')
        conf_exist_and_parsed = bool(
            self.blocknet_utility.blocknet_conf_local and self.blocknet_utility.xbridge_conf_local)
        self.blocknet_conf_status_checkbox_state.set(conf_exist_and_parsed)
        self.blocknet_conf_status_checkbox_string_var.set(
            "blocknet.conf/xbridge.conf valid" if conf_exist_and_parsed else "missing or invalid blocknet.conf/xbridge.conf, click on Check Config button")
        exist = self.blocknet_utility.check_data_folder_existence()
        self.blocknet_data_path_status_checkbox_state.set(exist)
        self.blocknet_data_path_status_checkbox_string_var.set("Valid Data Path" if exist else "No valid data path set")
        self.blocknet_rpc_connection_checkbox_state.set(self.blocknet_utility.valid_rpc)
        self.blocknet_rpc_connection_checkbox_string_var.set(
            "RPC Connection active" if self.blocknet_utility.valid_rpc else "RPC Connection inactive")

    async def update_status_blockdx(self):
        self.blockdx_process_status_checkbox_state.set(self.blockdx_process_running)
        self.blockdx_process_status_checkbox_string_var.set(
            f"Blockdx Process is running, PIDs: {self.blockdx_utility.blockdx_pids}" if self.blockdx_process_running else "Blockdx Process is not running")
        self.blockdx_start_close_button_string_var.set("Downloading..." if self.blockdx_utility.downloading_bin else (
            "Close" if self.blockdx_process_running else "Start"))
        self.blockdx_start_close_button.config(
            state='normal' if not self.blockdx_utility.downloading_bin and self.blocknet_utility.valid_rpc and not self.disable_start_blockdx_button else 'disabled')

        # Check if data folder and blocknet conf are present
        valid_core_setup = bool(self.blocknet_utility.data_folder) and bool(self.blocknet_utility.blocknet_conf_local)
        if valid_core_setup:
            xbridgeconfpath = os.path.join(self.blocknet_utility.data_folder, "xbridge.conf")
            rpc_user = self.blocknet_utility.blocknet_conf_local.get('global', {}).get('rpcuser')
            rpc_password = self.blocknet_utility.blocknet_conf_local.get('global', {}).get('rpcpassword')
            # Enable or disable the check config button based on the presence of xbridge.conf and rpc credentials
            self.blockdx_check_config_button.config(
                state='normal' if (os.path.exists(xbridgeconfpath) and rpc_password and rpc_user) else 'disabled')
            # Check if blockdx config is synchronized
            blockdx_conf = self.blockdx_utility.blockdx_conf_local
            is_blockdx_config_sync = (
                    blockdx_conf and
                    blockdx_conf.get('user') == rpc_user and
                    blockdx_conf.get('password') == rpc_password and
                    blockdx_conf.get('xbridgeConfPath') == xbridgeconfpath and
                    isinstance(blockdx_conf.get('selectedWallets'), list) and
                    blockdx_selectedWallets_blocknet in blockdx_conf.get('selectedWallets')
            )
            # Update the validity checkbox and process status text
            self.blockdx_valid_config_checkbox_state.set(is_blockdx_config_sync)
            self.blockdx_valid_config_checkbox_string_var.set(
                "Blockdx config is synchronized" if is_blockdx_config_sync else "Blockdx config is not synchronized with core, click on Check Config button")
        else:
            self.blockdx_valid_config_checkbox_state.set(False)
            # If data folder or blocknet conf is missing, disable the check config button
            self.blockdx_check_config_button.config(state='disabled')
            self.blockdx_valid_config_checkbox_string_var.set(
                "Blockdx config is not synchronized, configure blocknet core first")

    async def check_processes(self):

        system = platform.system()
        blockdx_bin = blockdx_bin_name.get(system, None)
        if not blockdx_bin:
            logging.warning("Unsupported system")
            return

        start_time = time.time()

        # Check Blocknet process
        if self.blocknet_utility.blocknet_process is not None:
            process_status = self.blocknet_utility.blocknet_process.poll()
            if process_status is not None:
                logging.info(f"Blocknet process has terminated with return code {process_status}")
                self.blocknet_utility.blocknet_process = None

        # Check Block DX process
        if self.blockdx_utility.blockdx_process is not None:
            process_status = self.blockdx_utility.blockdx_process.poll()
            if process_status is not None:
                logging.info(f"blockdx process has terminated with return code {process_status}")
                self.blockdx_utility.blockdx_process = None

        blocknet_processes = []
        blockdx_processes = []

        try:
            # Get all processes
            for proc in psutil.process_iter(['pid', 'name']):
                # Check if any process matches the Blocknet process name
                if blocknet_bin_name in proc.info['name']:
                    blocknet_processes.append(proc.info['pid'])
                # Check if any process matches the Block DX process name
                if blockdx_bin in proc.info['name']:
                    blockdx_processes.append(proc.info['pid'])
        except psutil.Error as e:
            logging.warning(f"Error while checking processes: {e}")

        # Update Blocknet process status and store the PIDs
        self.blocknet_process_running = bool(blocknet_processes)
        self.blocknet_utility.blocknet_pids = blocknet_processes

        # Update Block DX process status and store the PIDs
        self.blockdx_process_running = bool(blockdx_processes)
        self.blockdx_utility.blockdx_pids = blockdx_processes
        # Calculate execution time
        # end_time = time.time()
        # execution_time = end_time - start_time
        # Log execution time
        # logging.debug(f"Execution time of check_processes: {execution_time} seconds")

    def update_status(self):
        # Define an async function to run the coroutines concurrently
        async def update_status_async():
            await asyncio.gather(
                self.update_status_blocknet_core(),
                self.update_status_blockdx()
            )

        # Run the async function using asyncio.run() to execute the coroutines
        asyncio.run(update_status_async())

        # Schedule the next update
        self.root.after(1000, self.update_status)

    def update_processes(self):
        # Define an async function to run the coroutines concurrently
        async def update_status_async():
            await asyncio.gather(
                self.check_processes()
            )

        # Run the async function using asyncio.run() to execute the coroutines
        asyncio.run(update_status_async())

        # Schedule the next update
        self.root.after(2000, self.update_processes)


def load_cfg_json():
    system = platform.system()
    local_filename = "cfg.json"
    local_conf_path = aio_blocknet_data_path.get(system)
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


def save_cfg_json(key, data):
    system = platform.system()
    local_filename = "cfg.json"
    local_conf_path = aio_blocknet_data_path.get(system)
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


def enable_button(button):
    button.config(state=tk.NORMAL)


def disable_button(button):
    button.config(state=tk.DISABLED)


def run_gui():
    root = tk.Tk()
    app = BlocknetGUI(root=root)
    try:
        root.mainloop()
    except:
        sys.exit(0)


if __name__ == "__main__":
    run_gui()
    # cProfile.run('run_gui()', filename='profile_stats.txt')
