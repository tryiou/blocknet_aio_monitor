import logging
import os
import subprocess
import sys

from utilities import global_variables
from utilities.helper_util import UtilityHelper


class BaseBinUtil:
    def __init__(self, app_name):
        self.app_name = app_name
        self.helper = UtilityHelper()
        self.binary_percent_download = None
        self.downloading_bin = False
        self.system = os.name
        self.process = None

    def download_binary(self, url, tmp_filename, exe_path, extract_path):
        self.downloading_bin = True
        try:
            self.helper.download_file(
                url,
                os.path.join(global_variables.aio_folder, tmp_filename),
                exe_path,
                extract_path,
                self.system,
                "binary_percent_download",
                self
            )
        finally:
            self.downloading_bin = False

    def start_process(self, command, cwd=None, env_vars=None, dmg_path=None, mount_point=None):        # Prepare environment variables if provided
        if env_vars:
            full_env = os.environ.copy()
            full_env.update(env_vars)
        else:
            full_env = None

        self.process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=full_env,
            start_new_session=True
        )
        return self.process

    def graceful_terminate(self, timeout=10):
        if not self.process:
            return

        try:
            self.process.terminate()
            self.process.wait(timeout=timeout)
            logging.info(f"Closed {self.app_name}")
            self.process = None
        except subprocess.TimeoutExpired:
            logging.info(f"Force terminating {self.app_name}")
            self.force_kill()
            logging.info(f"{self.app_name} has been force terminated")
            self.process = None

    def force_kill(self):
        if self.process:
            try:
                self.process.kill()
                logging.info(f"Killed {self.app_name}")
                self.process = None
            except Exception as e:
                logging.error(f"Error killing {self.app_name}: {e}")

    def mount_dmg(self, dmg_path, mount_path):
        if sys.platform == "darwin":
            if dmg_path and mount_path:
                self.helper.handle_dmg(dmg_path, mount_path, "mount")

    def unmount_dmg(self, mount_path):
        if sys.platform == "darwin":
            if mount_path:
                self.helper.handle_dmg(None, mount_path, "unmount")
