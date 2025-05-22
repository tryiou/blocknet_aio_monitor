import logging
import os
import shutil
import time
from threading import Thread

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

import widgets_strings
from gui.binary_frame_manager import BinaryFrameManager
from utilities import utils, global_variables


class BinaryFileHandler(FileSystemEventHandler):
    """
    Handles file modification events with rate limiting for binary updates.
    """

    def __init__(self, binary_manager: 'BinaryManager'):
        """
        Initializes the handler.
        :param binary_manager: The manager responsible for binary updates.
        """
        super().__init__()
        self.binary_manager: 'BinaryManager' = binary_manager
        self.max_delay: float = 5  # seconds
        self.last_run: float = 0
        self.scheduled: bool = False

    def on_modified(self, event: 'FileSystemEvent') -> None:
        """
        Called when a file is modified. Executes binary check/update with rate limiting.
        """
        # logging.info("File modified detected: %s", event.src_path)

        if self.scheduled:
            # logging.debug("Update already scheduled, skipping immediate execution.")
            return

        time_since_last = time.time() - self.last_run
        # logging.debug("Time since last run: %.2f seconds", time_since_last)

        if time_since_last >= self.max_delay:
            # Execute immediately
            # logging.info("Executing check_and_update_aio_folder immediately.")
            self.binary_manager.check_and_update_aio_folder()
            self.last_run = time.time()
        else:
            # Schedule for later
            delay_ms = int((self.max_delay - time_since_last) * 1000)
            # logging.info("Scheduling check_and_update_aio_folder in %d ms.", delay_ms)
            self.scheduled = True
            self.binary_manager.root_gui.after(delay_ms, self._execute_scheduled)

    def _execute_scheduled(self) -> None:
        """
        Executes the scheduled update and resets the schedule flag.
        """
        # logging.info("Executing scheduled check_and_update_aio_folder.")
        self.binary_manager.check_and_update_aio_folder()
        self.last_run = time.time()
        self.scheduled = False


class BinaryManager:
    def __init__(self, root_gui):
        self.root_gui = root_gui
        self.frame_manager = None

        self.disable_start_blocknet_button = False
        self.disable_start_xlite_button = False
        self.disable_start_blockdx_button = False

        self.download_blocknet_thread = None
        self.download_blockdx_thread = None
        self.download_xlite_thread = None

        self.observer = Observer()
        self.handler = BinaryFileHandler(self)
        self.observer.schedule(self.handler, global_variables.aio_folder, recursive=False)
        self.observer.start()

        self.tooltip_manager = self.root_gui.tooltip_manager

    async def setup(self):
        self.frame_manager = BinaryFrameManager(self)

        self.root_gui.after(0, self.check_and_update_aio_folder)
        self.root_gui.after(0, self.update_blocknet_buttons)
        self.root_gui.after(0, self.update_blockdx_buttons)
        self.root_gui.after(0, self.update_xlite_buttons)
        self.root_gui.after(0, self.update_xbridge_bots_buttons)  # Add this line

    def _start_or_close_binary(self, process_running, stop_func, start_func, button, disable_flag):
        img = self.root_gui.stop_greyed_img if process_running else self.root_gui.start_greyed_img
        utils.disable_button(button, img=img)
        setattr(self, disable_flag,
                True)  # Disable the button flag
        if process_running:
            Thread(target=stop_func).start()
        else:
            Thread(target=start_func).start()
        self.root_gui.after(self.root_gui.time_disable_button, self._enable_binary_start_button, disable_flag)

    def _enable_binary_start_button(self, disable_flag):
        setattr(self, disable_flag, False)

    def start_or_close_blocknet(self):
        if not self.root_gui.blocknet_manager.blocknet_process_running:
            self.root_gui.blocknet_manager.check_config()
        self._start_or_close_binary(
            process_running=self.root_gui.blocknet_manager.blocknet_process_running,
            stop_func=self.root_gui.blocknet_manager.utility.close_blocknet,
            start_func=self.root_gui.blocknet_manager.utility.start_blocknet,
            button=self.frame_manager.blocknet_start_close_button,
            disable_flag='disable_start_blocknet_button'
        )

    def start_or_close_blockdx(self):
        if not self.root_gui.blockdx_manager.process_running:
            self.root_gui.blockdx_manager.blockdx_check_config()
        self._start_or_close_binary(
            process_running=self.root_gui.blockdx_manager.process_running,
            stop_func=self.root_gui.blockdx_manager.utility.close_blockdx,
            start_func=self.root_gui.blockdx_manager.utility.start_blockdx,
            button=self.frame_manager.blockdx_start_close_button,
            disable_flag='disable_start_blockdx_button'
        )

    def start_or_close_xlite(self):
        if not self.root_gui.xlite_manager.process_running and self.root_gui.stored_password:
            env_vars = [{"CC_WALLET_PASS": self.root_gui.stored_password}, {"CC_WALLET_AUTOLOGIN": 'true'}]
        else:
            env_vars = []

        self._start_or_close_binary(
            process_running=self.root_gui.xlite_manager.process_running,
            stop_func=self.root_gui.xlite_manager.utility.close_xlite,
            start_func=lambda: self.root_gui.xlite_manager.utility.start_xlite(env_vars=env_vars),
            button=self.frame_manager.xlite_toggle_execution_button,
            disable_flag='disable_start_xlite_button'
        )

    def install_delete_blocknet_command(self):
        blocknet_boolvar = self.frame_manager.blocknet_installed_boolvar.get()
        if blocknet_boolvar:
            self.delete_blocknet_command()
        else:
            self.download_blocknet_command()

    def download_blocknet_command(self):
        utils.disable_button(self.frame_manager.install_delete_blocknet_button, img=self.root_gui.install_greyed_img)
        self.download_blocknet_thread = Thread(target=self.root_gui.blocknet_manager.utility.download_blocknet_bin,
                                               daemon=True)
        self.download_blocknet_thread.start()

    def delete_blocknet_command(self):
        blocknet_pruned_version = self.root_gui.blocknet_manager.version[0].replace('v', '')
        for item in os.listdir(global_variables.aio_folder):
            item_path = os.path.join(global_variables.aio_folder, item)
            if os.path.isdir(item_path):
                # if a wrong version is found, delete it.
                if 'blocknet-' in item:
                    if blocknet_pruned_version in item:
                        logging.info(f"deleting {item_path}")
                        shutil.rmtree(item_path)

    def install_delete_blockdx_command(self):
        blockdx_boolvar = self.frame_manager.blockdx_installed_boolvar.get()
        if blockdx_boolvar:
            self.delete_blockdx_command()
        else:
            self.download_blockdx_command()

    def download_blockdx_command(self):
        utils.disable_button(self.frame_manager.install_delete_blockdx_button, img=self.root_gui.install_greyed_img)
        self.download_blockdx_thread = Thread(target=self.root_gui.blockdx_manager.utility.download_blockdx_bin,
                                              daemon=True)
        self.download_blockdx_thread.start()

    def delete_blockdx_command(self):
        blockdx_pruned_version = self.root_gui.blockdx_manager.version[0].replace('v', '')
        for item in os.listdir(global_variables.aio_folder):
            item_path = os.path.join(global_variables.aio_folder, item)
            if global_variables.system == 'Darwin':
                blockdx_filename = os.path.basename(global_variables.blockdx_release_url)
                if os.path.isfile(item_path):
                    if blockdx_filename in item_path:
                        self.root_gui.blockdx_manager.unmount_dmg()
                        os.remove(item_path)
            else:
                if os.path.isdir(item_path):
                    if 'BLOCK-DX-' in item:
                        if blockdx_pruned_version in item:
                            logging.info(f"deleting {item_path}")
                            shutil.rmtree(item_path)

    def install_delete_xlite_command(self):
        xlite_boolvar = self.frame_manager.xlite_installed_boolvar.get()
        if xlite_boolvar:
            self.delete_xlite_command()
        else:
            self.download_xlite_command()

    def download_xlite_command(self):
        utils.disable_button(self.frame_manager.install_delete_xlite_button, img=self.root_gui.install_greyed_img)
        self.download_xlite_thread = Thread(target=self.root_gui.xlite_manager.utility.download_xlite_bin, daemon=True)
        self.download_xlite_thread.start()

    def delete_xlite_command(self):
        xlite_pruned_version = self.root_gui.xlite_manager.version[0].replace('v', '')
        for item in os.listdir(global_variables.aio_folder):
            item_path = os.path.join(global_variables.aio_folder, item)
            if global_variables.system == 'Darwin':
                xlite_filename = os.path.basename(global_variables.xlite_release_url)
                if os.path.isfile(item_path):
                    if xlite_filename in item_path:
                        self.root_gui.xlite_manager.utility.unmount_dmg()
                        os.remove(item_path)
            else:
                if os.path.isdir(item_path):
                    if 'XLite-' in item:
                        if xlite_pruned_version in item:
                            logging.info(f"deleting {item_path}")
                            shutil.rmtree(item_path)

    def check_and_update_aio_folder(self):
        # logging.info("check_and_update_aio_folder")

        # Get system information and versions
        is_darwin = global_variables.system == "Darwin"
        aio_folder = global_variables.aio_folder

        # Define version info for each application
        apps_info = {
            "blocknet": {
                "version": self._prune_version(self.root_gui.blocknet_manager.version),
                "dir_prefix": "blocknet-",
                "is_dir": True,
                "darwin_file": None,
                "boolvar": self.root_gui.binary_manager.frame_manager.blocknet_installed_boolvar
            },
            "blockdx": {
                "version": self._prune_version(self.root_gui.blockdx_manager.version),
                "dir_prefix": "BLOCK-DX-",
                "is_dir": not is_darwin,
                "darwin_file": os.path.basename(global_variables.blockdx_release_url) if is_darwin else None,
                "boolvar": self.root_gui.binary_manager.frame_manager.blockdx_installed_boolvar
            },
            "xlite": {
                "version": self._prune_version(self.root_gui.xlite_manager.version),
                "dir_prefix": "XLite-",
                "is_dir": not is_darwin,
                "darwin_file": os.path.basename(global_variables.xlite_release_url) if is_darwin else None,
                "boolvar": self.root_gui.binary_manager.frame_manager.xlite_installed_boolvar
            }
        }

        # Check each application
        for app_name, app_info in apps_info.items():
            app_info["found"] = False

        # Scan the AIO folder for matching items
        for item in os.listdir(aio_folder):
            full_path = os.path.join(aio_folder, item)
            # logging.info(f"item: {item}")

            for app_name, app_info in apps_info.items():
                if app_info["dir_prefix"] in item:
                    self._check_app_version(app_info, item, full_path)

        # Update GUI with results
        for app_info in apps_info.values():
            # logging.info(app_info)
            app_info["boolvar"].set(app_info["found"])

    def _prune_version(self, version):
        """Remove 'v' prefix from version string."""
        return version[0].replace('v', '')

    def _log_incorrect_target(self, target):
        """Log incorrect version found."""
        logging.info(f"incorrect version: {target}")
        # shutil.rmtree(target) if os.path.isdir(target) else os.remove(target)
        return

    def _check_app_version(self, app_info, item, full_path):
        """Check if the item matches the expected version for the given app."""
        if app_info["is_dir"] and os.path.isdir(full_path):
            # Directory check for non-Darwin or blocknet
            if app_info["version"] in item:
                app_info["found"] = True
            else:
                self._log_incorrect_target(full_path)
        elif not app_info["is_dir"] and os.path.isfile(full_path):
            # File check for Darwin (macOS) for blockdx and xlite
            if app_info["darwin_file"] in item:
                app_info["found"] = True
            else:
                self._log_incorrect_target(full_path)

    def update_blocknet_buttons(self):
        # BLOCKNET
        self.update_blocknet_start_close_button()
        blocknet_boolvar = self.frame_manager.blocknet_installed_boolvar.get()
        percent_buff = self.root_gui.blocknet_manager.utility.binary_percent_download
        dl_string = f"{int(percent_buff)}%" if percent_buff else ""
        var_blocknet = dl_string if self.root_gui.blocknet_manager.utility.downloading_bin else ""
        blocknet_folder = os.path.join(global_variables.aio_folder, global_variables.conf_data.blocknet_bin_path[0])
        if blocknet_boolvar:
            var_blocknet = ""
            self.tooltip_manager.update_tooltip(widget=self.frame_manager.install_delete_blocknet_button,
                                                msg=blocknet_folder)
            button_condition = self.root_gui.blocknet_manager.blocknet_process_running or self.root_gui.blocknet_manager.utility.downloading_bin
        else:
            self.tooltip_manager.update_tooltip(widget=self.frame_manager.install_delete_blocknet_button,
                                                msg=global_variables.blocknet_release_url)
            button_condition = self.root_gui.blocknet_manager.utility.downloading_bin

        if button_condition:
            utils.disable_button(self.frame_manager.install_delete_blocknet_button,
                                 img=self.root_gui.delete_greyed_img if blocknet_boolvar else self.root_gui.install_greyed_img)
        else:
            utils.enable_button(self.frame_manager.install_delete_blocknet_button,
                                img=self.root_gui.delete_img if blocknet_boolvar else self.root_gui.install_img)
        self.frame_manager.install_delete_blocknet_string_var.set(var_blocknet)
        self.root_gui.after(2000, self.update_blocknet_buttons)

    def update_blockdx_buttons(self):
        # BLOCK-DX
        self.update_blockdx_start_close_button()
        blockdx_boolvar = self.frame_manager.blockdx_installed_boolvar.get()
        percent_buff = self.root_gui.blockdx_manager.utility.binary_percent_download
        dl_string = f"{int(percent_buff)}%" if percent_buff else ""
        var_blockdx = dl_string if self.root_gui.blockdx_manager.utility.downloading_bin else ""
        blockdx_folder = os.path.join(global_variables.aio_folder, global_variables.blockdx_curpath)
        if blockdx_boolvar:
            var_blockdx = ""
            self.tooltip_manager.update_tooltip(widget=self.frame_manager.install_delete_blockdx_button,
                                                msg=blockdx_folder)
            button_condition = self.root_gui.blockdx_manager.process_running or self.root_gui.blockdx_manager.utility.downloading_bin
        else:
            self.tooltip_manager.update_tooltip(widget=self.frame_manager.install_delete_blockdx_button,
                                                msg=global_variables.blockdx_release_url)
            button_condition = self.root_gui.blockdx_manager.utility.downloading_bin

        if button_condition:
            utils.disable_button(self.frame_manager.install_delete_blockdx_button,
                                 img=self.root_gui.delete_greyed_img if blockdx_boolvar else self.root_gui.install_greyed_img)
        else:
            utils.enable_button(self.frame_manager.install_delete_blockdx_button,
                                img=self.root_gui.delete_img if blockdx_boolvar else self.root_gui.install_img)

        self.frame_manager.install_delete_blockdx_string_var.set(var_blockdx)
        self.root_gui.after(2000, self.update_blockdx_buttons)

    def update_xlite_buttons(self):
        # Xlite
        self.update_xlite_start_close_button()
        xlite_boolvar = self.frame_manager.xlite_installed_boolvar.get()
        percent_buff = self.root_gui.xlite_manager.utility.binary_percent_download
        dl_string = f"{int(percent_buff)}%" if percent_buff else ""
        var_xlite = dl_string if self.root_gui.xlite_manager.utility.downloading_bin else ""
        folder = os.path.join(global_variables.aio_folder, global_variables.xlite_curpath)
        if xlite_boolvar:
            var_xlite = ""
            self.tooltip_manager.update_tooltip(widget=self.frame_manager.install_delete_xlite_button,
                                                msg=folder)
            button_condition = self.root_gui.xlite_manager.process_running or self.root_gui.xlite_manager.utility.downloading_bin
        else:
            self.tooltip_manager.update_tooltip(widget=self.frame_manager.install_delete_xlite_button,
                                                msg=global_variables.xlite_release_url)
            button_condition = self.root_gui.xlite_manager.utility.downloading_bin

        if button_condition:
            utils.disable_button(self.frame_manager.install_delete_xlite_button,
                                 img=self.root_gui.delete_greyed_img if xlite_boolvar else self.root_gui.install_greyed_img)
        else:
            utils.enable_button(self.frame_manager.install_delete_xlite_button,
                                img=self.root_gui.delete_img if xlite_boolvar else self.root_gui.install_img)
        self.frame_manager.install_delete_xlite_string_var.set(var_xlite)
        self.root_gui.after(2000, self.update_xlite_buttons)

    def update_blocknet_start_close_button(self):
        var = widgets_strings.close_string if self.root_gui.blocknet_manager.blocknet_process_running else widgets_strings.start_string
        self.frame_manager.blocknet_start_close_button_string_var.set(var)

        if self.root_gui.blocknet_manager.blocknet_process_running:
            self.tooltip_manager.update_tooltip(widget=self.frame_manager.blocknet_start_close_button,
                                                msg=widgets_strings.close_string)
        else:
            self.tooltip_manager.update_tooltip(widget=self.frame_manager.blocknet_start_close_button,
                                                msg=widgets_strings.start_string)

        enabled = (not self.root_gui.blocknet_manager.utility.downloading_bin and
                   not self.frame_manager.parent.disable_start_blocknet_button and
                   not self.root_gui.blocknet_manager.utility.bootstrap_checking)
        if enabled:
            img = self.root_gui.stop_img if self.root_gui.blocknet_manager.blocknet_process_running else self.root_gui.start_img
            utils.enable_button(self.frame_manager.blocknet_start_close_button, img=img)
        else:
            img = self.root_gui.stop_greyed_img if self.root_gui.blocknet_manager.blocknet_process_running else self.root_gui.start_greyed_img
            utils.disable_button(self.frame_manager.blocknet_start_close_button, img=img)

    def update_blockdx_start_close_button(self):
        # blockdx_start_close_button_string_var
        var = widgets_strings.close_string if self.root_gui.blockdx_manager.process_running else widgets_strings.start_string
        self.frame_manager.blockdx_start_close_button_string_var.set(var)

        enabled = (self.root_gui.blockdx_manager.process_running or (
                not self.root_gui.blockdx_manager.utility.downloading_bin and
                self.root_gui.blocknet_manager.utility.valid_rpc) and
                   not self.frame_manager.parent.disable_start_blockdx_button)
        if enabled:
            if self.root_gui.blockdx_manager.process_running:
                self.tooltip_manager.update_tooltip(widget=self.frame_manager.blockdx_start_close_button,
                                                    msg=widgets_strings.close_string)
                img = self.root_gui.stop_img
            else:
                self.tooltip_manager.update_tooltip(widget=self.frame_manager.blockdx_start_close_button,
                                                    msg=widgets_strings.start_string)
                img = self.root_gui.start_img
            utils.enable_button(self.frame_manager.blockdx_start_close_button, img=img)

        else:
            if self.root_gui.blockdx_manager.process_running:
                img = self.root_gui.stop_greyed_img
                self.tooltip_manager.update_tooltip(widget=self.frame_manager.blockdx_start_close_button,
                                                    msg=widgets_strings.close_string)
            else:
                self.tooltip_manager.update_tooltip(widget=self.frame_manager.blockdx_start_close_button,
                                                    msg=widgets_strings.blockdx_missing_blocknet_config_string)
                img = self.root_gui.start_greyed_img
            utils.disable_button(self.frame_manager.blockdx_start_close_button, img=img)

    def update_xlite_start_close_button(self):
        # xlite_start_close_button_string_var
        var = widgets_strings.close_string if self.root_gui.xlite_manager.process_running else widgets_strings.start_string
        self.frame_manager.xlite_toggle_execution_string_var.set(var)

        if self.root_gui.xlite_manager.process_running:
            self.tooltip_manager.update_tooltip(widget=self.frame_manager.xlite_toggle_execution_button,
                                                msg=widgets_strings.close_string)
        else:
            self.tooltip_manager.update_tooltip(widget=self.frame_manager.xlite_toggle_execution_button,
                                                msg=widgets_strings.start_string)

        # xlite_start_close_button
        disable_start_close_button = self.root_gui.xlite_manager.utility.downloading_bin or self.disable_start_xlite_button

        if not disable_start_close_button:
            img = self.root_gui.stop_img if self.root_gui.xlite_manager.process_running else self.root_gui.start_img
            # self.xlite_start_close_button.configure(image=img)
            utils.enable_button(self.frame_manager.xlite_toggle_execution_button, img=img)
        else:
            img = self.root_gui.stop_greyed_img if self.root_gui.xlite_manager.process_running else self.root_gui.start_greyed_img
            utils.disable_button(self.frame_manager.xlite_toggle_execution_button, img=img)

    def update_xbridge_bots_buttons(self):
        # XBridge Bots
        self.update_xbridge_bots_start_close_button()
        self.update_xbridge_bots_install_delete_button()

        if self.frame_manager.xbridge_bot_manager.process and self.frame_manager.xbridge_bot_manager.process.poll() is not None:
            self.frame_manager.xbridge_bot_manager.process = None

        # Schedule next update
        self.root_gui.after(2000, self.update_xbridge_bots_buttons)

    def update_xbridge_bots_install_delete_button(self):
        bots_boolvar = self.frame_manager.bots_installed_boolvar.get()
        if bots_boolvar:
            # self.tooltip_manager.update_tooltip(widget=self.frame_manager.install_delete_bots_button,
            #                                     msg=self.frame_manager.xbridge_bot_manager.target_dir)
            button_condition = self.frame_manager.xbridge_bot_manager.process or self.frame_manager.xbridge_bot_manager.thread and self.frame_manager.xbridge_bot_manager.thread.is_alive()
        else:
            # self.tooltip_manager.update_tooltip(widget=self.frame_manager.install_delete_bots_button,
            #                                     msg=self.frame_manager.xbridge_bot_manager.repo_url)
            button_condition = self.frame_manager.xbridge_bot_manager.process or self.frame_manager.xbridge_bot_manager.thread and self.frame_manager.xbridge_bot_manager.thread.is_alive()

            # Set install/delete button image based on state
        if button_condition:
            utils.disable_button(self.frame_manager.install_delete_bots_button,
                                 img=self.root_gui.delete_greyed_img if bots_boolvar else self.root_gui.install_greyed_img)
        else:
            utils.enable_button(self.frame_manager.install_delete_bots_button,
                                img=self.root_gui.delete_img if bots_boolvar else self.root_gui.install_img)

    def update_xbridge_bots_start_close_button(self):

        # Update tooltip message
        if self.frame_manager.xbridge_bot_manager.process:
            self.tooltip_manager.update_tooltip(widget=self.frame_manager.bots_toggle_execution_button,
                                                msg=widgets_strings.close_string)
        else:
            self.tooltip_manager.update_tooltip(widget=self.frame_manager.bots_toggle_execution_button,
                                                msg=widgets_strings.start_string)

            # Determine if button should be enabled/disabled based on download status
        disable_start_close_button = self.frame_manager.xbridge_bot_manager.thread and self.frame_manager.xbridge_bot_manager.thread.is_alive()
        # or not self.frame_manager.xbridge_bot_manager.repo_management.venv

        if not disable_start_close_button:
            img = self.root_gui.stop_img if self.frame_manager.xbridge_bot_manager.process else self.root_gui.start_img
            utils.enable_button(self.frame_manager.bots_toggle_execution_button, img=img)
        else:
            img = self.root_gui.stop_greyed_img if self.frame_manager.xbridge_bot_manager.process else self.root_gui.start_greyed_img
            utils.disable_button(self.frame_manager.bots_toggle_execution_button, img=img)

    def update_xbridge_bots_version_optionmenu(self):
        self.frame_manager.bots_version_optionmenu.configure(
            values=self.frame_manager.xbridge_bot_manager.get_available_branches())
