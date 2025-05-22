import asyncio
import logging
import os
import signal

import customtkinter as ctk
from PIL import Image

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
    """Main GUI class for Blocknet AIO application."""

    def __init__(self):
        """Initialize the Blocknet AIO GUI application."""
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

        self.disable_daemons_conf_check: bool = False

        self.cfg: dict = utils.load_cfg_json()
        self.adjust_theme()
        self.custom_path: str = None
        self.stored_password: str = None
        if self.cfg:
            if 'custom_path' in self.cfg:
                self.custom_path = self.cfg['custom_path']
            if 'salt' in self.cfg and 'xl_pass' in self.cfg:
                try:
                    self.stored_password = utils.decrypt_password(self.cfg['xl_pass'], self.cfg['salt'].encode())
                except Exception as e:
                    logging.error(f"Error decrypting XLite password: {e}")
                    self.stored_password = None

        self.time_disable_button: int = 3000

        self.tooltip_manager: TooltipManager = TooltipManager(self)

        self.blocknet_manager: BlocknetManager = BlocknetManager(self)
        self.binary_manager: BinaryManager = BinaryManager(self)
        self.blockdx_manager: BlockDXManager = BlockDXManager(self)
        self.xlite_manager: XliteManager = XliteManager(self)

    async def setup_management_sections(self) -> None:
        """Initialize and setup all management sections asynchronously."""
        await asyncio.gather(
            self.binary_manager.setup(),
            self.blocknet_manager.setup(),
            self.blockdx_manager.setup(),
            self.xlite_manager.setup()
        )

    def init_setup(self) -> None:
        """Initialize the GUI setup, including layout, images, and frame configuration."""
        self.title(widgets_strings.app_title_string)
        self.resizable(False, False)
        self.setup_load_images()
        self.after(0, self.check_processes)
        asyncio.run(self.setup_management_sections())
        self.setup_tooltips()
        self.init_grid()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def setup_load_images(self) -> None:
        """Load and set up images for use in the GUI."""
        resize = (65, 30)
        self.theme_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(global_variables.DIRPATH, "img", "light.png")).resize(resize,
                                                                                                      Image.LANCZOS),
            dark_image=Image.open(os.path.join(global_variables.DIRPATH, "img", "dark.png")).resize(resize,
                                                                                                    Image.LANCZOS),
            size=resize
        )
        resize = (50, 50)
        self.transparent_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(global_variables.DIRPATH, "img", "transparent.png")).resize(resize,
                                                                                                            Image.LANCZOS)
        )
        self.start_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(global_variables.DIRPATH, "img", "start-50.png")).resize(resize,
                                                                                                         Image.LANCZOS)
        )
        self.start_greyed_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(global_variables.DIRPATH, "img", "start-50_greyed.png")).resize(resize,
                                                                                                                Image.LANCZOS)
        )
        self.stop_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(global_variables.DIRPATH, "img", "stop-50.png")).resize(resize,
                                                                                                        Image.LANCZOS)
        )
        self.stop_greyed_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(global_variables.DIRPATH, "img", "stop-50_greyed.png")).resize(resize,
                                                                                                               Image.LANCZOS)
        )
        self.delete_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(global_variables.DIRPATH, "img", "delete-50.png")).resize(resize,
                                                                                                          Image.LANCZOS)
        )
        self.delete_greyed_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(global_variables.DIRPATH, "img", "delete-50_greyed.png")).resize(resize,
                                                                                                                 Image.LANCZOS)
        )
        self.install_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(global_variables.DIRPATH, "img", "installer-50.png")).resize(resize,
                                                                                                             Image.LANCZOS)
        )
        self.install_greyed_img = ctk.CTkImage(
            light_image=Image.open(os.path.join(global_variables.DIRPATH, "img", "installer-50_greyed.png")).resize(
                resize, Image.LANCZOS)
        )

    def setup_tooltips(self) -> None:
        """Set up tooltips for various GUI components."""
        self.tooltip_manager.register_tooltip(self.blocknet_manager.frame_manager.master_frame,
                                              msg=widgets_strings.tooltip_howtouse, delay=1, follow=True,
                                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        self.tooltip_manager.register_tooltip(self.blockdx_manager.frame_manager.master_frame,
                                              msg=widgets_strings.tooltip_howtouse, delay=1, follow=True,
                                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        self.tooltip_manager.register_tooltip(self.xlite_manager.frame_manager.master_frame,
                                              msg=widgets_strings.tooltip_howtouse, delay=1, follow=True,
                                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.master_frame,
                                              msg=widgets_strings.tooltip_howtouse, delay=1, follow=True,
                                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.title_frame,
                                              msg=widgets_strings.tooltip_bins_title_msg, delay=1, follow=True,
                                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.header_label,
                                              msg=widgets_strings.tooltip_bins_title_msg, delay=1, follow=True,
                                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        self.tooltip_manager.register_tooltip(self.xlite_manager.frame_manager.xlite_label,
                                              msg=widgets_strings.tooltip_xlite_label_msg, delay=1.0, border_width=2,
                                              follow=True, bg_color=tooltip_bg_color)
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.blocknet_label,
                                              msg=widgets_strings.tooltip_blocknet_core_label_msg, delay=1, follow=True,
                                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.blockdx_label,
                                              msg=widgets_strings.tooltip_blockdx_label_msg,
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.xlite_label,
                                              msg=widgets_strings.tooltip_xlite_label_msg, delay=1, follow=True,
                                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.install_delete_blocknet_button, msg='',
                                              delay=1, width=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.install_delete_blockdx_button,
                                              msg=global_variables.blockdx_release_url, delay=1, width=1, follow=True,
                                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.install_delete_xlite_button,
                                              msg=global_variables.xlite_release_url, delay=1, follow=True,
                                              bg_color=tooltip_bg_color, border_width=2, justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.blocknet_start_close_button, msg='',
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.blockdx_start_close_button, msg='',
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.binary_manager.frame_manager.xlite_toggle_execution_button, msg='',
                                              delay=1, follow=True, bg_color=tooltip_bg_color, border_width=2,
                                              justify="left")
        self.tooltip_manager.register_tooltip(self.blocknet_manager.frame_manager.label,
                                              msg=widgets_strings.tooltip_blocknet_core_label_msg, delay=1.0,
                                              border_width=2, follow=True, bg_color=tooltip_bg_color)
        self.tooltip_manager.register_tooltip(self.blockdx_manager.frame_manager.label,
                                              msg=widgets_strings.tooltip_blockdx_label_msg, delay=1.0, border_width=2,
                                              follow=True, bg_color=tooltip_bg_color)

    def init_grid(self) -> None:
        """Initialize the grid layout for GUI components."""
        x: int = 0
        y: int = 0
        padx_main_frame: int = 10
        pady_main_frame: int = 5
        self.grid_frames(x, y, padx_main_frame, pady_main_frame)
        self.binary_manager.frame_manager.grid_widgets(x, y)
        self.blocknet_manager.frame_manager.grid_widgets(x, y)
        self.blockdx_manager.frame_manager.grid_widgets(x, y)
        self.xlite_manager.frame_manager.grid_widgets(x, y)

    def grid_frames(self, x: int, y: int, padx_main_frame: int, pady_main_frame: int) -> None:
        """Grid layout for frames in the GUI."""
        self.binary_manager.frame_manager.master_frame.grid(row=x, column=y, padx=padx_main_frame, pady=pady_main_frame,
                                                            sticky=MAIN_FRAMES_STICKY)
        # bin panel have 5 buttons per row
        self.binary_manager.frame_manager.title_frame.grid(row=0, column=0, columnspan=5, padx=5, pady=5,
                                                           sticky=TITLE_FRAMES_STICKY)

        self.blocknet_manager.frame_manager.master_frame.grid(row=x + 1, column=y, padx=padx_main_frame,
                                                              pady=pady_main_frame,
                                                              sticky=MAIN_FRAMES_STICKY)
        self.blocknet_manager.frame_manager.title_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5,
                                                             sticky=TITLE_FRAMES_STICKY)

        self.blockdx_manager.frame_manager.master_frame.grid(row=x + 2, column=y, padx=padx_main_frame,
                                                             pady=pady_main_frame,
                                                             sticky=MAIN_FRAMES_STICKY)
        self.blockdx_manager.frame_manager.title_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5,
                                                            sticky=TITLE_FRAMES_STICKY)

        self.xlite_manager.frame_manager.master_frame.grid(row=x + 3, column=y, padx=padx_main_frame,
                                                           pady=pady_main_frame,
                                                           sticky=MAIN_FRAMES_STICKY)
        self.xlite_manager.frame_manager.title_frame.grid(row=0, column=0, columnspan=2, padx=5, pady=5,
                                                          sticky=TITLE_FRAMES_STICKY)

    def handle_signal(self, signum: int, frame) -> None:
        """Handle signals like SIGINT and SIGTERM."""
        print(f"Signal {signum} received.")
        self.on_close()

    def on_close(self) -> None:
        """Handle application close event."""
        logging.info("Closing application...")
        utils.terminate_all_threads()
        logging.info("Threads terminated.")
        os._exit(0)

    def adjust_theme(self) -> None:
        """Adjust the theme of the application based on the configuration."""
        if self.cfg and 'theme' in self.cfg:
            actual: str = ctk.get_appearance_mode()
            if self.cfg['theme'] != actual:
                if actual == "Dark":
                    new_theme: str = "Light"
                else:
                    new_theme: str = "Dark"
                ctk.set_appearance_mode(new_theme)

    def switch_theme_command(self) -> None:
        """Switch the application theme to the opposite of the current theme."""
        actual: str = ctk.get_appearance_mode()
        if actual == "Dark":
            new_theme: str = "Light"
        else:
            new_theme: str = "Dark"
        ctk.set_appearance_mode(new_theme)
        utils.save_cfg_json("theme", new_theme)

    def check_processes(self) -> None:
        blocknet_processes, blockdx_processes, xlite_processes, xlite_daemon_processes = utils.processes_check()
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

        self.after(5000, func=self.check_processes)


def run_gui() -> None:
    """Run the Blocknet AIO GUI application."""
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
