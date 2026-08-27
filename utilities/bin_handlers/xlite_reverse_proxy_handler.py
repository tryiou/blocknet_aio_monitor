import logging
import os
import re
import socket
import subprocess

from utilities.app_container import AppContainer
from utilities.bin_handlers.base_binutil import BaseBinUtil

logger = logging.getLogger(__name__)


class XliteReverseProxyHandler(BaseBinUtil):
    PORT = 11111

    def __init__(self, container: AppContainer | None = None):
        super().__init__("XliteReverseProxy", container)

        self.release_url = self.container.xlite_reverse_proxy_release_url
        self.bin_name = self.container.xlite_reverse_proxy_bin

        if not self.release_url or not self.bin_name:
            logger.error("Reverse proxy not configured for current system")
            self.executable_path = None
            return

        # Extract version from URL (expecting format: .../vX.Y.Z/...)
        version = None
        if self.release_url:
            match = re.search(r"/v(\d+\.\d+\.\d+)/", self.release_url)
            if match:
                version = match.group(1)

        folder_name = f"xlite-reverse-proxy-{version}" if version else "xlite-reverse-proxy-unknown"
        aio_folder = self.container.aio_folder
        if aio_folder:
            self.executable_path = os.path.join(aio_folder, folder_name, self.bin_name)
        else:
            self.executable_path = None
        self.process = None
        self.running_locally = False

    def port_occupied(self) -> bool:
        """Verify if proxy port is available"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex(("localhost", self.PORT)) == 0

    def start(self):
        if not self.release_url or not self.bin_name:
            logger.error("Proxy config missing")
            return

        if self.port_occupied():
            logger.info("Port 11111 occupied (external proxy detected)")
            self.running_locally = False
            return

        try:
            if not self.executable_path:
                logger.error("Executable path not configured")
                return

            # Type assertion for mypy
            exe_path = self.executable_path  # type: ignore

            # Create directory if needed
            bin_dir = os.path.dirname(exe_path)
            if bin_dir and not os.path.exists(bin_dir):
                os.makedirs(bin_dir, exist_ok=True)

            # Download if missing
            if not os.path.exists(exe_path) and not self.download_standalone_binary(self.release_url, exe_path):
                logger.error("Proxy download failed")
                return

            # Start proxy with dynlist=true argument
            self.process = subprocess.Popen(
                [exe_path, "-dynlist=true"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                cwd=bin_dir,
            )
            self.running_locally = True
            logger.info(f"Proxy started (PID: {self.process.pid} in {bin_dir}) with dynlist=true")

        except Exception as e:
            logger.error(f"Proxy start failed: {e}")
            self.running_locally = False

    def stop(self):
        if not self.running_locally or not self.process:
            return

        try:
            # Check if process is still running
            if self.process.poll() is not None:
                logger.info("Proxy already stopped")
                self.process = None
                self.running_locally = False
                return

            # Try graceful termination first
            logger.info(f"Terminating proxy (PID: {self.process.pid})")
            self.process.terminate()

            # Wait for process to exit
            try:
                self.process.wait(timeout=5)
                logger.info("Proxy terminated gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("Proxy didn't terminate gracefully, forcing kill")
                # Kill the entire process group to ensure cleanup
                try:
                    import signal

                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except (ProcessLookupError, AttributeError):
                    # Process already dead or pgid not available
                    pass
                self.process.kill()
                self.process.wait(timeout=2)
                logger.info("Proxy killed forcefully")

            # Verify process is actually dead
            if self.process.poll() is None:
                logger.error("Proxy process still running after stop attempt")
                # Final attempt to kill
                try:
                    import signal

                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except (ProcessLookupError, AttributeError):
                    pass

        except Exception as e:
            logger.error(f"Proxy stop error: {e}")
            # Try emergency cleanup
            try:
                if self.process and self.process.poll() is None:
                    import signal

                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except (ProcessLookupError, AttributeError):
                pass
        finally:
            self.process = None
            self.running_locally = False

    def __del__(self):
        """Ensure cleanup when object is destroyed"""
        try:
            self.stop()
        except Exception:
            pass
