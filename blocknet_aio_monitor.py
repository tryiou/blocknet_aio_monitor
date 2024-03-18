import asyncio
import ctypes
# import cProfile
import logging
import shutil
import signal
import time
import CTkToolTip
import customtkinter as ctk
import custom_tk_mods.ctkInputDialogMod as ctkInputDialogMod
import custom_tk_mods.ctkCheckBox as ctkCheckBoxMod
import json
import psutil
import threading
from PIL import Image
import PIL._tkinter_finder
from threading import Thread
from cryptography.fernet import Fernet

from blockdx import BlockdxUtility
from blocknet_core import BlocknetUtility
from xlite import XliteUtility

from conf_data import (blockdx_selectedWallets_blocknet, blockdx_bin_path, blocknet_bin_path, xlite_bin_path)

from widgets_strings import *
from globals_variables import *

asyncio_logger = logging.getLogger('asyncio')
asyncio_logger.setLevel(logging.WARNING)
pil_logger = logging.getLogger('PIL')
pil_logger.setLevel(logging.WARNING)
button_width = 120
gui_width = 400

# ctk.set_appearance_mode("system")
# ctk.set_default_color_theme("dark-blue")
ctk.set_default_color_theme(themepath)


class BlocknetGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.blocknet_version = [blocknet_release_url.split('/')[7]]
        self.blockdx_version = [blockdx_release_url.split('/')[7]]
        self.xlite_version = [xlite_release_url.split('/')[7]]

        self.last_process_check_time = None
        self.disable_daemons_conf_check = False
        self.is_blockdx_config_sync = None

        # threads
        self.download_xlite_thread = None
        self.download_blockdx_thread = None
        self.download_blocknet_thread = None
        self.update_status_thread = None
        self.blocknet_t1 = None
        self.blocknet_t2 = None
        self.xlite_t2 = None
        self.xlite_t1 = None
        self.blockdx_t2 = None
        self.blockdx_t1 = None
        self.bootstrap_thread = None

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
                    logging.error(f"Error decrypting XLite password: {e}")
                    self.xlite_password = None

        self.blocknet_utility = BlocknetUtility(custom_path=custom_path)
        self.blockdx_utility = BlockdxUtility()
        self.xlite_utility = XliteUtility()

        # binaries frame
        self.bins_install_delete_xlite_string_var = None
        self.bins_install_delete_blockdx_string_var = None
        self.bins_install_delete_blocknet_string_var = None
        self.xlite_bin_installed_boolvar = None
        self.blockdx_bin_installed_boolvar = None
        self.blocknet_bin_installed_boolvar = None
        self.bins_found_label = None
        self.bins_xlite_label = None
        self.bins_blockdx_label = None
        self.bins_blocknet_label = None
        self.bins_header_label = None
        self.bins_install_delete_xlite_tooltip = None
        self.bins_install_delete_blockdx_tooltip = None
        self.bins_install_delete_blocknet_tooltip = None
        self.bins_xlite_found_checkbox = None
        self.bins_blockdx_found_checkbox = None
        self.bins_blocknet_found_checkbox = None
        self.bins_xlite_version_optionmenu = None
        self.bins_blockdx_version_optionmenu = None
        self.bins_blocknet_version_optionmenu = None
        self.bins_install_delete_blocknet_button = None
        self.bins_install_delete_blockdx_button = None
        self.bins_install_delete_xlite_button = None
        self.bins_last_aio_folder_check_time = None

        # blocknet
        self.blocknet_download_bootstrap_button = None
        self.blocknet_download_bootstrap_string_var = None
        self.blocknet_data_path_entry_string_var = None
        self.blocknet_conf_status_checkbox_string_var = None
        self.blocknet_start_close_button_string_var = None
        self.blocknet_data_path_status_checkbox_string_var = None
        self.blocknet_process_status_checkbox_string_var = None
        self.blocknet_rpc_connection_checkbox_string_var = None
        self.blocknet_core_label = None
        self.blocknet_check_config_button = None
        self.blocknet_custom_path_button = None
        self.blocknet_start_close_button = None
        self.blocknet_conf_status_checkbox = None
        self.blocknet_conf_status_checkbox_state = None
        self.blocknet_data_path_entry = None
        self.blocknet_data_path_label = None
        self.blocknet_data_path_status_checkbox = None
        self.blocknet_data_path_status_checkbox_state = None
        self.blocknet_process_running = False
        self.blocknet_process_status_checkbox = None
        self.blocknet_process_status_checkbox_state = None
        self.blocknet_rpc_connection_checkbox = None
        self.blocknet_rpc_connection_checkbox_state = None

        # block-dx
        self.blockdx_process_status_checkbox_string_var = None
        self.blockdx_start_close_button_string_var = None
        self.blockdx_valid_config_checkbox_string_var = None
        self.blockdx_label = None
        self.blockdx_check_config_button = None
        self.blockdx_start_close_button = None
        self.disable_start_blockdx_button = False
        self.disable_start_blocknet_button = False
        self.blockdx_process_status_checkbox = None
        self.blockdx_process_status_checkbox_state = None
        self.blockdx_valid_config_checkbox = None
        self.blockdx_valid_config_checkbox_state = None
        self.blockdx_process_running = False

        # xlite
        self.disable_start_xlite_button = False
        self.xlite_label = None
        self.xlite_process_running = False
        self.xlite_process_status_checkbox = None
        self.xlite_process_status_checkbox_state = None
        self.xlite_process_status_checkbox_string_var = None
        self.xlite_check_config_button = None
        self.xlite_check_config_button_string_var = None
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
        # xlite-daemon
        self.xlite_daemon_process_running = False
        self.xlite_daemon_process_status_checkbox = None
        self.xlite_daemon_process_status_checkbox_state = None
        self.xlite_daemon_process_status_checkbox_string_var = None
        self.xlite_daemon_valid_config_checkbox = None
        self.xlite_daemon_valid_config_checkbox_state = None
        self.xlite_daemon_valid_config_checkbox_string_var = None

        self.time_disable_button = 3000

        # frames
        self.bins_download_frame = None
        self.blocknet_core_frame = None
        self.blocknet_title_frame = None
        self.blockdx_frame = None
        self.blockdx_title_frame = None
        self.xlite_frame = None
        self.xlite_title_frame = None

        self.init_setup()

    def init_setup(self):
        self.title(app_title_string)
        self.resizable(False, False)
        self.init_frames()

        self.set_howtouse_tooltip()

        # Call functions to setup management sections
        self.setup_bin()
        self.setup_blocknet_core()
        self.setup_blockdx()
        self.setup_xlite()
        # Update status for UI elements
        # Update process & pids for Blocknet Core, Block-DX & XLite
        self.update_status_thread = Thread(target=self.update_status)
        self.update_status_thread.daemon = True
        self.update_status_thread.start()
        # Bind the close event to the on_close method
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def set_howtouse_tooltip(self):
        CTkToolTip.CTkToolTip(self.blocknet_core_frame, message=tooltip_howtouse, delay=1, follow=True, border_width=2,
                              justify="left")
        CTkToolTip.CTkToolTip(self.blockdx_frame, message=tooltip_howtouse, delay=1, follow=True, border_width=2,
                              justify="left")
        CTkToolTip.CTkToolTip(self.xlite_frame, message=tooltip_howtouse, delay=1, follow=True, border_width=2,
                              justify="left")
        CTkToolTip.CTkToolTip(self.bins_download_frame, message=tooltip_howtouse, delay=1, follow=True, border_width=2,
                              justify="left")

    def init_frames(self):
        self.bins_download_frame = ctk.CTkFrame(master=self)
        self.blocknet_core_frame = ctk.CTkFrame(master=self)
        self.blockdx_frame = ctk.CTkFrame(master=self)
        self.xlite_frame = ctk.CTkFrame(master=self)
        self.bins_download_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        self.blocknet_core_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")
        self.blockdx_frame.grid(row=2, column=0, padx=10, pady=5, sticky="nsew")
        self.xlite_frame.grid(row=3, column=0, padx=10, pady=5, sticky="nsew")

    async def coroutine_bins_check_aio_folder(self):
        blocknet_pruned_version = self.blocknet_version[0].replace('v', '')
        blockdx_pruned_version = self.blockdx_version[0].replace('v', '')
        xlite_pruned_version = self.xlite_version[0].replace('v', '')

        blocknet_present = False
        blockdx_present = False
        xlite_present = False

        for item in os.listdir(aio_folder):
            item_path = os.path.join(aio_folder, item)
            if os.path.isdir(item_path):
                # if a wrong version is found, delete it.
                if 'blocknet-' in item:
                    if blocknet_pruned_version in item:
                        blocknet_present = True
                    else:
                        logging.info(f"deleting outdated version: {item_path}")
                        shutil.rmtree(item_path)
                elif 'BLOCK-DX-' in item:
                    if blockdx_pruned_version in item:
                        blockdx_present = True
                    else:
                        logging.info(f"deleting outdated version: {item_path}")
                        shutil.rmtree(item_path)
                elif 'XLite-' in item:
                    if xlite_pruned_version in item:
                        xlite_present = True
                    else:
                        logging.info(f"deleting outdated version: {item_path}")
                        shutil.rmtree(item_path)

        self.blocknet_bin_installed_boolvar.set(blocknet_present)
        self.blockdx_bin_installed_boolvar.set(blockdx_present)
        self.xlite_bin_installed_boolvar.set(xlite_present)
        self.bins_last_aio_folder_check_time = time.time()

    async def coroutine_update_bins_buttons(self):
        blocknet_boolvar = self.blocknet_bin_installed_boolvar.get()
        blockdx_boolvar = self.blockdx_bin_installed_boolvar.get()
        xlite_boolvar = self.xlite_bin_installed_boolvar.get()

        if blocknet_boolvar:
            var_blocknet = "Delete"
            blocknet_folder = os.path.join(aio_folder, blocknet_bin_path[0])
            configure_tooltip_text(self.bins_install_delete_blocknet_tooltip, blocknet_folder)
            if self.blocknet_process_running or self.blocknet_utility.downloading_bin:
                disable_button(self.bins_install_delete_blocknet_button)
            else:
                enable_button(self.bins_install_delete_blocknet_button)
        else:
            configure_tooltip_text(self.bins_install_delete_blocknet_tooltip, blocknet_release_url)
            percent_buff = self.blocknet_utility.binary_percent_download
            dl_string = f"DL: {str(int(percent_buff))}%" if percent_buff else "DL"
            var_blocknet = dl_string if self.blocknet_utility.downloading_bin else download_string
            if self.blocknet_utility.downloading_bin:
                disable_button(self.bins_install_delete_blocknet_button)
            else:
                enable_button(self.bins_install_delete_blocknet_button)

        if blockdx_boolvar:
            var_blockdx = "Delete"
            blockdx_folder = os.path.join(aio_folder, blockdx_bin_path.get(system))
            configure_tooltip_text(self.bins_install_delete_blockdx_tooltip, blockdx_folder)
            if self.blockdx_process_running or self.blockdx_utility.downloading_bin:
                disable_button(self.bins_install_delete_blockdx_button)
            else:
                enable_button(self.bins_install_delete_blockdx_button)
        else:
            configure_tooltip_text(self.bins_install_delete_blockdx_tooltip, blockdx_release_url)
            percent_buff = self.blockdx_utility.binary_percent_download
            dl_string = f"DL: {str(int(percent_buff))}%" if percent_buff else "DL"
            var_blockdx = dl_string if self.blockdx_utility.downloading_bin else download_string
            if self.blockdx_utility.downloading_bin:
                disable_button(self.bins_install_delete_blockdx_button)
            else:
                enable_button(self.bins_install_delete_blockdx_button)

        if xlite_boolvar:
            var_xlite = "Delete"
            folder = os.path.join(aio_folder, xlite_bin_path.get(system))
            configure_tooltip_text(self.bins_install_delete_xlite_tooltip, folder)
            if self.xlite_process_running or self.xlite_utility.downloading_bin:
                disable_button(self.bins_install_delete_xlite_button)
            else:
                enable_button(self.bins_install_delete_xlite_button)
        else:
            configure_tooltip_text(self.bins_install_delete_xlite_tooltip, xlite_release_url)
            percent_buff = self.xlite_utility.binary_percent_download
            dl_string = f"DL: {str(int(percent_buff))}%" if percent_buff else "DL"
            var_xlite = dl_string if self.xlite_utility.downloading_bin else download_string
            if self.xlite_utility.downloading_bin:
                disable_button(self.bins_install_delete_xlite_button)
            else:
                enable_button(self.bins_install_delete_xlite_button)

        self.bins_install_delete_blocknet_string_var.set(var_blocknet)
        self.bins_install_delete_blockdx_string_var.set(var_blockdx)
        self.bins_install_delete_xlite_string_var.set(var_xlite)

    async def update_bins_buttons_o(self):
        blocknet_boolvar = self.blocknet_bin_installed_boolvar.get()
        blockdx_boolvar = self.blockdx_bin_installed_boolvar.get()
        xlite_boolvar = self.xlite_bin_installed_boolvar.get()

        if blocknet_boolvar:
            var_blocknet = "Delete"
            blocknet_folder = os.path.join(aio_folder, blocknet_bin_path[0])
            configure_tooltip_text(self.bins_install_delete_blocknet_tooltip, blocknet_folder)
        else:
            configure_tooltip_text(self.bins_install_delete_blocknet_tooltip, blocknet_release_url)
            percent_buff = self.blocknet_utility.binary_percent_download
            dl_string = f"DL: {str(int(percent_buff))}%" if percent_buff else "DL"
            var_blocknet = f"{dl_string}" if self.blocknet_utility.downloading_bin else download_string

        if blockdx_boolvar:
            var_blockdx = "Delete"
            blockdx_folder = os.path.join(aio_folder, blockdx_bin_path.get(system))
            configure_tooltip_text(self.bins_install_delete_blockdx_tooltip, blockdx_folder)
        else:
            configure_tooltip_text(self.bins_install_delete_blockdx_tooltip, blockdx_release_url)
            percent_buff = self.blockdx_utility.binary_percent_download
            dl_string = f"DL: {str(int(percent_buff))}%" if percent_buff else "DL"
            var_blockdx = f"{dl_string}" if self.blockdx_utility.downloading_bin else download_string

        if xlite_boolvar:
            var_xlite = "Delete"
            folder = os.path.join(aio_folder, xlite_bin_path.get(system))
            configure_tooltip_text(self.bins_install_delete_xlite_tooltip, folder)
        else:
            configure_tooltip_text(self.bins_install_delete_xlite_tooltip, xlite_release_url)
            percent_buff = self.xlite_utility.binary_percent_download
            dl_string = f"DL: {str(int(percent_buff))}%" if percent_buff else "DL"
            var_xlite = f"{dl_string}" if self.xlite_utility.downloading_bin else download_string
        self.bins_install_delete_blocknet_string_var.set(var_blocknet)
        self.bins_install_delete_blockdx_string_var.set(var_blockdx)
        self.bins_install_delete_xlite_string_var.set(var_xlite)

        if blocknet_boolvar:
            if self.blocknet_process_running:
                disable_button(self.bins_install_delete_blocknet_button)
            else:
                enable_button(self.bins_install_delete_blocknet_button)
        else:
            if self.blocknet_utility.downloading_bin:
                disable_button(self.bins_install_delete_blocknet_button)
            else:
                enable_button(self.bins_install_delete_blocknet_button)

        if blockdx_boolvar:
            if self.blockdx_process_running:
                disable_button(self.bins_install_delete_blockdx_button)
            else:
                enable_button(self.bins_install_delete_blockdx_button)
        else:
            if self.blockdx_utility.downloading_bin:
                disable_button(self.bins_install_delete_blockdx_button)
            else:
                enable_button(self.bins_install_delete_blockdx_button)

        if xlite_boolvar:
            if self.xlite_process_running:
                disable_button(self.bins_install_delete_xlite_button)
            else:
                enable_button(self.bins_install_delete_xlite_button)
        else:
            if self.xlite_utility.downloading_bin:
                disable_button(self.bins_install_delete_xlite_button)
            else:
                enable_button(self.bins_install_delete_xlite_button)

    def handle_signal(self, signum, frame):
        print("Signal {} received.".format(signum))
        self.on_close()

    def stop_bootstrap_thread(self):
        if self.bootstrap_thread and self.bootstrap_thread.is_alive():
            terminate_thread(self.bootstrap_thread)
            self.bootstrap_thread.join()

    def on_close(self):
        logging.info("Closing application...")
        terminate_all_threads()
        logging.info("Threads terminated.")
        self.destroy()
        logging.info("Tkinter GUI destroyed.")
        # Schedule forced exit after a 5-second timeout
        threading.Timer(interval=1, function=os._exit, args=(0,)).start()

    def switch_theme_command(self):
        actual = ctk.get_appearance_mode()
        if actual == "Dark":
            new_theme = "Light"
        else:
            new_theme = "Dark"
        ctk.set_appearance_mode(new_theme)
        # print(actual, new_theme)

    def setup_bin(self):
        self.bin_title_frame = ctk.CTkFrame(self.bins_download_frame)
        self.bin_title_frame.grid(row=0, column=0, columnspan=5, padx=5, pady=5, sticky="ew")
        self.bins_header_label = ctk.CTkLabel(self.bin_title_frame, text="Binaries Control panel:", width=140,
                                              anchor='w')
        self.bins_header_label.grid(row=0, column=0, columnspan=2, padx=5, pady=0, sticky="nw")
        self.bins_found_label = ctk.CTkLabel(self.bin_title_frame, text="Found:", anchor='s', width=245)
        self.bins_found_label.grid(row=0, column=4, pady=5, sticky='ew')
        # os.path.join(aio_folder, "img", "dark.png")
        resize = (65, 30)

        self.theme_img = ctk.CTkImage(
            light_image=PIL.Image.open(os.path.join(DIRPATH, "img", "light.png")).resize(resize, PIL.Image.LANCZOS),
            dark_image=PIL.Image.open(os.path.join(DIRPATH, "img", "dark.png")).resize(resize, PIL.Image.LANCZOS),
            size=resize)
        bg_color = self.bin_title_frame.cget('fg_color')
        self.bins_button_switch_theme = ctk.CTkButton(self.bin_title_frame,
                                                      image=self.theme_img, command=self.switch_theme_command, text='',
                                                      fg_color=bg_color, hover=False,width=50)
        self.bins_button_switch_theme.grid(row=0, column=5, padx=2, pady=2, sticky='ew')
        # Creating labels
        self.bins_blocknet_label = ctk.CTkLabel(self.bins_download_frame, text="Blocknet Core:")
        self.bins_blockdx_label = ctk.CTkLabel(self.bins_download_frame, text="Block-DX:")
        self.bins_xlite_label = ctk.CTkLabel(self.bins_download_frame, text="Xlite:")
        self.blocknet_bin_installed_boolvar = ctk.BooleanVar(value=False)
        self.blockdx_bin_installed_boolvar = ctk.BooleanVar(value=False)
        self.xlite_bin_installed_boolvar = ctk.BooleanVar(value=False)

        width = 150
        self.bins_blocknet_version_optionmenu = ctk.CTkOptionMenu(self.bins_download_frame,
                                                                  values=self.blocknet_version,
                                                                  width=width,
                                                                  state='disabled')
        self.bins_blockdx_version_optionmenu = ctk.CTkOptionMenu(self.bins_download_frame,
                                                                 values=self.blockdx_version,
                                                                 width=width,
                                                                 state='disabled')
        self.bins_xlite_version_optionmenu = ctk.CTkOptionMenu(self.bins_download_frame,
                                                               values=self.xlite_version,
                                                               width=width,
                                                               state='disabled')
        self.bins_blocknet_found_checkbox = ctkCheckBoxMod.CTkCheckBox(self.bins_download_frame,
                                                                       text='',
                                                                       variable=self.blocknet_bin_installed_boolvar,
                                                                       state='disabled',
                                                                       corner_radius=25, )
        self.bins_blockdx_found_checkbox = ctkCheckBoxMod.CTkCheckBox(self.bins_download_frame,
                                                                      text='',
                                                                      variable=self.blockdx_bin_installed_boolvar,
                                                                      state='disabled',
                                                                      corner_radius=25)
        self.bins_xlite_found_checkbox = ctkCheckBoxMod.CTkCheckBox(self.bins_download_frame,
                                                                    text='',
                                                                    variable=self.xlite_bin_installed_boolvar,
                                                                    state='disabled',
                                                                    corner_radius=25)
        width = 75
        self.bins_install_delete_blocknet_string_var = ctk.StringVar(value='')
        self.bins_install_delete_blocknet_button = ctk.CTkButton(self.bins_download_frame,
                                                                 state='normal',
                                                                 command=self.install_delete_blocknet_command,
                                                                 textvariable=self.bins_install_delete_blocknet_string_var,
                                                                 width=width)
        self.bins_install_delete_blocknet_tooltip = CTkToolTip.CTkToolTip(self.bins_install_delete_blocknet_button,
                                                                          message='', delay=1,
                                                                          follow=True,
                                                                          border_width=2,
                                                                          justify="left")
        self.bins_install_delete_blockdx_string_var = ctk.StringVar(value='')
        self.bins_install_delete_blockdx_button = ctk.CTkButton(self.bins_download_frame,
                                                                state='normal',
                                                                command=self.install_delete_blockdx_command,
                                                                textvariable=self.bins_install_delete_blockdx_string_var,
                                                                width=width)
        self.bins_install_delete_blockdx_tooltip = CTkToolTip.CTkToolTip(self.bins_install_delete_blockdx_button,
                                                                         message=blockdx_release_url, delay=1,
                                                                         follow=True,
                                                                         border_width=2,
                                                                         justify="left")
        self.bins_install_delete_xlite_string_var = ctk.StringVar(value='')
        self.bins_install_delete_xlite_button = ctk.CTkButton(self.bins_download_frame,
                                                              state='normal',
                                                              command=self.install_delete_xlite_command,
                                                              textvariable=self.bins_install_delete_xlite_string_var,
                                                              width=width)
        self.bins_install_delete_xlite_tooltip = CTkToolTip.CTkToolTip(self.bins_install_delete_xlite_button,
                                                                       message=xlite_release_url, delay=1, follow=True,
                                                                       border_width=2,
                                                                       justify="left")
        self.blocknet_start_close_button_string_var = ctk.StringVar(value='')
        self.blocknet_start_close_button = ctk.CTkButton(self.bins_download_frame,
                                                         textvariable=self.blocknet_start_close_button_string_var,
                                                         command=self.start_or_close_blocknet,
                                                         width=width + 12)
        self.blockdx_start_close_button_string_var = ctk.StringVar(value='')
        self.blockdx_start_close_button = ctk.CTkButton(self.bins_download_frame,
                                                        textvariable=self.blockdx_start_close_button_string_var,
                                                        command=self.start_or_close_blockdx,
                                                        width=width + 12)
        self.xlite_start_close_button_string_var = ctk.StringVar(value='')
        self.xlite_start_close_button = ctk.CTkButton(self.bins_download_frame,
                                                      textvariable=self.xlite_start_close_button_string_var,
                                                      command=self.start_or_close_xlite,
                                                      width=width + 12)
        x = 0
        y = 0

        self.bins_blocknet_label.grid(row=x + 1, column=y, padx=5, pady=2, sticky="e")
        self.bins_blockdx_label.grid(row=x + 2, column=y, padx=5, pady=2, sticky="e")
        self.bins_xlite_label.grid(row=x + 3, column=y, padx=5, pady=(2, 5), sticky="e")
        sticky = 'ew'
        self.bins_blocknet_version_optionmenu.grid(row=x + 1, column=y + 1, padx=5, sticky=sticky)
        self.bins_blockdx_version_optionmenu.grid(row=x + 2, column=y + 1, padx=5, sticky=sticky)
        self.bins_xlite_version_optionmenu.grid(row=x + 3, column=y + 1, padx=5, pady=(2, 5), sticky=sticky)
        self.bins_blocknet_found_checkbox.grid(row=x + 1, column=y + 2, padx=5, sticky=sticky)
        self.bins_blockdx_found_checkbox.grid(row=x + 2, column=y + 2, padx=5, sticky=sticky)
        self.bins_xlite_found_checkbox.grid(row=x + 3, column=y + 2, padx=5, pady=(2, 5), sticky=sticky)
        button_sticky = 'e'
        self.bins_install_delete_blocknet_button.grid(row=x + 1, column=y + 3, padx=8, sticky=button_sticky)
        self.bins_install_delete_blockdx_button.grid(row=x + 2, column=y + 3, padx=8, sticky=button_sticky)
        self.bins_install_delete_xlite_button.grid(row=x + 3, column=y + 3, padx=8, pady=(2, 5), sticky=button_sticky)
        self.blocknet_start_close_button.grid(row=x + 1, column=y + 4, padx=(8, 2), sticky='ew')
        # Button for starting or closing Block-dx
        self.blockdx_start_close_button.grid(row=x + 2, column=y + 4, padx=(8, 2), sticky='ew')
        # Button for starting or closing Xlite
        self.xlite_start_close_button.grid(row=x + 3, column=y + 4, padx=(8, 2), pady=(2, 5), sticky='ew')

    def setup_blocknet_core(self):
        # Frame for Data Path label and entry
        self.blocknet_title_frame = ctk.CTkFrame(self.blocknet_core_frame)
        self.blocknet_title_frame.grid(row=0, column=0, columnspan=5, padx=5, pady=5, sticky="ew")
        # Add widgets for Blocknet Core management inside the blocknet_core_frame
        # Label for Blocknet Core frame
        width = 350
        self.blocknet_core_label = ctk.CTkLabel(self.blocknet_title_frame, text=blocknet_frame_title_string,
                                                width=width, anchor="w")
        self.blocknet_core_label.grid(row=0, column=0, columnspan=2, padx=5, pady=0)

        CTkToolTip.CTkToolTip(self.blocknet_core_label, message=tooltip_blocknet_core_label_msg,
                              delay=1.0, border_width=2, follow=True)

        # Label for Data Path
        self.blocknet_data_path_label = ctk.CTkLabel(self.blocknet_title_frame, text="Data Path: ")
        self.blocknet_data_path_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")

        width = 275
        self.blocknet_data_path_entry_string_var = ctk.StringVar(value=self.blocknet_utility.data_folder)
        self.blocknet_data_path_entry = ctk.CTkEntry(self.blocknet_title_frame,
                                                     textvariable=self.blocknet_data_path_entry_string_var,
                                                     state='normal', width=width)
        self.blocknet_data_path_entry.grid(row=1, column=1, padx=(0, 10), pady=5, sticky="ew")
        self.blocknet_data_path_entry.configure(state='readonly')

        # Button for setting custom path
        self.blocknet_custom_path_button = ctk.CTkButton(self.blocknet_title_frame,
                                                         text=blocknet_set_custom_path_string,
                                                         command=self.open_custom_path_dialog,
                                                         width=button_width)
        self.blocknet_custom_path_button.grid(row=1, column=3, padx=2, pady=2, sticky="e")

        # Button for downloading blocknet bootstrap
        self.blocknet_download_bootstrap_string_var = ctk.StringVar(value="Get Bootstrap")
        self.blocknet_download_bootstrap_button = ctk.CTkButton(self.blocknet_title_frame,
                                                                textvariable=self.blocknet_download_bootstrap_string_var,
                                                                command=self.download_bootstrap_command,
                                                                width=button_width)
        self.blocknet_download_bootstrap_button.grid(row=0, column=3, padx=2, pady=2, sticky="e")

        # Checkboxes
        self.blocknet_data_path_status_checkbox_state = ctk.BooleanVar()
        self.blocknet_data_path_status_checkbox_string_var = ctk.StringVar(value="Data Path")
        self.blocknet_data_path_status_checkbox = ctkCheckBoxMod.CTkCheckBox(self.blocknet_core_frame,
                                                                             textvariable=self.blocknet_data_path_status_checkbox_string_var,
                                                                             variable=self.blocknet_data_path_status_checkbox_state,
                                                                             state='disabled',
                                                                             corner_radius=25,
                                                                             width=165)  # , disabledforeground='black')
        self.blocknet_data_path_status_checkbox.grid(row=2, column=0, padx=10, pady=5, sticky="w")

        self.blocknet_process_status_checkbox_state = ctk.BooleanVar()
        self.blocknet_process_status_checkbox_string_var = ctk.StringVar(value='')
        self.blocknet_process_status_checkbox = ctkCheckBoxMod.CTkCheckBox(self.blocknet_core_frame,
                                                                           textvariable=self.blocknet_process_status_checkbox_string_var,
                                                                           variable=self.blocknet_process_status_checkbox_state,
                                                                           state='disabled',
                                                                           corner_radius=25)  # , disabledforeground='black')
        self.blocknet_process_status_checkbox.grid(row=3, column=0, padx=10, pady=5, sticky="w")

        self.blocknet_conf_status_checkbox_state = ctk.BooleanVar()
        self.blocknet_conf_status_checkbox_string_var = ctk.StringVar(value='')
        self.blocknet_conf_status_checkbox = ctkCheckBoxMod.CTkCheckBox(self.blocknet_core_frame,
                                                                        textvariable=self.blocknet_conf_status_checkbox_string_var,
                                                                        variable=self.blocknet_conf_status_checkbox_state,
                                                                        corner_radius=25,
                                                                        state='disabled')  # , disabledforeground='black')
        self.blocknet_conf_status_checkbox.grid(row=2, column=1, padx=10, pady=5, sticky="w")

        self.blocknet_rpc_connection_checkbox_state = ctk.BooleanVar()
        self.blocknet_rpc_connection_checkbox_string_var = ctk.StringVar(value='')
        self.blocknet_rpc_connection_checkbox = ctkCheckBoxMod.CTkCheckBox(self.blocknet_core_frame,
                                                                           textvariable=self.blocknet_rpc_connection_checkbox_string_var,
                                                                           variable=self.blocknet_rpc_connection_checkbox_state,
                                                                           corner_radius=25,
                                                                           state='disabled')  # , disabledforeground='black')
        self.blocknet_rpc_connection_checkbox.grid(row=3, column=1, padx=10, pady=5, sticky="w")

        # Button for starting or closing Blocknet

        # Button for checking config
        # self.blocknet_check_config_button = ctk.CTkButton(self.blocknet_core_frame,
        #                                                   text=check_config_string,
        #                                                   command=self.blocknet_check_config,
        #                                                   width=button_width)
        # self.blocknet_check_config_button.grid(row=3, column=3, sticky="e")

    def setup_blockdx(self):
        self.blockdx_title_frame = ctk.CTkFrame(self.blockdx_frame)
        self.blockdx_title_frame.grid(row=0, column=0, columnspan=2, padx=(5, 2), pady=5, sticky="ew")
        # Label for Block-dx frame
        width = 475
        self.blockdx_label = ctk.CTkLabel(self.blockdx_title_frame, text=blockdx_frame_title_string, width=width,
                                          anchor='w')
        self.blockdx_label.grid(row=0, column=0, padx=5, pady=0)

        CTkToolTip.CTkToolTip(self.blockdx_label, message=tooltip_blockdx_label_msg,
                              delay=1.0, border_width=2, follow=True)
        # Checkboxes
        self.blockdx_process_status_checkbox_state = ctk.BooleanVar()
        self.blockdx_process_status_checkbox_string_var = ctk.StringVar(value='')
        self.blockdx_process_status_checkbox = ctkCheckBoxMod.CTkCheckBox(self.blockdx_frame,
                                                                          textvariable=self.blockdx_process_status_checkbox_string_var,
                                                                          variable=self.blockdx_process_status_checkbox_state,
                                                                          corner_radius=25,
                                                                          state='disabled')
        self.blockdx_process_status_checkbox.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.blockdx_valid_config_checkbox_state = ctk.BooleanVar()
        self.blockdx_valid_config_checkbox_string_var = ctk.StringVar(value='')
        self.blockdx_valid_config_checkbox = ctkCheckBoxMod.CTkCheckBox(self.blockdx_frame,
                                                                        textvariable=self.blockdx_valid_config_checkbox_string_var,
                                                                        variable=self.blockdx_valid_config_checkbox_state,
                                                                        corner_radius=25,
                                                                        state='disabled',
                                                                        width=190)  # , disabledforeground='black')
        self.blockdx_valid_config_checkbox.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # Button for checking config
        # self.blockdx_check_config_button = ctk.CTkButton(self.blockdx_frame, text=check_config_string,
        #                                                  command=self.blockdx_check_config,
        #                                                  width=button_width, state='disabled')
        # self.blockdx_check_config_button.grid(row=1, column=1, sticky="e")

    def setup_xlite(self):
        self.xlite_title_frame = ctk.CTkFrame(self.xlite_frame)
        self.xlite_title_frame.grid(row=0, column=0, columnspan=4, padx=5, pady=5, sticky="ew")
        width = 350
        self.xlite_label = ctk.CTkLabel(self.xlite_title_frame, text=xlite_frame_title_string, width=width, anchor='w')
        self.xlite_label.grid(row=0, column=0, columnspan=2, padx=5, pady=0)

        CTkToolTip.CTkToolTip(self.xlite_label, message=tooltip_xlite_label_msg,
                              delay=1.0, border_width=2, follow=True)
        # Checkboxes
        self.xlite_process_status_checkbox_state = ctk.BooleanVar()
        self.xlite_process_status_checkbox_string_var = ctk.StringVar(value='')
        self.xlite_process_status_checkbox = ctkCheckBoxMod.CTkCheckBox(self.xlite_frame,
                                                                        textvariable=self.xlite_process_status_checkbox_string_var,
                                                                        variable=self.xlite_process_status_checkbox_state,
                                                                        corner_radius=25,
                                                                        state='disabled')
        self.xlite_process_status_checkbox.grid(row=1, column=0, padx=10, pady=5, sticky="w")

        self.xlite_daemon_process_status_checkbox_state = ctk.BooleanVar()
        self.xlite_daemon_process_status_checkbox_string_var = ctk.StringVar(value='')
        self.xlite_daemon_process_status_checkbox = ctkCheckBoxMod.CTkCheckBox(self.xlite_frame,
                                                                               textvariable=self.xlite_daemon_process_status_checkbox_string_var,
                                                                               variable=self.xlite_daemon_process_status_checkbox_state,
                                                                               corner_radius=25,
                                                                               state='disabled')
        self.xlite_daemon_process_status_checkbox.grid(row=2, column=0, padx=10, pady=5, sticky="w")

        self.xlite_reverse_proxy_process_status_checkbox_state = ctk.BooleanVar()
        self.xlite_reverse_proxy_process_status_checkbox_string_var = ctk.StringVar(
            value=xlite_reverse_proxy_not_running_string)
        self.xlite_reverse_proxy_process_status_checkbox = ctkCheckBoxMod.CTkCheckBox(self.xlite_frame,
                                                                                      textvariable=self.xlite_reverse_proxy_process_status_checkbox_string_var,
                                                                                      variable=self.xlite_reverse_proxy_process_status_checkbox_state,
                                                                                      corner_radius=25,
                                                                                      state='disabled')
        self.xlite_valid_config_checkbox_state = ctk.BooleanVar()
        self.xlite_valid_config_checkbox_string_var = ctk.StringVar(value='')
        self.xlite_valid_config_checkbox = ctkCheckBoxMod.CTkCheckBox(self.xlite_frame,
                                                                      textvariable=self.xlite_valid_config_checkbox_string_var,
                                                                      variable=self.xlite_valid_config_checkbox_state,
                                                                      corner_radius=25,
                                                                      state='disabled')
        self.xlite_valid_config_checkbox.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        self.xlite_daemon_valid_config_checkbox_state = ctk.BooleanVar()
        self.xlite_daemon_valid_config_checkbox_string_var = ctk.StringVar(value='')
        self.xlite_daemon_valid_config_checkbox = ctkCheckBoxMod.CTkCheckBox(self.xlite_frame,
                                                                             textvariable=self.xlite_daemon_valid_config_checkbox_string_var,
                                                                             variable=self.xlite_daemon_valid_config_checkbox_state,
                                                                             corner_radius=25,
                                                                             state='disabled')
        self.xlite_daemon_valid_config_checkbox.grid(row=2, column=1, padx=10, pady=5, sticky="ew")

        # Button for refreshing Xlite config data
        # self.xlite_check_config_button_string_var = ctk.StringVar(value=check_config_string)
        # self.xlite_check_config_button = ctk.CTkButton(self.xlite_frame,
        #                                                textvariable=self.xlite_check_config_button_string_var,
        #                                                command=self.refresh_xlite_confs, width=button_width)
        # self.xlite_check_config_button.grid(row=1, column=1, sticky="e")

        # Create the Button widget with a text variable
        self.xlite_store_password_button_string_var = ctk.StringVar(value='')
        self.xlite_store_password_button = ctk.CTkButton(self.xlite_title_frame,
                                                         textvariable=self.xlite_store_password_button_string_var,
                                                         width=button_width)

        self.xlite_store_password_button.grid(row=0, column=3, padx=2, pady=2, sticky="e")
        # Bind left-click event
        self.xlite_store_password_button.bind("<Button-1>",
                                              lambda event: self.xlite_store_password_button_mouse_click(event))

        # Bind right-click event
        self.xlite_store_password_button.bind("<Button-3>",
                                              lambda event: self.xlite_store_password_button_mouse_click(event))

        # Set button command for normal button clicks
        self.xlite_store_password_button.configure(command=self.xlite_store_password_button_mouse_click)

    def xlite_store_password_button_mouse_click(self, event=None):
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
            # self.xlite_store_password_button.configure(relief='raised')
            return "break"

        # For left-click event
        if event and event.num == 1:
            # ask_user_pass
            # store_salted_pass
            logging.info("Left click detected")
            password = ctkInputDialogMod.CTkInputDialog(title="Store XLite Password", text="Enter XLite password:",
                                                        show='*', fg_color="#0f2742",
                                                        entry_text_color="#123149").get_input()
            # password = simpledialog.askstring("Store XLite Password","Enter XLite password:" , show='*')
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
            return "break"

    def refresh_xlite_confs(self):
        self.xlite_utility.parse_xlite_conf()
        self.xlite_utility.parse_xlite_daemon_conf()

    def blocknet_check_config(self):
        use_xlite = bool(self.xlite_utility.xlite_daemon_confs_local)
        if use_xlite:
            xlite_daemon_conf = self.xlite_utility.xlite_daemon_confs_local
        else:
            xlite_daemon_conf = None
        self.blocknet_utility.compare_and_update_local_conf(xlite_daemon_conf)

    def blockdx_check_config(self):
        # Get required data
        if bool(self.blocknet_utility.data_folder and self.blocknet_utility.blocknet_conf_local):
            xbridgeconfpath = os.path.normpath(os.path.join(self.blocknet_utility.data_folder, "xbridge.conf"))
            logging.info(f"xbridgeconfpath: {xbridgeconfpath}")
            rpc_user = self.blocknet_utility.blocknet_conf_local.get('global', {}).get('rpcuser')
            rpc_password = self.blocknet_utility.blocknet_conf_local.get('global', {}).get('rpcpassword')
            self.blockdx_utility.compare_and_update_local_conf(xbridgeconfpath, rpc_user, rpc_password)

    def open_custom_path_dialog(self):
        # ctk.filedialog.askdirectory()
        custom_path = ctk.filedialog.askdirectory(parent=self, title="Select Custom Path for Blocknet Core Datadir",
                                                  mustexist=False)
        if custom_path:
            self.on_custom_path_set(custom_path)

    def on_custom_path_set(self, custom_path):
        self.blocknet_utility.set_custom_data_path(custom_path)
        self.blocknet_data_path_entry_string_var.set(self.blocknet_utility.data_folder)
        save_cfg_json('custom_path', custom_path)

    def enable_blocknet_start_button(self):
        self.disable_start_blocknet_button = False

    def enable_blockdx_start_button(self):
        self.disable_start_blockdx_button = False

    def enable_xlite_start_button(self):
        self.disable_start_xlite_button = False

    def download_bootstrap_command(self):
        disable_button(self.blocknet_download_bootstrap_button)
        self.bootstrap_thread = Thread(target=self.blocknet_utility.download_bootstrap)
        self.bootstrap_thread.daemon = True
        self.bootstrap_thread.start()

    def install_delete_blocknet_command(self):
        blocknet_boolvar = self.blocknet_bin_installed_boolvar.get()
        if blocknet_boolvar:
            self.delete_blocknet_command()
        else:
            self.download_blocknet_command()

    def install_delete_blockdx_command(self):
        blockdx_boolvar = self.blockdx_bin_installed_boolvar.get()
        if blockdx_boolvar:
            self.delete_blockdx_command()
        else:
            self.download_blockdx_command()

    def install_delete_xlite_command(self):
        xlite_boolvar = self.xlite_bin_installed_boolvar.get()
        if xlite_boolvar:
            self.delete_xlite_command()
        else:
            self.download_xlite_command()

    def download_blocknet_command(self):
        disable_button(self.bins_install_delete_blocknet_button)
        self.download_blocknet_thread = Thread(target=self.blocknet_utility.download_blocknet_bin)
        self.download_blocknet_thread.daemon = True
        self.download_blocknet_thread.start()

    def download_blockdx_command(self):
        disable_button(self.bins_install_delete_blockdx_button)
        self.download_blockdx_thread = Thread(target=self.blockdx_utility.download_blockdx_bin)
        self.download_blockdx_thread.daemon = True
        self.download_blockdx_thread.start()

    def download_xlite_command(self):
        disable_button(self.bins_install_delete_xlite_button)
        self.download_xlite_thread = Thread(target=self.xlite_utility.download_xlite_bin)
        self.download_xlite_thread.daemon = True
        self.download_xlite_thread.start()

    def delete_blocknet_command(self):
        blocknet_pruned_version = self.blocknet_version[0].replace('v', '')
        for item in os.listdir(aio_folder):
            item_path = os.path.join(aio_folder, item)
            if os.path.isdir(item_path):
                # if a wrong version is found, delete it.
                if 'blocknet-' in item:
                    if blocknet_pruned_version in item:
                        logging.info(f"deleting {item_path}")
                        shutil.rmtree(item_path)

    def delete_blockdx_command(self):
        if system == 'Darwin':
            self.blockdx_utility.unmount_dmg()
        blockdx_pruned_version = self.blockdx_version[0].replace('v', '')
        for item in os.listdir(aio_folder):
            item_path = os.path.join(aio_folder, item)
            if os.path.isdir(item_path):
                if 'BLOCK-DX-' in item:
                    if blockdx_pruned_version in item:
                        logging.info(f"deleting {item_path}")
                        shutil.rmtree(item_path)

    def delete_xlite_command(self):
        if system == 'Darwin':
            self.xlite_utility.unmount_dmg()
        xlite_pruned_version = self.xlite_version[0].replace('v', '')
        for item in os.listdir(aio_folder):
            item_path = os.path.join(aio_folder, item)
            if os.path.isdir(item_path):
                if 'XLite-' in item:
                    if xlite_pruned_version in item:
                        logging.info(f"deleting {item_path}")
                        shutil.rmtree(item_path)

    def start_or_close_blocknet(self):
        disable_button(self.blocknet_start_close_button)
        self.disable_start_blocknet_button = True
        if self.blocknet_process_running:
            self.blocknet_t1 = Thread(target=self.blocknet_utility.close_blocknet)
            self.blocknet_t1.start()
        else:
            self.blocknet_check_config()
            self.blocknet_t2 = Thread(target=self.blocknet_utility.start_blocknet)
            self.blocknet_t2.start()
        self.after(self.time_disable_button, self.enable_blocknet_start_button)

    def start_or_close_blockdx(self):
        disable_button(self.blockdx_start_close_button)
        self.disable_start_blockdx_button = True
        if self.blockdx_process_running:
            self.blockdx_t1 = Thread(target=self.blockdx_utility.close_blockdx)
            self.blockdx_t1.start()
        else:
            self.blockdx_check_config()
            self.blockdx_t2 = Thread(target=self.blockdx_utility.start_blockdx)
            self.blockdx_t2.start()
        self.after(self.time_disable_button, self.enable_blockdx_start_button)

    def start_or_close_xlite(self):
        disable_button(self.xlite_start_close_button)
        self.disable_start_xlite_button = True
        if self.xlite_process_running:
            self.xlite_t1 = Thread(target=self.xlite_utility.close_xlite)
            self.xlite_t1.start()

        else:
            if self.xlite_password:
                env_vars = [{"CC_WALLET_PASS": self.xlite_password}, {"CC_WALLET_AUTOLOGIN": 'true'}]
            else:
                env_vars = []
            self.xlite_t2 = Thread(target=lambda: self.xlite_utility.start_xlite(env_vars=env_vars))
            self.xlite_t2.start()
        self.after(self.time_disable_button, self.enable_xlite_start_button)

    def update_blocknet_bootstrap_button(self):
        bootstrap_download_in_progress = bool(self.blocknet_utility.checking_bootstrap)
        enabled = (self.blocknet_utility.data_folder and not bootstrap_download_in_progress and
                   not self.blocknet_process_running)
        if enabled:
            enable_button(self.blocknet_download_bootstrap_button)
        else:
            disable_button(self.blocknet_download_bootstrap_button)
        if bootstrap_download_in_progress:
            if self.blocknet_utility.bootstrap_percent_download:
                var = f"Progress: {self.blocknet_utility.bootstrap_percent_download:.1f}%"
            else:
                var = "Loading"
        else:
            var = "Get Bootstrap"
        self.blocknet_download_bootstrap_string_var.set(var)

    def update_blocknet_start_close_button(self):
        # blocknet_start_close_button
        # blocknet_start_close_button_string_var
        var = close_string if self.blocknet_process_running else start_string
        self.blocknet_start_close_button_string_var.set(var)

        enabled = (not self.blocknet_utility.downloading_bin and
                   not self.disable_start_blocknet_button and
                   not self.blocknet_utility.checking_bootstrap)
        # logging.debug(
        #     f"blocknet_utility.downloading_bin: {self.blocknet_utility.downloading_bin}"
        #     f", self.disable_start_blocknet_button: {self.disable_start_blocknet_button}, enabled: {enabled}"
        # )
        if enabled:
            enable_button(self.blocknet_start_close_button)
        else:
            disable_button(self.blocknet_start_close_button)

    def update_blocknet_process_status_checkbox(self):
        # blocknet_process_status_checkbox_string_var
        var = blocknet_running_string if self.blocknet_process_running else blocknet_not_running_string
        self.blocknet_process_status_checkbox_string_var.set(var)
        # blocknet_process_status_checkbox_state
        self.blocknet_process_status_checkbox_state.set(self.blocknet_process_running)

    def update_blocknet_custom_path_button(self):
        # blocknet_custom_path_button
        bootstrap_download_in_progress = (
                self.blocknet_utility.checking_bootstrap or self.blocknet_utility.bootstrap_percent_download)
        condition = (not self.blocknet_process_running and not bootstrap_download_in_progress)
        if condition:
            enable_button(self.blocknet_custom_path_button)
        else:
            disable_button(self.blocknet_custom_path_button)

    def update_blocknet_conf_status_checkbox(self):
        # blocknet_conf_status_checkbox_state
        conf_exist_and_parsed = bool(
            self.blocknet_utility.blocknet_conf_local and self.blocknet_utility.xbridge_conf_local)
        self.blocknet_conf_status_checkbox_state.set(conf_exist_and_parsed)

        # blocknet_conf_status_checkbox_string_var

        var = blocknet_valid_config_string if conf_exist_and_parsed else blocknet_not_valid_config_string
        self.blocknet_conf_status_checkbox_string_var.set(var)

    def update_blocknet_data_path_status_checkbox(self):
        # blocknet_data_path_status_checkbox_state
        exist = self.blocknet_utility.check_data_folder_existence()
        self.blocknet_data_path_status_checkbox_state.set(exist)

        # blocknet_data_path_status_checkbox_string_var
        var = blocknet_data_path_created_string if exist else blocknet_data_path_notfound_string
        self.blocknet_data_path_status_checkbox_string_var.set(var)

    def update_blocknet_rpc_connection_checkbox(self):
        # blocknet_rpc_connection_checkbox_state
        self.blocknet_rpc_connection_checkbox_state.set(self.blocknet_utility.valid_rpc)

        # blocknet_rpc_connection_checkbox_string_var
        var = blocknet_active_rpc_string if self.blocknet_utility.valid_rpc else blocknet_inactive_rpc_string
        self.blocknet_rpc_connection_checkbox_string_var.set(var)

    def update_blockdx_process_status_checkbox(self):
        # blockdx_process_status_checkbox_state
        self.blockdx_process_status_checkbox_state.set(self.blockdx_process_running)

        # blockdx_process_status_checkbox_string_var
        var = blockdx_running_string if self.blockdx_process_running else blockdx_not_running_string
        # , PIDs: {self.blockdx_utility.blockdx_pids}
        self.blockdx_process_status_checkbox_string_var.set(var)

    def update_blockdx_start_close_button(self):
        # blockdx_start_close_button_string_var
        var = close_string if self.blockdx_process_running else start_string
        self.blockdx_start_close_button_string_var.set(var)

        enabled = (self.blockdx_process_running or (not self.blockdx_utility.downloading_bin and
                                                    self.blocknet_utility.valid_rpc) and
                   not self.disable_start_blockdx_button)
        if enabled:
            enable_button(self.blockdx_start_close_button)
        else:
            disable_button(self.blockdx_start_close_button)

    def update_blockdx_config_button_checkbox(self):
        # blockdx_valid_config_checkbox_state
        # blockdx_check_config_button
        valid_core_setup = bool(self.blocknet_utility.data_folder) and bool(self.blocknet_utility.blocknet_conf_local)
        if valid_core_setup and self.blocknet_utility.valid_rpc:
            var = blockdx_valid_config_string if self.is_blockdx_config_sync else blockdx_not_valid_config_string
            self.blockdx_valid_config_checkbox_string_var.set(var)
        else:
            self.blockdx_valid_config_checkbox_string_var.set(blockdx_missing_blocknet_config_string)

        if valid_core_setup:
            xbridgeconfpath = os.path.join(self.blocknet_utility.data_folder, "xbridge.conf")
            rpc_user = self.blocknet_utility.blocknet_conf_local.get('global', {}).get('rpcuser')
            rpc_password = self.blocknet_utility.blocknet_conf_local.get('global', {}).get('rpcpassword')

            # blockdx_valid_config_checkbox_state
            blockdx_conf = self.blockdx_utility.blockdx_conf_local
            self.is_blockdx_config_sync = (
                    bool(blockdx_conf) and
                    blockdx_conf.get('user') == rpc_user and
                    blockdx_conf.get('password') == rpc_password and
                    blockdx_conf.get('xbridgeConfPath') == xbridgeconfpath and
                    isinstance(blockdx_conf.get('selectedWallets'), list) and
                    blockdx_selectedWallets_blocknet in blockdx_conf.get('selectedWallets', [])
            )
            self.blockdx_valid_config_checkbox_state.set(
                (self.is_blockdx_config_sync and self.blocknet_utility.valid_rpc))

        else:
            self.blockdx_valid_config_checkbox_state.set(False)

    def update_xlite_process_status_checkbox(self):
        # xlite_process_status_checkbox_state
        self.xlite_process_status_checkbox_state.set(self.xlite_process_running)

        # xlite_process_status_checkbox_string_var
        var = xlite_running_string if self.xlite_process_running else xlite_not_running_string
        # , PIDs: {self.xlite_utility.xlite_pids}
        self.xlite_process_status_checkbox_string_var.set(var)

    def update_xlite_start_close_button(self):
        # xlite_start_close_button_string_var
        var = close_string if self.xlite_process_running else start_string
        self.xlite_start_close_button_string_var.set(var)

        # xlite_start_close_button
        disable_start_close_button = self.xlite_utility.downloading_bin or self.disable_start_xlite_button
        if not disable_start_close_button:
            enable_button(self.xlite_start_close_button)
        else:
            disable_button(self.xlite_start_close_button)

    def update_xlite_store_password_button(self):
        # xlite_store_password_button
        var = xlite_stored_password_string if self.xlite_password else xlite_store_password_string
        self.xlite_store_password_button_string_var.set(var)
        # self.xlite_store_password_button.configure(relief='raised' if not self.xlite_password else 'sunken')

    def update_xlite_daemon_process_status(self):
        # xlite_daemon_process_status_checkbox_state
        self.xlite_daemon_process_status_checkbox_state.set(self.xlite_daemon_process_running)

        # xlite_daemon_process_status_checkbox_string_var
        var = xlite_daemon_running_string if self.xlite_daemon_process_running else xlite_daemon_not_running_string
        # , PIDs: {self.xlite_utility.xlite_daemon_pids}
        self.xlite_daemon_process_status_checkbox_string_var.set(var)

    def update_xlite_valid_config_checkbox(self):
        # xlite_valid_config_checkbox_state
        valid_config = True if self.xlite_utility.xlite_conf_local else False
        self.xlite_valid_config_checkbox_state.set(valid_config)
        # self.xlite_valid_config_checkbox_string_var
        var = xlite_valid_config_string if valid_config else xlite_not_valid_config_string
        self.xlite_valid_config_checkbox_string_var.set(var)

    def update_xlite_daemon_valid_config_checkbox(self):
        # xlite_daemon_valid_config_checkbox_state
        valid_config = True if (self.xlite_utility.xlite_daemon_confs_local and
                                'master' in self.xlite_utility.xlite_daemon_confs_local) else False
        self.xlite_daemon_valid_config_checkbox_state.set(valid_config)
        # self.xlite_daemon_valid_config_checkbox_string_var

        var = xlite_daemon_valid_config_string if valid_config else xlite_daemon_not_valid_config_string
        self.xlite_daemon_valid_config_checkbox_string_var.set(var)

    async def coroutine_update_status_blocknet_core(self):
        self.update_blocknet_bootstrap_button()
        self.update_blocknet_start_close_button()
        self.update_blocknet_process_status_checkbox()
        self.update_blocknet_custom_path_button()
        self.update_blocknet_conf_status_checkbox()
        self.update_blocknet_data_path_status_checkbox()
        self.update_blocknet_rpc_connection_checkbox()

    async def coroutine_update_status_blockdx(self):
        self.update_blockdx_process_status_checkbox()
        self.update_blockdx_start_close_button()
        self.update_blockdx_config_button_checkbox()

    def detect_new_xlite_install_and_add_to_xbridge(self):
        # logging.info(f"detect_new_xlite_install_and_add_to_xbridge, valid_coins_rpc: {self.xlite_utility.valid_coins_rpc}, disable_daemons_conf_check: {self.disable_daemons_conf_check}")
        if not self.disable_daemons_conf_check and self.xlite_utility.valid_coins_rpc:
            self.blocknet_utility.check_xbridge_conf(self.xlite_utility.xlite_daemon_confs_local)
            if self.blocknet_process_running and self.blocknet_utility.valid_rpc:
                logging.debug("dxloadxbridgeConf")
                self.blocknet_utility.blocknet_rpc.send_rpc_request("dxloadxbridgeConf")
            self.disable_daemons_conf_check = True
        if self.disable_daemons_conf_check and not self.xlite_utility.valid_coins_rpc:
            self.disable_daemons_conf_check = False

    async def coroutine_update_status_xlite(self):
        self.detect_new_xlite_install_and_add_to_xbridge()
        self.update_xlite_process_status_checkbox()
        self.update_xlite_start_close_button()
        self.update_xlite_store_password_button()
        self.update_xlite_daemon_process_status()
        self.update_xlite_valid_config_checkbox()
        self.update_xlite_daemon_valid_config_checkbox()

    def update_status(self):
        # Define an async function to run the coroutines concurrently
        async def update_status_async():
            coroutines = [
                self.coroutine_update_status_blocknet_core(),
                self.coroutine_update_status_blockdx(),
                self.coroutine_update_status_xlite(),
                self.coroutine_update_bins_buttons()
            ]
            if self.bins_should_check_aio_folder(max_delay=3.33):
                coroutines.append(self.coroutine_bins_check_aio_folder())
            if self.should_check_processes(max_delay=3.33):
                coroutines.append(self.coroutine_check_processes())

            await asyncio.gather(*coroutines)

        # Run the async function using asyncio.run() to execute the coroutines
        asyncio.run(update_status_async())
        # Schedule the next update
        self.after(1000, self.update_status)

    def bins_should_check_aio_folder(self, max_delay=5):
        current_time = time.time()
        if not self.bins_last_aio_folder_check_time or current_time - self.bins_last_aio_folder_check_time >= max_delay:
            self.bins_last_aio_folder_check_time = current_time
            return True
        return False

    def should_check_processes(self, max_delay=5):
        current_time = time.time()
        if not self.last_process_check_time or current_time - self.last_process_check_time >= max_delay:
            self.last_process_check_time = current_time
            return True
        return False

    async def coroutine_check_processes(self):
        # start_time = time.time()
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
                logging.info(f"Block-DX process has terminated with return code {process_status}")
                self.blockdx_utility.blockdx_process = None

        # Check Xlite process
        if self.xlite_utility.xlite_process is not None:
            process_status = self.xlite_utility.xlite_process.poll()
            if process_status is not None:
                logging.info(f"XLite process has terminated with return code {process_status}")
                self.xlite_utility.xlite_process = None

        # Check Xlite process
        if self.xlite_utility.xlite_daemon_process is not None:
            process_status = self.xlite_utility.xlite_daemon_process.poll()
            if process_status is not None:
                logging.info(f"XLite-daemon process has terminated with return code {process_status}")
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


def configure_tooltip_text(tooltip, msg):
    if tooltip.get() != msg:
        tooltip.configure(message=msg)


def boolvar_to_button_state(boolvar):
    if boolvar.get() is True:
        return ctk.NORMAL
    elif boolvar.get() is False:
        return ctk.DISABLED
    else:
        logging.error(f"boolvar_to_button_state error, boolvar: {boolvar}")


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


def terminate_all_threads():
    logging.info("Terminating all threads...")
    for thread in threading.enumerate():
        if thread != threading.current_thread():
            logging.info(f"Terminating thread: {thread.name}")
            thread.join(timeout=0.25)  # Terminate thread
            logging.info(f"Thread {thread.name} terminated")


def terminate_thread(thread):
    """Terminates a python thread from another thread."""
    if not thread.is_alive():
        return

    exc = ctypes.py_object(SystemExit)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(thread.ident), exc)
    if res == 0:
        raise ValueError("nonexistent thread id")
    elif res > 1:
        # "if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


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
    if button.cget("state") == ctk.DISABLED:
        button.configure(state=ctk.NORMAL)


def disable_button(button):
    if button.cget("state") == ctk.NORMAL:
        button.configure(state=ctk.DISABLED)


def run_gui():
    app = BlocknetGUI()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("GUI execution terminated by user.")
        app.on_close()
        # sys.exit(0)
    except Exception as e:
        # Log the error to a file
        logging.basicConfig(filename='gui_errors.log', level=logging.ERROR,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        logging.error("An error occurred: %s", e)

        # Print a user-friendly error message
        print("An unexpected error occurred. Please check the log file 'gui_errors.log' for more information.")
        app.on_close()


if __name__ == "__main__":
    run_gui()
    # cProfile.run('run_gui()', filename='profile_stats.txt')
