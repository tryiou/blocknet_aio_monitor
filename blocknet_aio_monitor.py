import asyncio
import logging
import os
import signal

import PIL._tkinter_finder
import customtkinter as ctk
from PIL import Image
from psutil import process_iter

import widgets_strings
from gui.binary_manager import BinaryManager
from gui.blockdx_manager import BlockDXManager
from gui.blocknet_manager import BlocknetManager
from gui.tooltip_manager import TooltipManager
from gui.xlite_manager import XliteManager
from utilities import global_variables
from utilities import utils

asyncio_logger = logging.getLogger('asyncio')
asyncio_logger.setLevel(logging.WARNING)
pil_logger = logging.getLogger('PIL')
pil_logger.setLevel(logging.WARNING)
from gui.constants import tooltip_bg_color, MAIN_FRAMES_STICKY, TITLE_FRAMES_STICKY

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

        self.disable_daemons_conf_check = False

        self.cfg = utils.load_cfg_json()
        self.adjust_theme()
        self.custom_path = None
        self.stored_password = None
        if self.cfg:
            if 'custom_path' in self.cfg:
                self.custom_path = self.cfg['custom_path']
            if 'salt' in self.cfg and 'xl_pass' in self.cfg:
                try:
                    self.stored_password = utils.decrypt_password(self.cfg['xl_pass'], self.cfg['salt'].encode())
                except Exception as e:
                    logging.error(f"Error decrypting XLite password: {e}")
                    self.stored_password = None

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

        self.tooltip_manager = TooltipManager(self)

    async def setup_management_sections(self):
        await asyncio.gather(
            self.binary_manager.setup(),
            self.blocknet_manager.setup(),
            self.blockdx_manager.setup(),
            self.xlite_manager.setup()
        )

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
        self.after(0, self.check_processes)
        asyncio.run(self.setup_management_sections())
        self.setup_tooltips()
        self.init_grid()

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
        self.tooltip_manager.register_tooltip(self.blocknet_core_frame,
                                              msg=widgets_strings.tooltip_howtouse,
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.blockdx_frame,
                                              msg=widgets_strings.tooltip_howtouse,
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.xlite_frame,
                                              msg=widgets_strings.tooltip_howtouse,
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.bins_download_frame,
                                              msg=widgets_strings.tooltip_howtouse,
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.bins_title_frame,
                                              msg=widgets_strings.tooltip_bins_title_msg,
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.header_label,
                                              msg=widgets_strings.tooltip_bins_title_msg,
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.xlite_manager.frame_manager.xlite_label,
                                              msg=widgets_strings.tooltip_xlite_label_msg,
                                              delay=1.0, border_width=2, follow=True, bg_color=tooltip_bg_color)
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.blocknet_label,
                                              msg=widgets_strings.tooltip_blocknet_core_label_msg, delay=1,
                                              follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.blockdx_label,
                                              msg=widgets_strings.tooltip_blockdx_label_msg,
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.xlite_label,
                                              msg=widgets_strings.tooltip_xlite_label_msg,
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.install_delete_blocknet_button,
                                              msg='', delay=1, width=1, follow=True, bg_color=tooltip_bg_color,
                                              border_width=2, justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.install_delete_blockdx_button,
                                              msg=global_variables.blockdx_release_url,
                                              delay=1, width=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.install_delete_xlite_button,
                                              msg=global_variables.xlite_release_url,
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.blocknet_start_close_button,
                                              msg='',
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.blockdx_start_close_button,
                                              msg='',
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.xlite_toggle_execution_button,
                                              msg='',
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.blocknet_manager.frame_manager.label,
                                              msg=widgets_strings.tooltip_blocknet_core_label_msg,
                                              delay=1.0, border_width=2, follow=True, bg_color=tooltip_bg_color)
        self.tooltip_manager.register_tooltip(self.blockdx_manager.frame_manager.label,
                                              msg=widgets_strings.tooltip_blockdx_label_msg,
                                              delay=1.0, border_width=2, follow=True, bg_color=tooltip_bg_color)

    def init_grid(self):
        x = 0
        y = 0
        padx_main_frame = 10
        pady_main_frame = 5
        self.grid_frames(x, y, padx_main_frame, pady_main_frame)
        self.binary_manager.frame_manager.grid_widgets(x, y)
        self.blocknet_manager.frame_manager.grid_widgets(x, y)
        self.blockdx_manager.frame_manager.grid_widgets(x, y)
        self.xlite_manager.frame_manager.grid_widgets(x, y)

    def grid_frames(self, x, y, padx_main_frame, pady_main_frame):
        self.bins_download_frame.grid(row=x, column=y, padx=padx_main_frame, pady=pady_main_frame,
                                      sticky=MAIN_FRAMES_STICKY)
        # bin panel have 5 buttons per row
        self.bins_title_frame.grid(row=0, column=0, columnspan=5, padx=5, pady=5, sticky=TITLE_FRAMES_STICKY)

        self.blocknet_core_frame.grid(row=x + 1, column=y, padx=padx_main_frame, pady=pady_main_frame,
                                      sticky=MAIN_FRAMES_STICKY)
        self.blocknet_title_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5, sticky=TITLE_FRAMES_STICKY)

        self.blockdx_frame.grid(row=x + 2, column=y, padx=padx_main_frame, pady=pady_main_frame,
                                sticky=MAIN_FRAMES_STICKY)
        self.blockdx_title_frame.grid(row=0, column=0,columnspan=2,  padx=5, pady=5, sticky=TITLE_FRAMES_STICKY)

        self.xlite_frame.grid(row=x + 3, column=y, padx=padx_main_frame, pady=pady_main_frame,
                              sticky=MAIN_FRAMES_STICKY)
        self.xlite_title_frame.grid(row=0, column=0,columnspan=2,  padx=5, pady=5, sticky=TITLE_FRAMES_STICKY)

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

    def check_processes(self):
        blocknet_bin = global_variables.blocknet_bin
        blockdx_bin = global_variables.blockdx_bin[-1] if global_variables.system == "Darwin" \
            else global_variables.blockdx_bin
        xlite_bin = global_variables.xlite_bin[-1] if global_variables.system == "Darwin" \
            else global_variables.xlite_bin
        xlite_daemon_bin = global_variables.xlite_daemon_bin
        blocknet_processes = []
        blockdx_processes = []
        xlite_processes = []
        xlite_daemon_processes = []

        try:
            # Get all processes
            for proc in process_iter(['pid', 'name']):
                # Check if any process matches the Blocknet process name
                if blocknet_bin == proc.info['name']:
                    blocknet_processes.append(proc.info['pid'])
                # Check if any process matches the Block DX process name
                if blockdx_bin == proc.info['name']:
                    blockdx_processes.append(proc.info['pid'])
                # Check if any process matches the Xlite process name
                if xlite_bin == proc.info['name']:
                    xlite_processes.append(proc.info['pid'])
                # Check if any process matches the Xlite-daemon process name
                if xlite_daemon_bin == proc.info['name']:
                    xlite_daemon_processes.append(proc.info['pid'])
        except Exception as e:
            logging.warning(f"Error while checking processes: {e}")

        # Update Blocknet process status and store the PIDs
        self.blocknet_manager.blocknet_process_running = bool(blocknet_processes)
        self.blocknet_manager.utility.blocknet_pids = blocknet_processes

        # Update Block DX process status and store the PIDs
        self.blockdx_manager.process_running = bool(blockdx_processes)
        self.blockdx_manager.utility.blockdx_pids = blockdx_processes

        # Update Xlite process status and store the PIDs
        self.xlite_manager.process_running = bool(xlite_processes)
        self.xlite_manager.utility.xlite_pids = xlite_processes

        # Update Xlite-daemon process status and store the PIDs
        self.xlite_manager.daemon_process_running = bool(xlite_daemon_processes)
        self.xlite_manager.utility.xlite_daemon_pids = xlite_daemon_processes

        self.after(2000, self.check_processes)


def run_gui():
    app = Blocknet_AIO_GUI()
    # try:
    app.init_setup()
    app.mainloop()
    # except KeyboardInterrupt:
    #     print("GUI execution terminated by user.")
    # except Exception as e:
    #     # Log the error to a file
    #     logging.basicConfig(filename='gui_errors.log', level=logging.ERROR,
    #                         format='%(asctime)s - %(levelname)s - %(message)s')
    #     logging.error("An error occurred: %s", e)
    #
    #     # Print a user-friendly error message
    #     print("An unexpected error occurred. Please check the log file 'gui_errors.log' for more information.")
    #     app.on_close()


if __name__ == "__main__":
    run_gui()
