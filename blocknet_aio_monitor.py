import asyncio
# import cProfile
import logging
import os
import platform
import signal
import sys
import time
import tkinter as tk
from tkinter import filedialog, simpledialog
import json
import psutil
from threading import Thread
from cryptography.fernet import Fernet

from blockdx import BlockdxUtility
from blocknet_core import BlocknetUtility
from xlite import XliteUtility

from conf_data import blockdx_selectedWallets_blocknet, aio_blocknet_data_path, blocknet_bin_name, blockdx_bin_name, \
    xlite_bin_name, xlite_daemon_bin_name

asyncio_logger = logging.getLogger('asyncio')
asyncio_logger.setLevel(logging.WARNING)

system = platform.system()
machine = platform.machine()
blocknet_bin = blocknet_bin_name.get(system, None)
xlite_daemon_bin = xlite_daemon_bin_name.get((system, machine))
blockdx_bin = blockdx_bin_name.get(system, None)
xlite_bin = xlite_bin_name.get(system, None)


class BlocknetGUI:
    def __init__(self, root):
        self.cfg = load_cfg_json()
        custom_path = None
        self.xlite_password = None
        if self.cfg:
            if 'custom_path' in self.cfg:
                custom_path = self.cfg['custom_path']
            if 'salt' in self.cfg and 'xl_pass' in self.cfg:
                # logging.info(f"xlite password: {self.cfg['xl_pass']} {self.cfg['salt'].encode()}")
                try:
                    self.xlite_password = decrypt_password(self.cfg['xl_pass'], self.cfg['salt'].encode())
                except Exception as e:
                    logging.error(f"Error decrypting xlite password: {e}")
                    self.xlite_password = None

        self.blocknet_utility = BlocknetUtility(custom_path=custom_path)
        self.blockdx_utility = BlockdxUtility()
        self.xlite_utility = XliteUtility()

        # block-dx
        self.block_dx_label = None
        self.blockdx_check_config_button = None
        self.blockdx_process_running = False
        self.blockdx_process_status_checkbox = None
        self.blockdx_process_status_checkbox_state = None
        self.blockdx_process_status_checkbox_string_var = None
        self.blockdx_start_close_button = None
        self.blockdx_start_close_button_string_var = None
        self.blockdx_valid_config_checkbox = None
        self.blockdx_valid_config_checkbox_string_var = None
        self.blockdx_valid_config_checkbox_state = None
        self.disable_start_blockdx_button = False
        self.disable_start_blocknet_button = False

        # blocknet
        self.blocknet_check_config_button = None
        self.blocknet_conf_status_checkbox = None
        self.blocknet_conf_status_checkbox_state = None
        self.blocknet_conf_status_checkbox_string_var = None
        self.blocknet_core_label = None
        self.blocknet_custom_path_button = None
        self.blocknet_data_path_frame = None
        self.blocknet_data_path_entry = None
        self.blocknet_data_path_label = None
        self.blocknet_data_path_status_checkbox = None
        self.blocknet_data_path_status_checkbox_state = None
        self.blocknet_data_path_status_checkbox_string_var = None
        self.blocknet_process_running = False
        self.blocknet_process_status_checkbox = None
        self.blocknet_process_status_checkbox_state = None
        self.blocknet_process_status_checkbox_string_var = None
        self.blocknet_rpc_connection_checkbox = None
        self.blocknet_rpc_connection_checkbox_state = None
        self.blocknet_rpc_connection_checkbox_string_var = None
        self.blocknet_start_close_button = None
        self.blocknet_start_close_button_string_var = None

        # xlite-daemon
        self.xlite_daemon_process_running = False
        self.xlite_daemon_process_status_checkbox = None
        self.xlite_daemon_process_status_checkbox_state = None
        self.xlite_daemon_process_status_checkbox_string_var = None
        self.xlite_daemon_valid_config_checkbox = None
        self.xlite_daemon_valid_config_checkbox_state = None
        self.xlite_daemon_valid_config_checkbox_string_var = None

        # xlite
        self.disable_start_xlite_button = False
        self.xlite_label = None
        self.xlite_process_running = False
        self.xlite_process_status_checkbox = None
        self.xlite_process_status_checkbox_state = None
        self.xlite_process_status_checkbox_string_var = None
        self.xlite_refresh_button = None
        self.xlite_refresh_button_string_var = None
        self.xlite_reverse_proxy_process_status_checkbox = None
        self.xlite_reverse_proxy_process_status_checkbox_state = None
        self.xlite_reverse_proxy_process_status_checkbox_string_var = None
        self.xlite_start_close_button = None
        self.xlite_start_close_button_string_var = None
        self.xlite_store_password_button = None
        self.xlite_store_password_button_string_var = None
        self.xlite_valid_config_checkbox = None
        self.xlite_valid_config_checkbox_state = None
        self.xlite_valid_config_checkbox_string_var = None

        self.time_disable_button = 3000

        self.root = root
        self.root.title("Blocknet AIO monitor")

        # Create frames for Blocknet Core/Block-dx/Xlite management
        self.blocknet_core_frame = tk.Frame(root, borderwidth=2, relief="groove")
        self.blocknet_core_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        self.block_dx_frame = tk.Frame(root, borderwidth=2, relief="groove")
        self.block_dx_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        self.xlite_frame = tk.Frame(root, borderwidth=2, relief="groove")
        self.xlite_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")

        # Call functions to setup management sections
        self.setup_blocknet_core()
        self.setup_block_dx()
        self.setup_xlite()

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
        self.blocknet_data_path_frame = tk.Frame(self.blocknet_core_frame)
        self.blocknet_data_path_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="w")

        # Label for Data Path
        self.blocknet_data_path_label = tk.Label(self.blocknet_data_path_frame, text="Data Path: ")
        self.blocknet_data_path_label.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        # Entry for Data Path
        self.blocknet_data_path_entry = tk.Entry(self.blocknet_data_path_frame, width=40, state='normal')
        self.blocknet_data_path_entry.grid(row=0, column=1, padx=(0, 10), pady=5, sticky="ew")

        # Configure column to resize automatically
        self.blocknet_data_path_frame.columnconfigure(1, weight=1)

        # Insert data and configure the Entry widget
        self.blocknet_data_path_entry.insert(0, self.blocknet_utility.data_folder)
        self.blocknet_data_path_entry.config(state='readonly')

        # Checkboxes
        self.blocknet_data_path_status_checkbox_state = tk.BooleanVar()
        self.blocknet_data_path_status_checkbox_string_var = tk.StringVar(value="Data Path")
        self.blocknet_data_path_status_checkbox = tk.Checkbutton(self.blocknet_data_path_frame,
                                                                 textvariable=self.blocknet_data_path_status_checkbox_string_var,
                                                                 variable=self.blocknet_data_path_status_checkbox_state,
                                                                 state='disabled', disabledforeground='black')
        self.blocknet_data_path_status_checkbox.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self.blocknet_process_status_checkbox_state = tk.BooleanVar()
        self.blocknet_process_status_checkbox_string_var = tk.StringVar(value="Blocknet Process is running")
        self.blocknet_process_status_checkbox = tk.Checkbutton(self.blocknet_data_path_frame,
                                                               textvariable=self.blocknet_process_status_checkbox_string_var,
                                                               variable=self.blocknet_process_status_checkbox_state,
                                                               state='disabled', disabledforeground='black')
        self.blocknet_process_status_checkbox.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self.blocknet_conf_status_checkbox_state = tk.BooleanVar()
        self.blocknet_conf_status_checkbox_string_var = tk.StringVar(
            value="blocknet.conf/xbridge.conf found and parsed")
        self.blocknet_conf_status_checkbox = tk.Checkbutton(self.blocknet_data_path_frame,
                                                            textvariable=self.blocknet_conf_status_checkbox_string_var,
                                                            variable=self.blocknet_conf_status_checkbox_state,
                                                            state='disabled',
                                                            disabledforeground='black')
        self.blocknet_conf_status_checkbox.grid(row=3, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self.blocknet_rpc_connection_checkbox_state = tk.BooleanVar()
        self.blocknet_rpc_connection_checkbox_string_var = tk.StringVar(value="RPC Connection")
        self.blocknet_rpc_connection_checkbox = tk.Checkbutton(self.blocknet_data_path_frame,
                                                               textvariable=self.blocknet_rpc_connection_checkbox_string_var,
                                                               variable=self.blocknet_rpc_connection_checkbox_state,
                                                               state='disabled',
                                                               disabledforeground='black')
        self.blocknet_rpc_connection_checkbox.grid(row=4, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        # Button for setting custom path
        self.blocknet_custom_path_button = tk.Button(self.blocknet_data_path_frame, text="Set Custom Path",
                                                     command=self.open_custom_path_dialog, width=15)
        self.blocknet_custom_path_button.grid(row=0, column=3, padx=10, pady=5, sticky="e")

        # Button for starting or closing Blocknet
        self.blocknet_start_close_button_string_var = tk.StringVar(value="Start")
        self.blocknet_start_close_button = tk.Button(self.blocknet_data_path_frame,
                                                     textvariable=self.blocknet_start_close_button_string_var,
                                                     command=self.start_or_close_blocknet, width=15)
        self.blocknet_start_close_button.grid(row=1, column=3, padx=10, pady=5, sticky="e")

        # Button for checking config
        self.blocknet_check_config_button = tk.Button(self.blocknet_data_path_frame, text="Check Config",
                                                      command=self.blocknet_check_config,
                                                      width=15)
        self.blocknet_check_config_button.grid(row=2, column=3, padx=10, pady=5, sticky="e")

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

    def setup_xlite(self):
        self.xlite_label = tk.Label(self.xlite_frame, text="Xlite Management:")
        self.xlite_label.grid(row=0, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        # Checkboxes
        self.xlite_process_status_checkbox_state = tk.BooleanVar()
        self.xlite_process_status_checkbox_string_var = tk.StringVar(value="Xlite Process is running")
        self.xlite_process_status_checkbox = tk.Checkbutton(self.xlite_frame,
                                                            textvariable=self.xlite_process_status_checkbox_string_var,
                                                            variable=self.xlite_process_status_checkbox_state,
                                                            state='disabled', disabledforeground='black')
        self.xlite_process_status_checkbox.config(wraplength=400)
        self.xlite_process_status_checkbox.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self.xlite_daemon_process_status_checkbox_state = tk.BooleanVar()
        self.xlite_daemon_process_status_checkbox_string_var = tk.StringVar(value="Xlite-daemon Process is running")
        self.xlite_daemon_process_status_checkbox = tk.Checkbutton(self.xlite_frame,
                                                                   textvariable=self.xlite_daemon_process_status_checkbox_string_var,
                                                                   variable=self.xlite_daemon_process_status_checkbox_state,
                                                                   state='disabled', disabledforeground='black')
        self.xlite_daemon_process_status_checkbox.config(wraplength=400)
        self.xlite_daemon_process_status_checkbox.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self.xlite_reverse_proxy_process_status_checkbox_state = tk.BooleanVar()
        self.xlite_reverse_proxy_process_status_checkbox_string_var = tk.StringVar(
            value="Xlite-reverse-proxy Process is not running")
        self.xlite_reverse_proxy_process_status_checkbox = tk.Checkbutton(self.xlite_frame,
                                                                          textvariable=self.xlite_reverse_proxy_process_status_checkbox_string_var,
                                                                          variable=self.xlite_reverse_proxy_process_status_checkbox_state,
                                                                          state='disabled', disabledforeground='black')
        self.xlite_reverse_proxy_process_status_checkbox.config(wraplength=400)
        self.xlite_reverse_proxy_process_status_checkbox.grid(row=3, column=0, columnspan=2, padx=10, pady=5,
                                                              sticky="w")

        self.xlite_valid_config_checkbox_state = tk.BooleanVar()
        self.xlite_valid_config_checkbox_string_var = tk.StringVar(
            value="Xlite config is not valid")
        self.xlite_valid_config_checkbox = tk.Checkbutton(self.xlite_frame,
                                                          textvariable=self.xlite_valid_config_checkbox_string_var,
                                                          variable=self.xlite_valid_config_checkbox_state,
                                                          state='disabled', disabledforeground='black')
        self.xlite_valid_config_checkbox.config(wraplength=400)
        self.xlite_valid_config_checkbox.grid(row=4, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        self.xlite_daemon_valid_config_checkbox_state = tk.BooleanVar()
        self.xlite_daemon_valid_config_checkbox_string_var = tk.StringVar(value="Xlite-daemon config is not valid")
        self.xlite_daemon_valid_config_checkbox = tk.Checkbutton(self.xlite_frame,
                                                                 textvariable=self.xlite_daemon_valid_config_checkbox_string_var,
                                                                 variable=self.xlite_daemon_valid_config_checkbox_state,
                                                                 state='disabled', disabledforeground='black')
        self.xlite_daemon_valid_config_checkbox.config(wraplength=400)
        self.xlite_daemon_valid_config_checkbox.grid(row=5, column=0, columnspan=2, padx=10, pady=5, sticky="w")

        # Button for starting or closing Xlite
        self.xlite_start_close_button_string_var = tk.StringVar(value="Start")
        self.xlite_start_close_button = tk.Button(self.xlite_frame,
                                                  textvariable=self.xlite_start_close_button_string_var,
                                                  command=self.start_or_close_xlite, width=15)
        self.xlite_start_close_button.grid(row=0, column=1, padx=10, pady=5, sticky="e")

        # Button for refreshing Xlite config data
        self.xlite_refresh_button_string_var = tk.StringVar(value="Refresh Config")
        self.xlite_refresh_button = tk.Button(self.xlite_frame,
                                              textvariable=self.xlite_refresh_button_string_var,
                                              command=self.refresh_xlite_confs, width=15)
        self.xlite_refresh_button.grid(row=1, column=1, padx=10, pady=5, sticky="e")

        # Create the Button widget with a text variable
        self.xlite_store_password_button_string_var = tk.StringVar(value="Store Password")
        self.xlite_store_password_button = tk.Button(self.xlite_frame,
                                                     textvariable=self.xlite_store_password_button_string_var,
                                                     width=15)

        self.xlite_store_password_button.grid(row=2, column=1, padx=10, pady=5, sticky="e")
        # Bind left-click event
        self.xlite_store_password_button.bind("<Button-1>",
                                              lambda event: self.xlite_store_password_button_mouse_click(event))

        # Bind right-click event
        self.xlite_store_password_button.bind("<Button-3>",
                                              lambda event: self.xlite_store_password_button_mouse_click(event))

        # Set button command for normal button clicks
        self.xlite_store_password_button.config(command=self.xlite_store_password_button_mouse_click)

        # Configure column 1 to expand
        self.xlite_frame.grid_columnconfigure(1, weight=1)

    def xlite_store_password_button_mouse_click(self, event=None):

        # self.xlite_store_password_button.config(relief='sunken')

        # Function to handle storing password

        # Check if the right mouse button was clicked
        if event and event.num == 3:
            # wipe_stored_password
            logging.info("Right click detected")
            # Prevent the right-click event from propagating further
            remove_cfg_json_key("salt")
            remove_cfg_json_key("xl_pass")
            self.xlite_password = None
            # Delete CC_WALLET_PASS variable
            if "CC_WALLET_PASS" in os.environ:
                os.environ.pop("CC_WALLET_PASS")
            # Delete CC_WALLET_AUTOLOGIN variable
            if "CC_WALLET_AUTOLOGIN" in os.environ:
                os.environ.pop("CC_WALLET_AUTOLOGIN")
            # self.xlite_store_password_button.config(relief='raised')
            return "break"

        # For left-click event
        if event and event.num == 1:
            # ask_user_pass
            # store_salted_pass
            logging.info("Left click detected")
            password = simpledialog.askstring("Store Xlite Password", "Please enter Xlite your password:", show='*')
            if password:
                encryption_key = generate_key()
                salted_pass = encrypt_password(password, encryption_key)
                save_cfg_json(key="salt", data=encryption_key.decode())
                save_cfg_json(key="xl_pass", data=salted_pass)
                # Store the password in a variable or perform other actions
                # logging.debug(f"Password entered: {password}, salted xl_pass: {salted_pass}")
                self.xlite_password = password
            else:
                logging.info("No password entered.")
            # Perform actions for left-click (if needed)

            # Set button relief style back to 'raised'
            self.xlite_store_password_button.config(relief='raised')
            return "break"

    def refresh_xlite_confs(self):
        self.xlite_utility.parse_xlite_conf()
        self.xlite_utility.parse_xlite_daemon_conf()

    def blocknet_check_config(self):
        disable_button(self.blocknet_check_config_button)
        self.blocknet_utility.compare_and_update_local_conf()
        enable_button(self.blocknet_check_config_button)

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

    def enable_blocknet_start_button(self):
        self.disable_start_blocknet_button = False

    def enable_blockdx_start_button(self):
        self.disable_start_blockdx_button = False

    def enable_xlite_start_button(self):
        self.disable_start_xlite_button = False

    def start_or_close_blocknet(self):
        disable_button(self.blocknet_start_close_button)
        self.disable_start_blocknet_button = True
        if self.blocknet_process_running:
            my_thread = Thread(target=self.blocknet_utility.close_blocknet)
            my_thread.start()
        else:
            my_thread = Thread(target=self.blocknet_utility.start_blocknet)
            my_thread.start()
        self.root.after(self.time_disable_button, self.enable_blocknet_start_button)

    def start_or_close_blockdx(self):
        disable_button(self.blockdx_start_close_button)
        self.disable_start_blockdx_button = True
        if self.blockdx_process_running:
            my_thread = Thread(target=self.blockdx_utility.close_blockdx)
            my_thread.start()
        else:
            my_thread = Thread(target=self.blockdx_utility.start_blockdx)
            my_thread.start()
        self.root.after(self.time_disable_button, self.enable_blockdx_start_button)

    def start_or_close_xlite(self):
        disable_button(self.xlite_start_close_button)
        self.disable_start_xlite_button = True
        if self.xlite_process_running:
            my_thread = Thread(target=self.xlite_utility.close_xlite)
            my_thread.start()

        else:
            if self.xlite_password and self.xlite_utility.xlite_conf_local and self.xlite_utility.xlite_daemon_confs_local:
                # Set the value of CC_WALLET_PASS using self.xlite_password
                os.environ["CC_WALLET_PASS"] = self.xlite_password
                # Set the value of CC_WALLET_AUTOLOGIN to 'true'
                os.environ["CC_WALLET_AUTOLOGIN"] = 'true'
            my_thread = Thread(target=self.xlite_utility.start_xlite)
            my_thread.start()
        self.root.after(self.time_disable_button, self.enable_xlite_start_button)

    def update_blocknet_start_close_button(self):
        # blocknet_start_close_button_string_var
        var = "Downloading..." if self.blocknet_utility.downloading_bin else (
            "Close" if self.blocknet_process_running else "Start")
        self.blocknet_start_close_button_string_var.set(var)

        # blocknet_start_close_button
        # not self.blocknet_utility.downloading_bin and not self.disable_start_blocknet_button

        enabled = (not self.blocknet_utility.downloading_bin and not self.disable_start_blocknet_button)
        # logging.debug(
        #     f"blocknet_utility.downloading_bin: {self.blocknet_utility.downloading_bin}"
        #     f", self.disable_start_blocknet_button: {self.disable_start_blocknet_button}, enabled: {enabled}"
        # )
        # (self.blocknet_utility.downloading_bin or self.disable_start_blocknet_button)
        self.blocknet_start_close_button.config(state='normal' if enabled else 'disabled')

    def update_blocknet_process_status_checkbox(self):
        # blocknet_process_status_checkbox_string_var
        var = f"Blocknet Process is running, PIDs: {self.blocknet_utility.blocknet_pids}" if self.blocknet_process_running else "Blocknet Process is not running"
        self.blocknet_process_status_checkbox_string_var.set(var)

        # blocknet_process_status_checkbox_state
        self.blocknet_process_status_checkbox_state.set(self.blocknet_process_running)

    def update_blocknet_custom_path_button(self):
        # blocknet_custom_path_button
        self.blocknet_custom_path_button.config(state='normal' if not self.blocknet_process_running else 'disabled')

    def update_blocknet_conf_status_checkbox(self):
        # blocknet_conf_status_checkbox_state
        conf_exist_and_parsed = bool(
            self.blocknet_utility.blocknet_conf_local and self.blocknet_utility.xbridge_conf_local)
        self.blocknet_conf_status_checkbox_state.set(conf_exist_and_parsed)

        # blocknet_conf_status_checkbox_string_var
        var = "blocknet.conf/xbridge.conf valid" if conf_exist_and_parsed else "missing or invalid blocknet.conf/xbridge.conf, click on Check Config button"
        self.blocknet_conf_status_checkbox_string_var.set(var)

    def update_blocknet_data_path_status_checkbox(self):
        # blocknet_data_path_status_checkbox_state
        exist = self.blocknet_utility.check_data_folder_existence()
        self.blocknet_data_path_status_checkbox_state.set(exist)

        # blocknet_data_path_status_checkbox_string_var
        var = "Valid Data Path" if exist else "No valid data path set"
        self.blocknet_data_path_status_checkbox_string_var.set(var)

    def update_blocknet_rpc_connection_checkbox(self):
        # blocknet_rpc_connection_checkbox_state
        self.blocknet_rpc_connection_checkbox_state.set(self.blocknet_utility.valid_rpc)

        # blocknet_rpc_connection_checkbox_string_var
        var = "RPC Connection active" if self.blocknet_utility.valid_rpc else "RPC Connection inactive"
        self.blocknet_rpc_connection_checkbox_string_var.set(var)

    def update_blockdx_process_status_checkbox(self):
        # blockdx_process_status_checkbox_state
        self.blockdx_process_status_checkbox_state.set(self.blockdx_process_running)

        # blockdx_process_status_checkbox_string_var
        var = f"Blockdx Process is running, PIDs: {self.blockdx_utility.blockdx_pids}" if self.blockdx_process_running else "Blockdx Process is not running"
        self.blockdx_process_status_checkbox_string_var.set(var)

    def update_blockdx_start_close_button(self):
        # blockdx_start_close_button_string_var
        var = "Downloading..." if self.blockdx_utility.downloading_bin else (
            "Close" if self.blockdx_process_running else "Start")
        self.blockdx_start_close_button_string_var.set(var)

        # blockdx_start_close_button
        enabled = (self.blockdx_process_running and not self.disable_start_blockdx_button) or (
                not self.blockdx_utility.downloading_bin and self.blocknet_utility.valid_rpc and not self.disable_start_blockdx_button)
        self.blockdx_start_close_button.config(state='normal' if enabled else 'disabled')

    def update_blockdx_config_button_checkbox(self):
        # blockdx_valid_config_checkbox_state
        valid_core_setup = bool(self.blocknet_utility.data_folder) and bool(self.blocknet_utility.blocknet_conf_local)
        if valid_core_setup:
            xbridgeconfpath = os.path.join(self.blocknet_utility.data_folder, "xbridge.conf")
            rpc_user = self.blocknet_utility.blocknet_conf_local.get('global', {}).get('rpcuser')
            rpc_password = self.blocknet_utility.blocknet_conf_local.get('global', {}).get('rpcpassword')

            # blockdx_check_config_button
            blocknet_conf_is_valid = (os.path.exists(xbridgeconfpath) and rpc_password and rpc_user)
            self.blockdx_check_config_button.config(state='normal' if blocknet_conf_is_valid else 'disabled')

            # blockdx_valid_config_checkbox_state
            blockdx_conf = self.blockdx_utility.blockdx_conf_local
            is_blockdx_config_sync = (
                    bool(blockdx_conf) and
                    blockdx_conf.get('user') == rpc_user and
                    blockdx_conf.get('password') == rpc_password and
                    blockdx_conf.get('xbridgeConfPath') == xbridgeconfpath and
                    isinstance(blockdx_conf.get('selectedWallets'), list) and
                    blockdx_selectedWallets_blocknet in blockdx_conf.get('selectedWallets', [])
            )

            # blockdx_valid_config_checkbox_string_var
            self.blockdx_valid_config_checkbox_state.set(is_blockdx_config_sync)
            var = "Blockdx config is synchronized" if is_blockdx_config_sync else "Blockdx config is not synchronized with core, click on Check Config button"
            self.blockdx_valid_config_checkbox_string_var.set(var)
        else:
            # blockdx_check_config_button
            self.blockdx_valid_config_checkbox_state.set(False)
            self.blockdx_check_config_button.config(state='disabled')

            # blockdx_valid_config_checkbox_string_var
            var = "Blockdx config is not synchronized, configure blocknet core first"
            self.blockdx_valid_config_checkbox_string_var.set(var)

    def update_xlite_process_status_checkbox(self):
        # xlite_process_status_checkbox_state
        self.xlite_process_status_checkbox_state.set(self.xlite_process_running)

        # xlite_process_status_checkbox_string_var
        var = f"Xlite Process is running, PIDs: {self.xlite_utility.xlite_pids}" if self.xlite_process_running else (
            "Xlite Process is not running")
        self.xlite_process_status_checkbox_string_var.set(var)

    def update_xlite_start_close_button(self):
        # xlite_start_close_button_string_var
        var = "Downloading..." if self.xlite_utility.downloading_bin else (
            "Close" if self.xlite_process_running else "Start")
        self.xlite_start_close_button_string_var.set(var)

        # xlite_start_close_button
        disable_start_close_button = self.xlite_utility.downloading_bin or self.disable_start_xlite_button
        self.xlite_start_close_button.config(state='normal' if not disable_start_close_button else 'disabled')

    def update_xlite_store_password_button(self):
        # xlite_store_password_button
        self.xlite_store_password_button.config(relief='raised' if not self.xlite_password else 'sunken')

    def update_xlite_daemon_process_status(self):
        # xlite_daemon_process_status_checkbox_state
        self.xlite_daemon_process_status_checkbox_state.set(self.xlite_daemon_process_running)

        # xlite_daemon_process_status_checkbox_string_var
        var = f"Xlite-daemon Process is running, PIDs: {self.xlite_utility.xlite_daemon_pids}" if self.xlite_daemon_process_running else (
            "Xlite-daemon Process is not running")
        self.xlite_daemon_process_status_checkbox_string_var.set(var)

    def update_xlite_valid_config_checkbox(self):
        # xlite_valid_config_checkbox_state
        valid_config = True if self.xlite_utility.xlite_conf_local else False
        self.xlite_valid_config_checkbox_state.set(valid_config)
        # self.xlite_valid_config_checkbox_string_var
        var = f"Xlite config is valid" if valid_config else "Xlite config is not valid"
        self.xlite_valid_config_checkbox_string_var.set(var)

    def update_xlite_daemon_valid_config_checkbox(self):
        # xlite_daemon_valid_config_checkbox_state
        valid_config = True if (self.xlite_utility.xlite_daemon_confs_local and
                                'master' in self.xlite_utility.xlite_daemon_confs_local) else False
        self.xlite_daemon_valid_config_checkbox_state.set(valid_config)
        # self.xlite_daemon_valid_config_checkbox_string_var
        var = f"Xlite-daemon config is valid" if valid_config else "Xlite-daemon config is not valid"
        self.xlite_daemon_valid_config_checkbox_string_var.set(var)

    async def update_status_blocknet_core(self):
        self.update_blocknet_start_close_button()
        self.update_blocknet_process_status_checkbox()
        self.update_blocknet_custom_path_button()
        self.update_blocknet_conf_status_checkbox()
        self.update_blocknet_data_path_status_checkbox()
        self.update_blocknet_rpc_connection_checkbox()

    async def update_status_blockdx(self):
        self.update_blockdx_process_status_checkbox()
        self.update_blockdx_start_close_button()
        self.update_blockdx_config_button_checkbox()

    async def update_status_xlite(self):
        self.update_xlite_process_status_checkbox()
        self.update_xlite_start_close_button()
        self.update_xlite_store_password_button()
        self.update_xlite_daemon_process_status()
        self.update_xlite_valid_config_checkbox()
        self.update_xlite_daemon_valid_config_checkbox()

    def update_status(self):
        # Define an async function to run the coroutines concurrently
        async def update_status_async():
            await asyncio.gather(
                self.update_status_blocknet_core(),
                self.update_status_blockdx(),
                self.update_status_xlite()
            )

        # Run the async function using asyncio.run() to execute the coroutines
        asyncio.run(update_status_async())

        # Schedule the next update
        self.root.after(1000, self.update_status)

    async def check_processes(self):

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

        # Check Xlite process
        if self.xlite_utility.xlite_process is not None:
            process_status = self.xlite_utility.xlite_process.poll()
            if process_status is not None:
                logging.info(f"Xlite process has terminated with return code {process_status}")
                self.xlite_utility.xlite_process = None

        # Check Xlite process
        if self.xlite_utility.xlite_daemon_process is not None:
            process_status = self.xlite_utility.xlite_daemon_process.poll()
            if process_status is not None:
                logging.info(f"Xlite-daemon process has terminated with return code {process_status}")
                self.xlite_utility.xlite_daemon_process = None

        blocknet_processes = []
        blockdx_processes = []
        xlite_processes = []
        xlite_daemon_processes = []

        try:
            # Get all processes
            for proc in psutil.process_iter(['pid', 'name']):
                # Check if any process matches the Blocknet process name
                if blocknet_bin == proc.info['name']:
                    blocknet_processes.append(proc.info['pid'])
                # Check if any process matches the Block DX process name
                if (blockdx_bin[-1] if system == "Darwin" else blockdx_bin) == proc.info['name']:
                    blockdx_processes.append(proc.info['pid'])
                # Check if any process matches the Xlite process name
                if (xlite_bin[-1] if system == "Darwin" else xlite_bin) == proc.info['name']:
                    xlite_processes.append(proc.info['pid'])
                # Check if any process matches the Xlite-daemon process name
                if xlite_daemon_bin == proc.info['name']:
                    xlite_daemon_processes.append(proc.info['pid'])
        except psutil.Error as e:
            logging.warning(f"Error while checking processes: {e}")

        # Update Blocknet process status and store the PIDs
        self.blocknet_process_running = bool(blocknet_processes)
        self.blocknet_utility.blocknet_pids = blocknet_processes

        # Update Block DX process status and store the PIDs
        self.blockdx_process_running = bool(blockdx_processes)
        self.blockdx_utility.blockdx_pids = blockdx_processes

        # Update Xlite process status and store the PIDs
        self.xlite_process_running = bool(xlite_processes)
        self.xlite_utility.xlite_pids = xlite_processes

        # Update Xlite-daemon process status and store the PIDs
        self.xlite_daemon_process_running = bool(xlite_daemon_processes)
        self.xlite_utility.xlite_daemon_pids = xlite_daemon_processes

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


def remove_cfg_json_key(key):
    local_filename = "cfg.json"
    local_conf_path = aio_blocknet_data_path.get(system)
    filename = os.path.join(os.path.expandvars(os.path.expanduser(local_conf_path)), local_filename)

    # Try loading the existing JSON file
    try:
        with open(filename, 'r') as file:
            cfg_data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        # If file doesn't exist or JSON decoding error occurs, return without modifying anything
        logging.error(f"Failed to load JSON file: {filename}")
        return

    # Check if the key exists in the dictionary
    if key in cfg_data:
        # Remove the key from the dictionary
        del cfg_data[key]
        # Save the modified dictionary back to the file
        with open(filename, 'w') as file:
            json.dump(cfg_data, file)
        logging.info(f"Key '{key}' was removed from configuration file: {filename}")
    else:
        logging.warning(f"Key '{key}' not found in configuration file: {filename}")


def save_cfg_json(key, data):
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
