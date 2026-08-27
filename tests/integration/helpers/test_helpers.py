"""
Integration test helper utilities.

Provides helper functions and classes for integration testing.
"""

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

from utilities.app_container import AppContainer


class IntegrationTestHelper:
    """Helper class for integration testing."""

    @staticmethod
    def create_temp_workspace(prefix: str = "aio_test_") -> Path:
        """Create a temporary workspace for testing."""
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        return Path(temp_dir)

    @staticmethod
    def cleanup_workspace(workspace: Path) -> None:
        """Clean up a temporary workspace."""
        if workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)

    @staticmethod
    def create_mock_binary(workspace: Path, app_name: str, version: str = "1.0.0") -> Path:
        """Create a mock binary file."""
        binary_dir = workspace / f"{app_name}-{version}"
        binary_dir.mkdir(parents=True, exist_ok=True)

        binary_path = binary_dir / app_name
        binary_path.write_text(f"#!/bin/bash\necho '{app_name} {version}'")
        binary_path.chmod(0o755)

        return binary_path

    @staticmethod
    def create_mock_config(workspace: Path, config_name: str, content: str = "") -> Path:
        """Create a mock configuration file."""
        config_path = workspace / config_name
        config_path.write_text(content)
        return config_path

    @staticmethod
    def mock_file_system_structure(workspace: Path) -> Dict[str, Path]:
        """Create a mock file system structure for testing."""
        structure = {}

        # Create AIO folder structure
        aio_folder = workspace / "AIO_Blocknet"
        aio_folder.mkdir(parents=True, exist_ok=True)
        structure['aio_folder'] = aio_folder

        # Create binary directories
        for app in ['blocknet', 'blockdx', 'xlite']:
            app_dir = aio_folder / app
            app_dir.mkdir(exist_ok=True)
            structure[f'{app}_dir'] = app_dir

        # Create config directory
        config_dir = workspace / "config"
        config_dir.mkdir(exist_ok=True)
        structure['config_dir'] = config_dir

        # Create bootstrap directory
        bootstrap_dir = workspace / "bootstrap"
        bootstrap_dir.mkdir(exist_ok=True)
        structure['bootstrap_dir'] = bootstrap_dir

        return structure

    @staticmethod
    def create_test_data(workspace: Path) -> Dict[str, Any]:
        """Create test data for integration tests."""
        test_data = {}

        # Create mock config data
        config_data = {
            "custom_path": str(workspace),
            "xl_pass": "mock_encrypted_password",
            "salt": "mock_salt",
            "extra_option_blocknet_core_conf": [
                {"addnode": "node1.example.com:41412"},
                {"addnode": "node2.example.com:41412"}
            ]
        }

        config_file = workspace / "aio_config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)

        test_data['config_file'] = config_file
        test_data['config_data'] = config_data

        # Create mock blocknet config
        blocknet_conf = workspace / "blocknet.conf"
        blocknet_conf.write_text("""
rpcuser=testuser
rpcpassword=testpass
addnode=node1.example.com:41412
addnode=node2.example.com:41412
rpcallowip=127.0.0.1
""")
        test_data['blocknet_conf'] = blocknet_conf

        # Create mock blockdx config
        blockdx_conf = workspace / "blockdx.conf"
        blockdx_conf.write_text("""
rpcuser=testuser
rpcpassword=testpass
FullLog=true
selectedWallets_blocknet=BLOCK
""")
        test_data['blockdx_conf'] = blockdx_conf

        return test_data

    @staticmethod
    def patch_app_container(workspace: Path, **kwargs):
        """Patch AppContainer for testing.
        
        Note: The isolate_test_environment fixture in conftest.py already patches
        aio_folder, DIRPATH, and themepath for all tests. This method is kept for
        backward compatibility but should rarely be needed.
        """
        patches = []

        # Create a mock AppContainer
        container = MagicMock(spec=AppContainer)

        # Set up common properties from workspace
        container.dirpath = str(workspace)
        container.aio_folder = str(workspace / "aio")
        container.theme_path = str(workspace / "theme" / "aio.json")

        # Set up system-specific properties if provided
        if 'system' in kwargs:
            container.system = kwargs['system']
        else:
            container.system = "Linux"

        if 'machine' in kwargs:
            container.machine = kwargs['machine']
        else:
            container.machine = "x86_64"

        # Set up binary configurations if provided
        if 'blocknet_bin' in kwargs:
            container.blocknet_bin = kwargs['blocknet_bin']
        if 'blockdx_bin' in kwargs:
            container.blockdx_bin = kwargs['blockdx_bin']
        if 'xlite_bin' in kwargs:
            container.xlite_bin = kwargs['xlite_bin']
        if 'xlite_daemon_bin' in kwargs:
            container.xlite_daemon_bin = kwargs['xlite_daemon_bin']
        if 'xlite_reverse_proxy_bin' in kwargs:
            container.xlite_reverse_proxy_bin = kwargs['xlite_reverse_proxy_bin']

        # Set up release URLs if provided
        if 'blocknet_release_url' in kwargs:
            container.blocknet_release_url = kwargs['blocknet_release_url']
        if 'blockdx_release_url' in kwargs:
            container.blockdx_release_url = kwargs['blockdx_release_url']
        if 'xlite_release_url' in kwargs:
            container.xlite_release_url = kwargs['xlite_release_url']
        if 'xlite_reverse_proxy_release_url' in kwargs:
            container.xlite_reverse_proxy_release_url = kwargs['xlite_reverse_proxy_release_url']

        # Set up current paths if provided
        if 'blockdx_curpath' in kwargs:
            container.blockdx_curpath = kwargs['blockdx_curpath']
        if 'xlite_curpath' in kwargs:
            container.xlite_curpath = kwargs['xlite_curpath']

        # Set up volume names if provided (macOS specific)
        if 'blockdx_volume_name' in kwargs:
            container.blockdx_volume_name = kwargs['blockdx_volume_name']
        if 'xlite_volume_name' in kwargs:
            container.xlite_volume_name = kwargs['xlite_volume_name']

        # Mock conf_data access
        container.conf_data = MagicMock()

        # Patch get_container to return the mock
        patches.append(patch('utilities.app_container.get_container', return_value=container))

        # Apply all patches
        for p in patches:
            p.start()

        return patches

    @staticmethod
    def cleanup_patches(patches: list):
        """Clean up patches."""
        for p in patches:
            p.stop()

    @staticmethod
    def simulate_download_workflow(workspace: Path, app_name: str, version: str = "1.0.0") -> Dict[str, Any]:
        """Simulate a download workflow for testing."""
        result = {}

        # Create mock archive
        archive_name = f"{app_name}-{version}.tar.gz"
        archive_path = workspace / archive_name
        archive_path.write_bytes(b"mock archive content")
        result['archive'] = archive_path

        # Create extraction directory
        extract_dir = workspace / f"{app_name}-{version}"
        extract_dir.mkdir(parents=True, exist_ok=True)
        result['extract_dir'] = extract_dir

        # Create mock binary
        binary_path = extract_dir / app_name
        binary_path.write_text(f"#!/bin/bash\necho '{app_name} {version}'")
        binary_path.chmod(0o755)
        result['binary'] = binary_path

        return result

    @staticmethod
    def verify_file_exists(path: Path, description: str = "File") -> bool:
        """Verify a file exists and is accessible."""
        if not path.exists():
            print(f"ERROR: {description} does not exist: {path}")
            return False

        if not path.is_file():
            print(f"ERROR: {description} is not a file: {path}")
            return False

        # Check if file is readable
        try:
            with open(path, 'r') as f:
                f.read()
        except Exception as e:
            print(f"ERROR: Cannot read {description}: {e}")
            return False

        return True

    @staticmethod
    def verify_directory_exists(path: Path, description: str = "Directory") -> bool:
        """Verify a directory exists and is accessible."""
        if not path.exists():
            print(f"ERROR: {description} does not exist: {path}")
            return False

        if not path.is_dir():
            print(f"ERROR: {description} is not a directory: {path}")
            return False

        return True

    @staticmethod
    def verify_executable(path: Path, description: str = "Executable") -> bool:
        """Verify a file is executable."""
        if not path.exists():
            print(f"ERROR: {description} does not exist: {path}")
            return False

        if not os.access(path, os.X_OK):
            print(f"ERROR: {description} is not executable: {path}")
            return False

        return True


class WorkflowSimulator:
    """Simulate complete workflows for integration testing."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.helper = IntegrationTestHelper()

    def simulate_blocknet_install_workflow(self) -> Dict[str, Any]:
        """Simulate Blocknet installation workflow."""
        result = {}

        # Step 1: Create download directory
        download_dir = self.workspace / "downloads"
        download_dir.mkdir(exist_ok=True)
        result['download_dir'] = download_dir

        # Step 2: Simulate download
        archive_path = download_dir / "blocknet-4.4.1-linux.tar.gz"
        archive_path.write_bytes(b"mock blocknet archive")
        result['archive'] = archive_path

        # Step 3: Simulate extraction
        extract_dir = self.workspace / "blocknet-4.4.1"
        extract_dir.mkdir(parents=True, exist_ok=True)

        # Create blocknet-qt binary
        blocknet_qt = extract_dir / "blocknet-qt"
        blocknet_qt.write_text("#!/bin/bash\necho 'Blocknet Qt'")
        blocknet_qt.chmod(0o755)
        result['binary'] = blocknet_qt

        # Step 4: Create config directory
        config_dir = self.workspace / ".blocknet"
        config_dir.mkdir(exist_ok=True)
        result['config_dir'] = config_dir

        # Step 5: Create blocknet.conf
        blocknet_conf = config_dir / "blocknet.conf"
        blocknet_conf.write_text("""
rpcuser=testuser
rpcpassword=testpass
addnode=node1.example.com:41412
""")
        result['config'] = blocknet_conf

        return result

    def simulate_blockdx_install_workflow(self) -> Dict[str, Any]:
        """Simulate Block-DX installation workflow."""
        result = {}

        # Step 1: Create download directory
        download_dir = self.workspace / "downloads"
        download_dir.mkdir(exist_ok=True)
        result['download_dir'] = download_dir

        # Step 2: Simulate download
        archive_path = download_dir / "block-dx-1.9.0-linux-x64.zip"
        archive_path.write_bytes(b"mock blockdx archive")
        result['archive'] = archive_path

        # Step 3: Simulate extraction
        extract_dir = self.workspace / "BLOCK-DX-1.9.0"
        extract_dir.mkdir(parents=True, exist_ok=True)

        # Create block-dx binary
        blockdx_bin = extract_dir / "block-dx"
        blockdx_bin.write_text("#!/bin/bash\necho 'Block-DX'")
        blockdx_bin.chmod(0o755)
        result['binary'] = blockdx_bin

        # Step 4: Create config directory
        config_dir = self.workspace / ".blockdx"
        config_dir.mkdir(exist_ok=True)
        result['config_dir'] = config_dir

        # Step 5: Create blockdx.conf
        blockdx_conf = config_dir / "blockdx.conf"
        blockdx_conf.write_text("""
rpcuser=testuser
rpcpassword=testpass
FullLog=true
selectedWallets_blocknet=BLOCK
""")
        result['config'] = blockdx_conf

        return result

    def simulate_xlite_install_workflow(self) -> Dict[str, Any]:
        """Simulate XLite installation workflow."""
        result = {}

        # Step 1: Create download directory
        download_dir = self.workspace / "downloads"
        download_dir.mkdir(exist_ok=True)
        result['download_dir'] = download_dir

        # Step 2: Simulate download
        archive_path = download_dir / "XLite-1.0.7-linux.tar.gz"
        archive_path.write_bytes(b"mock xlite archive")
        result['archive'] = archive_path

        # Step 3: Simulate extraction
        extract_dir = self.workspace / "XLite-1.0.7-linux"
        extract_dir.mkdir(parents=True, exist_ok=True)

        # Create xlite binary
        xlite_bin = extract_dir / "xlite"
        xlite_bin.write_text("#!/bin/bash\necho 'XLite'")
        xlite_bin.chmod(0o755)
        result['binary'] = xlite_bin

        # Step 4: Create config directory
        config_dir = self.workspace / ".xlite"
        config_dir.mkdir(exist_ok=True)
        result['config_dir'] = config_dir

        # Step 5: Create xlite.conf
        xlite_conf = config_dir / "xlite.conf"
        xlite_conf.write_text("""
rpcuser=testuser
rpcpassword=testpass
""")
        result['config'] = xlite_conf

        return result

    def simulate_process_lifecycle(self, binary_path: Path) -> Dict[str, Any]:
        """Simulate process lifecycle (start, monitor, stop)."""
        result = {}

        # Create mock process
        import subprocess
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.wait.return_value = None
        mock_process.returncode = None

        result['process'] = mock_process

        # Simulate process state file
        state_file = self.workspace / f"process_{binary_path.name}.state"
        state_file.write_text("running")
        result['state_file'] = state_file

        # Simulate PID file
        pid_file = self.workspace / f"{binary_path.name}.pid"
        pid_file.write_text("12345")
        result['pid_file'] = pid_file

        return result
