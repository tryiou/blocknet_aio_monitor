import asyncio
import logging
import os
import shutil
import signal
import time
from threading import Thread

import CTkToolTip
import PIL._tkinter_finder
import customtkinter as ctk
from PIL import Image
from psutil import process_iter

from utilities import global_variables
from utilities import utils
import widgets_strings
from gui.binary_manager import BinaryManager
from gui.block_dx_manager import BlockDXManager
from gui.blocknet_core_manager import BlocknetManager
from gui.xlite_manager import XliteManager

asyncio_logger = logging.getLogger('asyncio')
asyncio_logger.setLevel(logging.WARNING)
pil_logger = logging.getLogger('PIL')
pil_logger.setLevel(logging.WARNING)
from gui.constants import tooltip_bg_color

ctk.set_default_color_theme(global_variables.themepath)


class Blocknet_AIO_GUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.install_greyed_img = None
        self.install_img = None
        self.delete_greyed_img = None
        self.delete_img = None
        self.stop_greyed_img = None
        self.stop_img = None
        self.start_greyed_img = None
        self.start_img = None
        self.transparent_img = None
        self.theme_img = None
        self.xlite_version = [global_variables.xlite_release_url.split('/')[7]]

        self.last_process_check_time = None
        self.disable_daemons_conf_check = False

        # threads
        self.update_status_process_folder_thread = None
        self.update_status_gui_thread = None
        self.blocknet_t1 = None
        self.blocknet_t2 = None
        self.xlite_t2 = None
        self.xlite_t1 = None
        self.blockdx_t2 = None
        self.blockdx_t1 = None

        self.cfg = utils.load_cfg_json()
        self.adjust_theme()
        self.custom_path = None
        self.xlite_password = None
        if self.cfg:
            if 'custom_path' in self.cfg:
                self.custom_path = self.cfg['custom_path']
            if 'salt' in self.cfg and 'xl_pass' in self.cfg:
                try:
                    self.xlite_password = utils.decrypt_password(self.cfg['xl_pass'], self.cfg['salt'].encode())
                except Exception as e:
                    logging.error(f"Error decrypting XLite password: {e}")
                    self.xlite_password = None

        self.binary_manager = None
        self.blocknet_manager = None
        self.blockdx_manager = None
        self.xlite_manager = None

        self.time_disable_button = 3000

        # frames
        self.bins_download_frame = None
        self.bins_title_frame = None
        self.blocknet_core_frame = None
        self.blocknet_title_frame = None
        self.blockdx_frame = None
        self.blockdx_title_frame = None
        self.xlite_frame = None
        self.xlite_title_frame = None

        self.init_setup()

    def setup_management_sections(self):
        self.blocknet_manager.setup()
        self.binary_manager.setup()
        self.blockdx_manager.setup()
        self.xlite_manager.setup()

    def create_managers(self):
        self.blocknet_manager = BlocknetManager(self, self.blocknet_core_frame, self.blocknet_title_frame)
        self.binary_manager = BinaryManager(self, self.bins_download_frame, self.bins_title_frame)
        self.blockdx_manager = BlockDXManager(self, self.blockdx_frame, self.blockdx_title_frame)
        self.xlite_manager = XliteManager(self, self.xlite_frame, self.xlite_title_frame)

    def init_setup(self):
        self.title(widgets_strings.app_title_string)
        self.resizable(False, False)
        self.setup_load_images()
        self.init_frames()
        self.create_managers()
        self.setup_management_sections()
        self.setup_tooltips()
        self.init_grid()

        self.update_status_gui_thread = Thread(target=self.update_status_gui, daemon=True)
        self.update_status_gui_thread.start()

        self.update_status_process_folder_thread = Thread(target=self.update_status_process_folder, daemon=True)
        self.update_status_process_folder_thread.start()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def init_frames(self):
        self.bins_download_frame = ctk.CTkFrame(master=self)
        self.bins_title_frame = ctk.CTkFrame(self.bins_download_frame)

        self.blocknet_core_frame = ctk.CTkFrame(master=self)
        self.blocknet_title_frame = ctk.CTkFrame(self.blocknet_core_frame)

        self.blockdx_frame = ctk.CTkFrame(master=self)
        self.blockdx_title_frame = ctk.CTkFrame(self.blockdx_frame)

        self.xlite_frame = ctk.CTkFrame(master=self)
        self.xlite_title_frame = ctk.CTkFrame(self.xlite_frame)

    def setup_load_images(self):
        resize = (65, 30)
        self.theme_img = ctk.CTkImage(
            light_image=PIL.Image.open(os.path.join(global_variables.DIRPATH, "img", "light.png")).resize(resize,
                                                                                                          PIL.Image.LANCZOS),
            dark_image=PIL.Image.open(os.path.join(global_variables.DIRPATH, "img", "dark.png")).resize(resize,
                                                                                                        PIL.Image.LANCZOS),
            size=resize)
        resize = (50, 50)
        self.transparent_img = ctk.CTkImage(
            light_image=PIL.Image.open(os.path.join(global_variables.DIRPATH, "img", "transparent.png")).resize(resize,
                                                                                                                PIL.Image.LANCZOS))
        self.start_img = ctk.CTkImage(
            light_image=PIL.Image.open(os.path.join(global_variables.DIRPATH, "img", "start-50.png")).resize(resize,
                                                                                                             PIL.Image.LANCZOS))
        self.start_greyed_img = ctk.CTkImage(
            light_image=PIL.Image.open(os.path.join(global_variables.DIRPATH, "img", "start-50_greyed.png")).resize(
                resize,
                PIL.Image.LANCZOS))
        self.stop_img = ctk.CTkImage(
            light_image=PIL.Image.open(os.path.join(global_variables.DIRPATH, "img", "stop-50.png")).resize(resize,
                                                                                                            PIL.Image.LANCZOS))
        self.stop_greyed_img = ctk.CTkImage(
            light_image=PIL.Image.open(os.path.join(global_variables.DIRPATH, "img", "stop-50_greyed.png")).resize(
                resize,
                PIL.Image.LANCZOS))
        self.delete_img = ctk.CTkImage(
            light_image=PIL.Image.open(os.path.join(global_variables.DIRPATH, "img", "delete-50.png")).resize(resize,
                                                                                                              PIL.Image.LANCZOS))
        self.delete_greyed_img = ctk.CTkImage(
            light_image=PIL.Image.open(os.path.join(global_variables.DIRPATH, "img", "delete-50_greyed.png")).resize(
                resize,
                PIL.Image.LANCZOS))
        self.install_img = ctk.CTkImage(
            light_image=PIL.Image.open(os.path.join(global_variables.DIRPATH, "img", "installer-50.png")).resize(resize,
                                                                                                                 PIL.Image.LANCZOS))
        self.install_greyed_img = ctk.CTkImage(
            light_image=PIL.Image.open(os.path.join(global_variables.DIRPATH, "img", "installer-50_greyed.png")).resize(
                resize,
                PIL.Image.LANCZOS))

    def setup_tooltips(self):
        CTkToolTip.CTkToolTip(self.blocknet_core_frame, message=widgets_strings.tooltip_howtouse, delay=1, follow=True,
                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        CTkToolTip.CTkToolTip(self.blockdx_frame, message=widgets_strings.tooltip_howtouse, delay=1, follow=True,
                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        CTkToolTip.CTkToolTip(self.xlite_frame, message=widgets_strings.tooltip_howtouse, delay=1, follow=True,
                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        CTkToolTip.CTkToolTip(self.bins_download_frame, message=widgets_strings.tooltip_howtouse, delay=1, follow=True,
                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        CTkToolTip.CTkToolTip(self.bins_title_frame, message=widgets_strings.tooltip_bins_title_msg, delay=1,
                              follow=True,
                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        CTkToolTip.CTkToolTip(self.binary_manager.frame_manager.bins_header_label,
                              message=widgets_strings.tooltip_bins_title_msg,
                              delay=1,
                              follow=True,
                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        CTkToolTip.CTkToolTip(self.xlite_manager.frame_manager.xlite_label,
                              message=widgets_strings.tooltip_xlite_label_msg,
                              delay=1.0,
                              border_width=2, follow=True,
                              bg_color=tooltip_bg_color)
        CTkToolTip.CTkToolTip(self.binary_manager.frame_manager.bins_blocknet_label,
                              message=widgets_strings.tooltip_blocknet_core_label_msg, delay=1, follow=True,
                              bg_color=tooltip_bg_color,
                              border_width=2, justify="left")
        CTkToolTip.CTkToolTip(self.binary_manager.frame_manager.bins_blockdx_label,
                              message=widgets_strings.tooltip_blockdx_label_msg,
                              delay=1,
                              follow=True,
                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        CTkToolTip.CTkToolTip(self.binary_manager.frame_manager.bins_xlite_label,
                              message=widgets_strings.tooltip_xlite_label_msg,
                              delay=1,
                              follow=True,
                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        self.binary_manager.frame_manager.bins_install_delete_blocknet_tooltip = CTkToolTip.CTkToolTip(
            self.binary_manager.frame_manager.bins_install_delete_blocknet_button,
            message='', delay=1, width=1, follow=True,
            bg_color=tooltip_bg_color,
            border_width=2, justify="left")
        self.binary_manager.frame_manager.bins_install_delete_blockdx_tooltip = CTkToolTip.CTkToolTip(
            self.binary_manager.frame_manager.bins_install_delete_blockdx_button,
            message=global_variables.blockdx_release_url,
            delay=1, width=1, follow=True,
            bg_color=tooltip_bg_color,
            border_width=2, justify="left")
        self.binary_manager.frame_manager.bins_install_delete_xlite_tooltip = CTkToolTip.CTkToolTip(
            self.binary_manager.frame_manager.bins_install_delete_xlite_button,
            message=global_variables.xlite_release_url,
            delay=1, follow=True, bg_color=tooltip_bg_color,
            border_width=2, justify="left")
        self.binary_manager.frame_manager.blocknet_start_close_button_tooltip = CTkToolTip.CTkToolTip(
            self.binary_manager.frame_manager.bin_blocknet_start_close_button,
            delay=1, follow=True,
            bg_color=tooltip_bg_color,
            border_width=2, justify="left")
        self.binary_manager.frame_manager.blockdx_start_close_button_tooltip = CTkToolTip.CTkToolTip(
            self.binary_manager.frame_manager.blockdx_start_close_button,
            delay=1, follow=True,
            bg_color=tooltip_bg_color,
            border_width=2, justify="left")
        self.binary_manager.frame_manager.xlite_start_close_button_tooltip = CTkToolTip.CTkToolTip(
            self.binary_manager.frame_manager.xlite_start_close_button,
            delay=1, follow=True,
            bg_color=tooltip_bg_color,
            border_width=2, justify="left")
        CTkToolTip.CTkToolTip(self.blocknet_manager.frame_manager.blocknet_core_label,
                              message=widgets_strings.tooltip_blocknet_core_label_msg,
                              delay=1.0, border_width=2, follow=True, bg_color=tooltip_bg_color)

        CTkToolTip.CTkToolTip(self.blockdx_manager.frame_manager.blockdx_label,
                              message=widgets_strings.tooltip_blockdx_label_msg,
                              delay=1.0, border_width=2, follow=True, bg_color=tooltip_bg_color)

    def init_grid(self):
        x = 0
        y = 0
        padx_main_frame = 10
        pady_main_frame = 5
        check_boxes_sticky = "ew"
        self.grid_frames(x, y, padx_main_frame, pady_main_frame)
        self.binary_manager.frame_manager.grid_widgets(x, y)
        self.blocknet_manager.frame_manager.grid_widgets(x, y, check_boxes_sticky)
        self.blockdx_manager.frame_manager.grid_widgets(x, y, check_boxes_sticky)
        self.xlite_manager.frame_manager.grid_widgets(x, y, check_boxes_sticky)

    def grid_frames(self, x, y, padx_main_frame, pady_main_frame):
        self.bins_download_frame.grid(row=x, column=y, padx=padx_main_frame, pady=pady_main_frame, sticky="nsew")
        self.bins_title_frame.grid(row=x, column=y, columnspan=5, padx=5, pady=5, sticky="ew")

        self.blocknet_core_frame.grid(row=x + 1, column=y, padx=padx_main_frame, pady=pady_main_frame, sticky="nsew")
        self.blocknet_title_frame.grid(row=x, column=y, columnspan=5, padx=5, pady=5, sticky="ew")

        self.blockdx_frame.grid(row=x + 2, column=y, padx=padx_main_frame, pady=pady_main_frame, sticky="nsew")
        self.blockdx_title_frame.grid(row=0, column=0, columnspan=3, padx=(5, 2), pady=5, sticky="ew")

        self.xlite_frame.grid(row=x + 3, column=y, padx=padx_main_frame, pady=pady_main_frame, sticky="nsew")
        self.xlite_title_frame.grid(row=0, column=0, columnspan=4, padx=5, pady=5, sticky="ew")

    def handle_signal(self, signum, frame):
        print("Signal {} received.".format(signum))
        self.on_close()

    def on_close(self):
        logging.info("Closing application...")
        utils.terminate_all_threads()
        logging.info("Threads terminated.")
        os._exit(0)

    def adjust_theme(self):
        if self.cfg and 'theme' in self.cfg:
            actual = ctk.get_appearance_mode()
            if self.cfg['theme'] != actual:
                if actual == "Dark":
                    new_theme = "Light"
                else:
                    new_theme = "Dark"
                ctk.set_appearance_mode(new_theme)

    def switch_theme_command(self):
        actual = ctk.get_appearance_mode()
        if actual == "Dark":
            new_theme = "Light"
        else:
            new_theme = "Dark"
        ctk.set_appearance_mode(new_theme)
        utils.save_cfg_json("theme", new_theme)

    def update_status_gui(self):
        async def run_coroutine(coroutine_func, delay=1):
            while True:
                await coroutine_func()
                await asyncio.sleep(delay)

        # Define a separate async function to run all coroutines
        async def run_all_coroutines():
            await asyncio.gather(
                run_coroutine(self.blocknet_manager.frame_manager.coroutine_update_status_blocknet_core),
                run_coroutine(self.blockdx_manager.frame_manager.coroutine_update_status_blockdx),
                run_coroutine(self.xlite_manager.frame_manager.coroutine_update_status_xlite),
                run_coroutine(self.binary_manager.frame_manager.coroutine_update_bins_buttons)
            )

        # Run all coroutines within the asyncio event loop
        asyncio.run(run_all_coroutines())

    def update_status_process_folder(self):
        async def run_coroutine(coroutine_func, delay=1):
            while True:
                await coroutine_func()
                await asyncio.sleep(delay)

        # Define a separate async function to run all coroutines
        async def run_all_coroutines():
            await asyncio.gather(
                run_coroutine(self.coroutine_bins_check_aio_folder, delay=2),
                run_coroutine(self.coroutine_check_processes, delay=2)
            )

        # Run all coroutines within the asyncio event loop
        asyncio.run(run_all_coroutines())

    def should_check_processes(self, max_delay=5):
        current_time = time.time()
        if not self.last_process_check_time or current_time - self.last_process_check_time >= max_delay:
            self.last_process_check_time = current_time
            return True
        return False

    async def coroutine_bins_check_aio_folder(self):
        blocknet_pruned_version = self.blocknet_manager.blocknet_version[0].replace('v', '')
        blockdx_pruned_version = self.blockdx_manager.blockdx_version[0].replace('v', '')
        xlite_pruned_version = self.xlite_version[0].replace('v', '')

        blocknet_present = False
        blockdx_present = False
        xlite_present = False

        for item in os.listdir(global_variables.aio_folder):
            if global_variables.system == "Darwin":
                blockdx_filename = os.path.basename(global_variables.blockdx_release_url)
                xlite_filename = os.path.basename(global_variables.xlite_release_url)
                item_path = os.path.join(global_variables.aio_folder, item)
                if os.path.isdir(item_path):
                    if 'blocknet-' in item:
                        if blocknet_pruned_version in item:
                            blocknet_present = True
                        else:
                            logging.info(f"deleting outdated version: {item_path}")
                            shutil.rmtree(item_path)
                elif os.path.isfile(item_path):
                    if 'BLOCK-DX-' in item:
                        if blockdx_filename in item:
                            blockdx_present = True
                        else:
                            logging.info(f"deleting outdated version: {item_path}")
                            os.remove(item_path)
                    elif 'XLite-' in item:
                        if xlite_filename in item:
                            xlite_present = True
                        else:
                            logging.info(f"deleting outdated version: {item_path}")
                            os.remove(item_path)
            else:
                item_path = os.path.join(global_variables.aio_folder, item)
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

        self.binary_manager.frame_manager.blocknet_bin_installed_boolvar.set(blocknet_present)
        self.binary_manager.frame_manager.blockdx_bin_installed_boolvar.set(blockdx_present)
        self.binary_manager.frame_manager.xlite_bin_installed_boolvar.set(xlite_present)
        self.binary_manager.frame_manager.bins_last_aio_folder_check_time = time.time()

    async def coroutine_check_processes(self):
        # Check Blocknet process
        if self.blocknet_manager.utility.blocknet_process is not None:
            process_status = self.blocknet_manager.utility.blocknet_process.poll()
            if process_status is not None:
                logging.info(f"Blocknet process has terminated with return code {process_status}")
                self.blocknet_manager.utility.blocknet_process = None

        # Check Block DX process
        if self.blockdx_manager.utility.blockdx_process is not None:
            process_status = self.blockdx_manager.utility.blockdx_process.poll()
            if process_status is not None:
                logging.info(f"Block-DX process has terminated with return code {process_status}")
                self.blockdx_manager.utility.blockdx_process = None

        # Check Xlite process
        if self.xlite_manager.utility.xlite_process is not None:
            process_status = self.xlite_manager.utility.xlite_process.poll()
            if process_status is not None:
                logging.info(f"XLite process has terminated with return code {process_status}")
                self.xlite_manager.utility.xlite_process = None

        # Check Xlite process
        if self.xlite_manager.utility.xlite_daemon_process is not None:
            process_status = self.xlite_manager.utility.xlite_daemon_process.poll()
            if process_status is not None:
                logging.info(f"XLite-daemon process has terminated with return code {process_status}")
                self.xlite_manager.utility.xlite_daemon_process = None

        blocknet_processes = []
        blockdx_processes = []
        xlite_processes = []
        xlite_daemon_processes = []

        try:
            # Get all processes
            for proc in process_iter(['pid', 'name']):
                # Check if any process matches the Blocknet process name
                if global_variables.blocknet_bin == proc.info['name']:
                    blocknet_processes.append(proc.info['pid'])
                # Check if any process matches the Block DX process name
                if (global_variables.blockdx_bin[
                    -1] if global_variables.system == "Darwin" else global_variables.blockdx_bin) == proc.info['name']:
                    blockdx_processes.append(proc.info['pid'])
                # Check if any process matches the Xlite process name
                if (global_variables.xlite_bin[
                    -1] if global_variables.system == "Darwin" else global_variables.xlite_bin) == proc.info['name']:
                    xlite_processes.append(proc.info['pid'])
                # Check if any process matches the Xlite-daemon process name
                if global_variables.xlite_daemon_bin == proc.info['name']:
                    xlite_daemon_processes.append(proc.info['pid'])
        except Exception as e:
            logging.warning(f"Error while checking processes: {e}")

        # Update Blocknet process status and store the PIDs
        self.blocknet_manager.blocknet_process_running = bool(blocknet_processes)
        self.blocknet_manager.utility.blocknet_pids = blocknet_processes

        # Update Block DX process status and store the PIDs
        self.blockdx_manager.blockdx_process_running = bool(blockdx_processes)
        self.blockdx_manager.utility.blockdx_pids = blockdx_processes

        # Update Xlite process status and store the PIDs
        self.xlite_manager.xlite_process_running = bool(xlite_processes)
        self.xlite_manager.utility.xlite_pids = xlite_processes

        # Update Xlite-daemon process status and store the PIDs
        self.xlite_manager.xlite_daemon_process_running = bool(xlite_daemon_processes)
        self.xlite_manager.utility.xlite_daemon_pids = xlite_daemon_processes


def run_gui():
    app = Blocknet_AIO_GUI()
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("GUI execution terminated by user.")
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
