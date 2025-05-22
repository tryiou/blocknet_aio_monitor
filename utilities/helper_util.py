import logging
import os
import subprocess
import tarfile
import zipfile

import psutil
import requests

logging.basicConfig(level=logging.DEBUG)


class UtilityHelper:
    def __init__(self):
        pass

    # Shared by all 3 utilities
    def download_file(self, url, tmp_path, final_path, extract_to, system, progress_attr, instance):
        logging.info(f"Starting download from {url}")
        response = requests.get(url, stream=True, timeout=(10, 30))
        response.raise_for_status()

        remote_size = int(response.headers.get('Content-Length', 0))
        with open(tmp_path, 'wb') as f:
            bytes_downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
                    if progress_attr and instance:
                        setattr(instance, progress_attr, (bytes_downloaded / remote_size) * 100)
                        logging.debug(f"Downloaded {bytes_downloaded}/{remote_size} bytes")

        if os.path.getsize(tmp_path) != remote_size:
            os.remove(tmp_path)
            raise ValueError("Download size mismatch")
        logging.info(f"File downloaded successfully to {tmp_path}")

        if url.endswith(".zip"):
            with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            os.remove(tmp_path)
            logging.info(f"Extracted ZIP file to {extract_to}")
        elif url.endswith(".tar.gz"):
            with tarfile.open(tmp_path, 'r:gz') as tar:
                tar.extractall(extract_to)
            os.remove(tmp_path)
            logging.info(f"Extracted TAR.GZ file to {extract_to}")
        elif url.endswith(".dmg") and system == "Darwin":
            os.rename(tmp_path, final_path)
            logging.info(f"Renamed DMG file to {final_path}")

    # Shared by all 3 utilities
    def terminate_processes(self, pids, name):
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                proc.wait(timeout=10)
                logging.info(f"Process {name} PID {pid} terminated successfully")
            except (psutil.NoSuchProcess, psutil.TimeoutExpired) as e:
                if isinstance(e, psutil.TimeoutExpired):
                    proc.kill()
                    logging.warning(f"Process {name} PID {pid}: Timeout expired, killed process")
                else:
                    logging.warning(f"Process {name} PID {pid}: {str(e)}")

    # Shared by BlockdxUtility and XliteUtility
    def handle_dmg(self, dmg_path, mount_path, action):
        if action == "mount":
            if not os.path.ismount(mount_path):
                subprocess.run(["hdiutil", "attach", dmg_path], check=True)
                logging.info(f"Mounted DMG {dmg_path} to {mount_path}")
            else:
                logging.warning(f"{mount_path} is already mounted")
        elif action == "unmount":
            if os.path.ismount(mount_path):
                subprocess.run(["hdiutil", "detach", mount_path], check=True)
                logging.info(f"Unmounted DMG from {mount_path}")
            else:
                logging.warning(f"{mount_path} is not mounted")
