import logging
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class PortablePythonInstaller:
    MINIFORGE_VERSION = "25.3.0-3"

    def __init__(self, target_dir: Path):
        self.target_dir = target_dir.resolve()
        self.system = platform.system()
        self.arch = platform.machine().lower()
        logging.info(f"Detected OS: {self.system}, Arch: {self.arch}")

    def get_installer_filename(self) -> str:
        base = f"Miniforge3-{self.MINIFORGE_VERSION}"
        if self.system == "Windows":
            return f"{base}-Windows-x86_64.exe"
        if self.system == "Linux":
            return f"{base}-Linux-x86_64.sh" if "x86" in self.arch else f"{base}-Linux-aarch64.sh"
        if self.system == "Darwin":
            return f"{base}-MacOSX-{self.arch}.sh"
        raise RuntimeError(f"Unsupported OS: {self.system}")

    def download(self, url: str, dest: Path):
        logging.info(f"Downloading {url}")
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        logging.info(f"Saved installer to {dest}")

    def install(self):
        self.target_dir.mkdir(parents=True, exist_ok=True)
        installer_name = self.get_installer_filename()
        url = f"https://github.com/conda-forge/miniforge/releases/download/{self.MINIFORGE_VERSION}/{installer_name}"
        installer_path = self.target_dir / installer_name
        install_path = self.target_dir / "miniforge"

        if install_path.exists():
            logging.info(f"Removing existing install dir: {install_path}")
            shutil.rmtree(install_path)

        self.download(url, installer_path)

        if self.system == "Windows":
            # Windows .exe silent install requires /D=path as last arg, no quotes, and path must not exist
            cmd = [
                str(installer_path),
                "/InstallationType=JustMe",
                "/AddToPath=0",
                "/RegisterPython=0",
                "/S",
                f"/D={str(install_path)}",  # must be last, no quotes
            ]
        else:
            installer_path.chmod(installer_path.stat().st_mode | stat.S_IEXEC)
            cmd = [str(installer_path), "-b", "-p", str(install_path)]

        logging.info(f"Running installer: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Installer failed: {e}")

        python_bin = install_path / ("Scripts/python.exe" if self.system == "Windows" else "bin/python")
        logging.info(f"✅ Installed portable Python to: {install_path}")
        logging.info(f"🔹 Python executable: {python_bin}")
        logging.info(f"🔹 pip: {python_bin} -m pip")
        logging.info(f"🔹 venv: {python_bin} -m venv /path/to/venv")

        return python_bin


if __name__ == "__main__":
    dest = Path("portable_python")
    installer = PortablePythonInstaller(dest)
    try:
        python_path = installer.install()
    except Exception as e:
        logging.error(f"❌ Installation failed: {e}")
        sys.exit(1)
