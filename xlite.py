import io
import platform
import tarfile
import zipfile
import psutil
import requests
import logging
import os
import subprocess
import time
import json
from contextlib import contextmanager
from conf_data import (xlite_releases_urls, xlite_bin_path, xlite_bin_name, aio_blocknet_data_path,
                       xlite_default_paths, xlite_daemon_default_paths)

logging.basicConfig(level=logging.DEBUG)

system = platform.system()
machine = platform.machine()


class XliteUtility:
    def __init__(self):
        self.process_running = None
        self.xlite_process = None
        self.xlite_daemon_process = None
        self.xlite_conf_local = None
        self.xlite_daemon_confs_local = {}
        self.running = True  # flag for async funcs
        self.xlite_pids = []
        self.xlite_daemon_pids = []
        self.parse_xlite_conf()
        self.parse_xlite_daemon_conf()
        self.downloading_bin = False
        # self.start_async_tasks()

    def parse_xlite_conf(self):
        data_folder = os.path.expandvars(os.path.expanduser(xlite_default_paths.get(system, None)))
        file = "app-settings.json"
        file_path = os.path.join(data_folder, file)
        meta_data = {}

        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as file:
                    meta_data = json.load(file)
                    logging.info(f"XLITE: Loaded JSON data from {file_path}: {meta_data}")
            except Exception as e:
                logging.error(f"Error parsing {file_path}: {e}, repairing file")
        else:
            logging.warning(f"{file_path} doesn't exist")
        self.xlite_conf_local = meta_data

    def parse_xlite_daemon_conf(self):
        # Assuming daemon_data_path and confs_folder are defined earlier in your code
        daemon_data_path = os.path.expandvars(os.path.expanduser(xlite_daemon_default_paths.get(system, None)))
        confs_folder = os.path.join(daemon_data_path, "settings")

        # List all files in the confs_folder
        if not os.path.exists(confs_folder):
            logging.warning(f"{confs_folder} doesn't exist")
            return 0

        files_in_folder = os.listdir(confs_folder)

        # Filter out only JSON files
        json_files = [file for file in files_in_folder if file.endswith('.json')]

        # Parse each JSON file
        for json_file in json_files:
            json_file_path = os.path.join(confs_folder, json_file)
            coin = str(json_file).split("-")[1].split(".")[0]
            try:
                with open(json_file_path, 'r') as file:
                    data = json.load(file)
                    # Do something with the parsed JSON data
                # logging.debug(f"Parsed data from {coin} {json_file}: {data}")
                self.xlite_daemon_confs_local[coin] = data
            except Exception as e:
                self.xlite_daemon_confs_local[coin] = "ERROR PARSING"
                logging.error(f"Error parsing {json_file_path}: {e}")
        logging.info(f"XLITE-DAEMON: Parsed every coins conf {self.xlite_daemon_confs_local}")

    def start_xlite(self, retry_limit=3, retry_count=0):
        if retry_count >= retry_limit:
            logging.error("Retry limit exceeded. Unable to start Xlite.")
            return

        local_path = os.path.expandvars(os.path.expanduser(aio_blocknet_data_path.get(system)))

        xlite_exe = os.path.join(local_path, *xlite_bin_path[system])

        if not os.path.exists(xlite_exe):
            self.downloading_bin = True
            logging.info(f"Xlite executable not found at {xlite_exe}. Downloading...")
            download_xlite_bin()
            self.downloading_bin = False

        try:
            if system == "Darwin":
                # mac mod
                url = xlite_releases_urls.get((system, machine))
                xlite_dmg_name = os.path.basename(url)
                dmg_path = os.join(local_path, xlite_dmg_name)
                # Mount the DMG file
                os.system(f'hdiutil attach "{dmg_path}"')
                # https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.dmg
                volume_name = ' '.join(os.path.splitext(os.path.basename(url))[0].split('-')[:-1])
                app_name = volume_name + '.app'
                # Path to the application inside the DMG file
                mount_path = f"/Volumes/{volume_name}/{app_name}"
                full_path = os.path.join(mount_path, *xlite_bin_name[system])
                logging.info(
                    f"volume_name: {volume_name}, app_name: {app_name}, mount_path: {mount_path}, full_path: {full_path}")
                self.xlite_process = subprocess.Popen([full_path],
                                                      stdout=subprocess.PIPE,
                                                      stderr=subprocess.PIPE,
                                                      stdin=subprocess.PIPE,
                                                      start_new_session=True)
            # first run not working
            # with change_directory(os.path.join(local_path, xlite_bin_path[system])):
            #     logging.info(f"DARWIN BIN: {['open', '-a', xlite_bin_name[system]]} ")
            #     self.xlite_process = subprocess.Popen(['open', '-a', xlite_bin_name[system]],
            #                                           stdout=subprocess.PIPE,
            #                                           stderr=subprocess.PIPE,
            #                                           stdin=subprocess.PIPE,
            #                                           start_new_session=True)
            else:
                # Start the Blocknet process using subprocess
                self.xlite_process = subprocess.Popen([xlite_exe],
                                                      stdout=subprocess.PIPE,
                                                      stderr=subprocess.PIPE,
                                                      stdin=subprocess.PIPE,
                                                      start_new_session=True)
            # Check if the process has started
            while self.xlite_process.pid is None:
                time.sleep(1)  # Wait for 1 second before checking again

            pid = self.xlite_process.pid
            logging.info(f"Started Xlite process with PID {pid}: {xlite_exe}")
        except Exception as e:
            logging.error(f"Error: {e}")

    def close_xlite(self):
        # Close the Xlite subprocess if it exists
        if self.xlite_process:
            try:
                self.xlite_process.terminate()
                # logging.info(f"Terminating Xlite subprocess.")
                self.xlite_process.wait(timeout=60)  # Wait for the process to terminate with a timeout of 60 seconds
                logging.info(f"Closed Xlite subprocess.")
                self.xlite_process = None
                return
            except subprocess.TimeoutExpired:
                logging.info(f"Force terminating Xlite subprocess.")
                self.kill_xlite()
                logging.info(f"Xlite subprocess has been force terminated.")
                self.xlite_process = None
                return
            except Exception as e:
                logging.error(f"Error: {e}")
        else:
            self.close_xlite_pids()

    def kill_xlite(self):
        # Kill the Xlite subprocess if it exists
        if self.xlite_process:
            try:
                self.xlite_process.kill()
                logging.info(f"Killed Xlite subprocess.")
                self.xlite_process = None
                return
            except Exception as e:
                logging.error(f"Error: {e}")

    def close_xlite_pids(self):
        # Close the Xlite processes using their PIDs
        for pid in self.xlite_pids:
            try:
                # Get the process object corresponding to the PID
                proc = psutil.Process(pid)
                proc.terminate()
                logging.info(f"Initiated termination of Xlite process with PID {pid}.")
                proc.wait(timeout=60)  # Wait for the process to terminate with a timeout of 60 seconds
                logging.info(f"Xlite process with PID {pid} has been terminated.")
            except psutil.NoSuchProcess:
                logging.warning(f"Xlite process with PID {pid} not found.")
            except psutil.TimeoutExpired:
                logging.warning(f"Force terminating Xlite process with PID {pid}.")
                if proc:
                    proc.kill()
                    proc.wait()
                    logging.info(f"Xlite process with PID {pid} has been force terminated.")
            except Exception as e:
                logging.error(f"Error: {e}")


@contextmanager
def change_directory(directory):
    # Save the current working directory
    saved_directory = os.getcwd()
    try:
        # Change the directory
        os.chdir(directory)
        yield
    finally:
        # Restore the original working directory
        os.chdir(saved_directory)


def download_xlite_bin():
    url = xlite_releases_urls.get((system, machine))
    local_path = os.path.expandvars(os.path.expanduser(aio_blocknet_data_path.get(system)))
    if url is None:
        raise ValueError(f"Unsupported OS or architecture {system} {machine}")

    response = requests.get(url)
    if response.status_code == 200:
        # Extract the archive from memory
        if url.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(response.content), "r") as zip_ref:
                local_path = os.path.join(local_path, xlite_bin_path[system])
                zip_ref.extractall(local_path)
        elif url.endswith(".tar.gz"):
            with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as tar:
                tar.extractall(local_path)
        else:
            print("Unsupported archive format.")
    else:
        print("Failed to download the Xlite binary.")
