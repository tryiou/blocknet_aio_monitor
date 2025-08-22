import logging
import os
import socket
import subprocess
import requests
from utilities import global_variables
from utilities.bin_handlers.base_binutil import BaseBinUtil

logger = logging.getLogger(__name__)

class XliteReverseProxyHandler(BaseBinUtil):
    PORT = 11111

    def __init__(self):
        super().__init__("XliteReverseProxy")
        
        self.release_url = global_variables.xlite_reverse_proxy_release_url
        self.bin_name = global_variables.xlite_reverse_proxy_bin
        
        if not self.release_url or not self.bin_name:
            logger.error("Reverse proxy not configured for current system")
            self.executable_path = None
            return
        
        # Extract version from URL (expecting format: .../vX.Y.Z/...)
        version = None
        if self.release_url:
            import re
            match = re.search(r'/v(\d+\.\d+\.\d+)/', self.release_url)
            if match:
                version = match.group(1)
        
        folder_name = f"xlite-reverse-proxy-{version}" if version else "xlite-reverse-proxy-unknown"
        self.executable_path = os.path.join(
            global_variables.aio_folder,
            folder_name,
            self.bin_name
        )
        self.process = None
        self.running_locally = False

    def port_occupied(self) -> bool:
        """Verify if proxy port is available"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(('localhost', self.PORT)) == 0

    def start(self):
        if not self.release_url or not self.bin_name:
            logger.error("Proxy config missing")
            return
        
        if self.port_occupied():
            logger.info("Port 11111 occupied (external proxy detected)")
            self.running_locally = False
            return
        
        try:
            # Create directory if needed
            bin_dir = os.path.dirname(self.executable_path)
            if not os.path.exists(bin_dir):
                os.makedirs(bin_dir, exist_ok=True)
            
            # Download if missing
            if not os.path.exists(self.executable_path):
                if not self.download_standalone_binary(self.release_url, self.executable_path):
                    logger.error("Proxy download failed")
                    return
            
            # Start proxy with dynlist=true argument
            self.process = subprocess.Popen(
                [self.executable_path, '-dynlist=true'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                cwd=bin_dir
            )
            self.running_locally = True
            logger.info(f"Proxy started (PID: {self.process.pid} in {bin_dir}) with dynlist=true")
            
        except Exception as e:
            logger.error(f"Proxy start failed: {e}")
            self.running_locally = False

    def stop(self):
        if self.running_locally and self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                logger.info("Proxy terminated")
            except Exception as e:
                logger.error(f"Proxy stop error: {e}")
            finally:
                self.process = None
                self.running_locally = False
