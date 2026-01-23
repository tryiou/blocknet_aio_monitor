"""
Unified pytest configuration and fixtures for all tests.

This module provides shared pytest fixtures and configuration for both
unit and integration tests, ensuring proper isolation from the production
environment (~/.AIO_Blocknet or ~/.config/...).
"""

import os
import tempfile
import shutil
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import json
import yaml

# Add project root to path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

# ============================================================================
# TEST ENVIRONMENT ISOLATION - MODULE LEVEL PATCHING
# ============================================================================

# Create a temporary directory for test isolation
_temp_test_dir = tempfile.mkdtemp(prefix="aio_test_isolation_")

# Patch modules at import time to prevent production folder access
# These patches must be applied BEFORE any test files import the modules

# Patch ConfigManager class FIRST (before any imports that might use it)
try:
    import utilities.config_manager as cm

    original_get_aio_path = cm.ConfigManager._get_aio_path


    def patched_get_aio_path(self):
        return Path(_temp_test_dir)


    cm.ConfigManager._get_aio_path = patched_get_aio_path
except ImportError:
    pass

# Patch global_variables module
try:
    import utilities.global_variables as gv

    gv.aio_folder = _temp_test_dir
    gv.DIRPATH = _temp_test_dir
    gv.themepath = os.path.join(_temp_test_dir, 'theme.json')
except ImportError:
    # If import fails, the patches will be applied when the module is imported
    pass

# Patch conf_data module
try:
    import utilities.conf_data as cd

    cd._cfg = None
    cd.config = {}
except ImportError:
    pass

# Patch ctk.set_default_color_theme to do nothing (prevent theme loading)
try:
    import customtkinter as ctk

    ctk.set_default_color_theme = lambda x: None
except ImportError:
    pass


# ============================================================================
# TEST ENVIRONMENT ISOLATION
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def isolate_test_environment():
    """
    Isolate tests from production environment by patching global variables
    and ConfigManager before any modules are imported.
    
    This fixture runs automatically for all tests and ensures
    that the ~/.AIO_Blocknet production folder is never accessed.
    
    Creates a temporary directory for test isolation that is cleaned up
    after all tests complete.
    """
    # Yield to allow tests to run
    yield _temp_test_dir

    # Clean up
    shutil.rmtree(_temp_test_dir, ignore_errors=True)


# ============================================================================
# MARKERS
# ============================================================================

def pytest_configure(config):
    """Register custom markers for tests."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "network: marks tests that require network access"
    )
    config.addinivalue_line(
        "markers", "gui: marks tests that interact with GUI components"
    )
    config.addinivalue_line(
        "markers", "filesystem: marks tests that perform file operations"
    )


# ============================================================================
# SHARED TEST FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def temp_workspace():
    """Create a temporary workspace for tests."""
    temp_dir = tempfile.mkdtemp(prefix="aio_test_workspace_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_aio_folder(temp_workspace):
    """Create a mock AIO folder structure."""
    aio_folder = temp_workspace / "AIO_Blocknet"
    aio_folder.mkdir(parents=True, exist_ok=True)

    # Create typical subdirectories
    (aio_folder / "blocknet").mkdir(exist_ok=True)
    (aio_folder / "blockdx").mkdir(exist_ok=True)
    (aio_folder / "xlite").mkdir(exist_ok=True)
    (aio_folder / "bootstrap").mkdir(exist_ok=True)

    return aio_folder


@pytest.fixture
def mock_config_file(temp_workspace):
    """Create a mock configuration file."""
    config_path = temp_workspace / "aio_config.json"
    config_data = {
        "custom_path": str(temp_workspace),
        "xl_pass": "mock_encrypted_password",
        "salt": "mock_salt",
        "extra_option_blocknet_core_conf": [
            {"addnode": "node1.example.com:41412"}
        ]
    }

    with open(config_path, 'w') as f:
        json.dump(config_data, f)

    return config_path


@pytest.fixture
def mock_config_yaml(temp_workspace):
    """Create a mock YAML configuration file."""
    config_path = temp_workspace / "aio_config.yaml"
    config_data = {
        "custom_path": str(temp_workspace),
        "xl_pass": "mock_encrypted_password",
        "salt": "mock_salt",
        "extra_option_blocknet_core_conf": [
            {"addnode": "node1.example.com:41412"}
        ]
    }

    with open(config_path, 'w') as f:
        yaml.dump(config_data, f)

    return config_path


# ============================================================================
# MOCK SERVICE FIXTURES
# ============================================================================

@pytest.fixture
def mock_github_api():
    """Mock GitHub API responses for releases."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {'Content-Length': '1024'}
    mock_response.iter_content = lambda chunk_size: [b'x' * chunk_size]

    with patch('requests.get', return_value=mock_response):
        yield mock_response


@pytest.fixture
def mock_rpc_server():
    """Mock RPC server for testing RPC client interactions."""
    mock_server = MagicMock()
    mock_server.send_rpc_request = MagicMock(return_value={"balance": 100.0})
    mock_server.close = MagicMock()

    with patch('utilities.rpc_client.RPCClient', return_value=mock_server):
        yield mock_server


@pytest.fixture
def mock_process_manager():
    """Mock process management for testing binary handlers."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.poll.return_value = None
    mock_process.wait.return_value = None

    with patch('subprocess.Popen', return_value=mock_process), \
            patch('psutil.Process', return_value=mock_process):
        yield mock_process


# ============================================================================
# FILE SYSTEM FIXTURES
# ============================================================================

@pytest.fixture
def mock_binary_files(temp_workspace):
    """Create mock binary files for testing."""
    binaries = {}

    # Blocknet binary
    blocknet_dir = temp_workspace / "blocknet-4.4.1"
    blocknet_dir.mkdir()
    blocknet_bin = blocknet_dir / "blocknet-qt"
    blocknet_bin.write_text("#!/bin/bash\necho 'blocknet-qt'")
    blocknet_bin.chmod(0o755)
    binaries['blocknet'] = blocknet_bin

    # Block-DX binary
    blockdx_dir = temp_workspace / "BLOCK-DX-1.0.0"
    blockdx_dir.mkdir()
    blockdx_bin = blockdx_dir / "block-dx"
    blockdx_bin.write_text("#!/bin/bash\necho 'block-dx'")
    blockdx_bin.chmod(0o755)
    binaries['blockdx'] = blockdx_bin

    # XLite binary
    xlite_dir = temp_workspace / "XLite-1.0.7-linux"
    xlite_dir.mkdir()
    xlite_bin = xlite_dir / "xlite"
    xlite_bin.write_text("#!/bin/bash\necho 'xlite'")
    xlite_bin.chmod(0o755)
    binaries['xlite'] = xlite_bin

    return binaries


@pytest.fixture
def mock_config_files(temp_workspace):
    """Create mock configuration files."""
    config_dir = temp_workspace / "config"
    config_dir.mkdir()

    # Blocknet config
    blocknet_conf = config_dir / "blocknet.conf"
    blocknet_conf.write_text("""
rpcuser=testuser
rpcpassword=testpass
addnode=node1.example.com:41412
""")

    # Block-DX config
    blockdx_conf = config_dir / "blockdx.conf"
    blockdx_conf.write_text("""
rpcuser=testuser
rpcpassword=testpass
FullLog=true
""")

    return {
        'blocknet': blocknet_conf,
        'blockdx': blockdx_conf
    }


# ============================================================================
# GUI FIXTURES
# ============================================================================

@pytest.fixture
def mock_gui_environment():
    """Mock GUI environment for tests."""
    with patch('customtkinter.CTk') as mock_ctk, \
            patch('PIL.Image.open') as mock_image, \
            patch('utilities.global_variables.themepath', '/mock/theme.json'), \
            patch('utilities.global_variables.DIRPATH', '/mock/dirpath'):
        mock_root = MagicMock()
        mock_ctk.return_value = mock_root

        yield {
            'root': mock_root,
            'ctk': mock_ctk,
            'image': mock_image
        }


# ============================================================================
# WORKFLOW FIXTURES
# ============================================================================

@pytest.fixture
def complete_workflow_setup(temp_workspace, mock_aio_folder, mock_config_file):
    """Complete workflow setup with all components initialized."""
    from utilities.config_manager import ConfigManager

    # Initialize config manager with test folder
    config_mgr = ConfigManager(aio_folder=str(mock_aio_folder))

    yield {
        'workspace': temp_workspace,
        'aio_folder': mock_aio_folder,
        'config_file': mock_config_file,
        'config_manager': config_mgr
    }


# ============================================================================
# NETWORK MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_network_responses():
    """Mock various network responses for testing."""
    responses = {
        'github_release': {
            'tag_name': 'v1.0.0',
            'assets': [
                {
                    'name': 'blocknet-1.0.0-linux.tar.gz',
                    'browser_download_url': 'https://github.com/blocknetdx/blocknet/releases/download/v1.0.0/blocknet-1.0.0-linux.tar.gz'
                }
            ]
        },
        'bootstrap_manifest': {
            'files': ['blocknet_bootstrap.tar.gz'],
            'size': 1024000
        }
    }

    return responses


@pytest.fixture
def mock_download_manager():
    """Mock download manager for testing download workflows."""
    mock_manager = MagicMock()
    mock_manager.download_file = MagicMock(return_value=True)
    mock_manager.extract_archive = MagicMock(return_value=True)
    mock_manager.get_file_size = MagicMock(return_value=1024)

    return mock_manager
