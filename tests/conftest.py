"""
Unified pytest configuration and fixtures for all tests.

This module provides shared pytest fixtures and configuration for both
unit and integration tests, ensuring proper isolation from the production
environment (~/.AIO_Blocknet or ~/.config/...).
"""

import json
import os
import shutil

# Add project root to path
import sys
import tempfile
from collections.abc import Callable, Iterable, Iterator
from contextlib import AbstractContextManager, ExitStack, contextmanager
from pathlib import Path
from typing import Any, Optional
from unittest.mock import MagicMock, Mock, patch

import customtkinter as ctk
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

# ============================================================================
# TEST ENVIRONMENT ISOLATION - MODULE LEVEL PATCHING
# ============================================================================

# Create a temporary directory for test isolation
_temp_test_dir = tempfile.mkdtemp(prefix="aio_test_isolation_")

# Disable app file logging for the whole test session: importing the entry
# point (blocknet_aio_monitor) would otherwise attach a real
# RotatingFileHandler to the root logger, whose per-record os.path.exists
# checks consume globally-patched os.path.exists side_effects in unrelated
# tests. Must be set before any app module is imported.
os.environ.setdefault("AIO_NO_FILE_LOG", "1")

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
    Isolate tests from production environment by patching ConfigManager
    before any modules are imported.

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
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "network: marks tests that require network access")
    config.addinivalue_line("markers", "gui: marks tests that interact with GUI components")
    config.addinivalue_line("markers", "filesystem: marks tests that perform file operations")


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
        "extra_option_blocknet_core_conf": [{"addnode": "node1.example.com:41412"}],
    }

    with open(config_path, "w") as f:
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
        "extra_option_blocknet_core_conf": [{"addnode": "node1.example.com:41412"}],
    }

    with open(config_path, "w") as f:
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
    mock_response.headers = {"Content-Length": "1024"}
    mock_response.iter_content = lambda chunk_size: [b"x" * chunk_size]

    with patch("requests.get", return_value=mock_response):
        yield mock_response


@pytest.fixture
def mock_rpc_server():
    """Mock RPC server for testing RPC client interactions."""
    mock_server = MagicMock()
    mock_server.send_rpc_request = MagicMock(return_value={"balance": 100.0})
    mock_server.close = MagicMock()

    with patch("utilities.rpc_client.RPCClient", return_value=mock_server):
        yield mock_server


@pytest.fixture
def mock_process_manager():
    """Mock process management for testing binary handlers."""
    mock_process = MagicMock()
    mock_process.pid = 12345
    mock_process.poll.return_value = None
    mock_process.wait.return_value = None

    with patch("subprocess.Popen", return_value=mock_process), patch("psutil.Process", return_value=mock_process):
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
    binaries["blocknet"] = blocknet_bin

    # Block-DX binary
    blockdx_dir = temp_workspace / "BLOCK-DX-1.0.0"
    blockdx_dir.mkdir()
    blockdx_bin = blockdx_dir / "block-dx"
    blockdx_bin.write_text("#!/bin/bash\necho 'block-dx'")
    blockdx_bin.chmod(0o755)
    binaries["blockdx"] = blockdx_bin

    # XLite binary
    xlite_dir = temp_workspace / "XLite-1.0.7-linux"
    xlite_dir.mkdir()
    xlite_bin = xlite_dir / "xlite"
    xlite_bin.write_text("#!/bin/bash\necho 'xlite'")
    xlite_bin.chmod(0o755)
    binaries["xlite"] = xlite_bin

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

    return {"blocknet": blocknet_conf, "blockdx": blockdx_conf}


# ============================================================================
# GUI FIXTURES
# ============================================================================


@pytest.fixture
def mock_gui_environment():
    """Mock GUI environment for tests."""
    mock_container = MagicMock()
    mock_container.theme_path = "/mock/theme.json"
    mock_container.dirpath = "/mock/dirpath"

    with (
        patch("customtkinter.CTk") as mock_ctk,
        patch("PIL.Image.open") as mock_image,
        patch("utilities.app_container.get_container", return_value=mock_container),
    ):
        mock_root = MagicMock()
        mock_ctk.return_value = mock_root

        yield {"root": mock_root, "ctk": mock_ctk, "image": mock_image}


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
        "workspace": temp_workspace,
        "aio_folder": mock_aio_folder,
        "config_file": mock_config_file,
        "config_manager": config_mgr,
    }


# ============================================================================
# NETWORK MOCK FIXTURES
# ============================================================================


@pytest.fixture
def mock_network_responses():
    """Mock various network responses for testing."""
    responses = {
        "github_release": {
            "tag_name": "v1.0.0",
            "assets": [
                {
                    "name": "blocknet-1.0.0-linux.tar.gz",
                    "browser_download_url": "https://github.com/blocknetdx/blocknet/releases/download/v1.0.0/blocknet-1.0.0-linux.tar.gz",
                }
            ],
        },
        "bootstrap_manifest": {"files": ["blocknet_bootstrap.tar.gz"], "size": 1024000},
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


# ============================================================================
# PHASE 1: CENTRALIZED COMMON MOCK PATTERNS
# ============================================================================


@pytest.fixture
def mock_app_container_base():
    """Base mock container with common properties."""
    container = MagicMock()
    container.system = "Linux"
    container.machine = "x86_64"
    container.aio_folder = "/test/aio"
    container.blocknet_release_url = "http://mock.com/blocknet"
    container.blockdx_release_url = "http://mock.com/blockdx"
    container.xlite_release_url = "http://mock.com/xlite"
    container.blockdx_curpath = "BLOCK-DX-1.0.0"
    container.xlite_curpath = "XLite-1.0.0"
    return container


@pytest.fixture
def mock_gui_root_base():
    """Base mock GUI root with common properties."""
    mock_root = MagicMock()
    mock_root.tooltip_manager = MagicMock()
    mock_root.time_disable_button = 3000
    mock_root.theme_manager = MagicMock()
    mock_root.progress_manager = MagicMock()
    mock_root.network_monitor = MagicMock()
    mock_root.wallet_manager = MagicMock()
    return mock_root


@pytest.fixture
def mock_file_operations_safe():
    """Safe file operation mocks for unit tests."""
    with (
        patch("os.path.exists") as mock_exists,
        patch("os.path.isdir") as mock_isdir,
        patch("os.path.isfile") as mock_isfile,
    ):
        mock_exists.return_value = True
        mock_isdir.return_value = True
        mock_isfile.return_value = False
        yield mock_exists, mock_isdir, mock_isfile


@pytest.fixture
def mock_targeted_file_ops():
    """Targeted file operation mocking - only for specific paths."""

    def mock_exists_side_effect(path):
        return str(path) in ["/test/aio", "/test/aio/blocknet", "/test/aio/blockdx", "/test/aio/xlite"]

    with patch("os.path.exists", side_effect=mock_exists_side_effect):
        yield


@pytest.fixture
def unit_test_mocks():
    """Mocks suitable for unit tests - minimal, focused."""
    with (
        patch("subprocess.Popen") as mock_popen,
        patch("psutil.Process") as mock_psutil,
        patch("os.listdir") as mock_listdir,
    ):
        mock_listdir.return_value = []
        yield mock_popen, mock_psutil, mock_listdir


@pytest.fixture
def integration_test_mocks():
    """Mocks suitable for integration tests - minimal mocking, real operations."""
    # Only essential mocking, use real file systems where possible
    with patch("requests.get") as mock_requests:
        mock_requests.return_value.status_code = 200
        mock_requests.return_value.headers = {"Content-Length": "1024"}
        mock_requests.return_value.iter_content = lambda chunk_size: [b"x" * chunk_size]
        yield mock_requests


@pytest.fixture
def binary_manager_test_setup(mock_app_container_base, mock_file_operations_safe):
    """Setup for binary manager tests using centralized mocks."""
    with (
        patch("gui.binary_manager.get_container", return_value=mock_app_container_base),
        patch("gui.binary_manager.utils") as mock_utils,
    ):
        yield mock_utils


@pytest.fixture
def config_manager_test_setup(temp_workspace):
    """Setup for config manager tests using real file operations."""
    from unittest.mock import patch

    # Allow real file operations but mock ConfigManager methods
    with patch("utilities.config_manager.ConfigManager._get_aio_path", return_value=temp_workspace):
        yield


@pytest.fixture
def utils_test_mocks():
    """Common mock patterns for utils tests."""
    with patch("os.makedirs") as mock_makedirs, patch("shutil.copy2") as mock_copy, patch("os.chmod") as mock_chmod:
        mock_makedirs.return_value = None
        mock_copy.return_value = None
        mock_chmod.return_value = None
        yield mock_makedirs, mock_copy, mock_chmod


def _build_utils_container(with_binaries: bool = False) -> MagicMock:
    """Build a standard mock container for utils tests."""
    container = MagicMock()
    container.conf_data.aio_blocknet_data_path = {"Linux": "/test/data"}
    container.system = "Linux"
    container.aio_folder = "/test/aio"
    if with_binaries:
        container.blocknet_bin = "blocknet"
        container.blockdx_bin = "blockdx"
        container.xlite_bin = "xlite"
        container.xlite_daemon_bin = "xlite_daemon"
    return container


@contextmanager
def _utils_container_env(
    container: MagicMock,
    exists_side_effect: Callable[[Any], bool] | None = None,
    extra_patches: Iterable[AbstractContextManager] = (),
) -> Iterator[MagicMock]:
    """Apply the patch environment shared by utils container fixtures."""
    with ExitStack() as stack:
        stack.enter_context(patch("utilities.utils.get_container", return_value=container))
        stack.enter_context(patch("os.path.expanduser", return_value="/test/data"))
        stack.enter_context(patch("os.path.expandvars", return_value="/test/data"))
        if exists_side_effect is None:
            stack.enter_context(patch("os.path.exists", return_value=False))
        else:
            stack.enter_context(patch("os.path.exists", side_effect=exists_side_effect))
        for ctx in extra_patches:
            stack.enter_context(ctx)
        yield container


@pytest.fixture
def utils_container_setup():
    """Standard container setup for utils tests."""
    with _utils_container_env(_build_utils_container()) as container:
        yield container


@pytest.fixture
def utils_container_setup_with_binaries():
    """Container setup with binary names set for process tests."""
    with _utils_container_env(_build_utils_container(with_binaries=True)) as container:
        yield container


@pytest.fixture
def utils_container_setup_custom_exists():
    """Container setup with custom exists behavior for config tests."""

    def mock_exists_side_effect(path):
        # Handle both joined paths and direct paths
        return str(path) in [
            "/test/aio",
            "/test/data/aio_settings.json",
            "/test/data/cfg.json",
            "/test/aio/aio_settings.json",
            "/test/aio/cfg.json",
        ]

    with _utils_container_env(
        _build_utils_container(),
        exists_side_effect=mock_exists_side_effect,
        extra_patches=(patch("os.rename"),),
    ) as container:
        yield container


# ============================================================================
# PHASE 2: SPECIALIZED FIXTURES FOR TARGET FILES
# ============================================================================


@pytest.fixture
def utils_test_container(temp_workspace):
    """Container setup optimized for utils tests"""
    container = MagicMock()
    container.conf_data.aio_blocknet_data_path = {"Linux": str(temp_workspace / "data")}
    container.system = "Linux"
    container.aio_folder = str(temp_workspace)  # Use temp_workspace directly, not a subdirectory
    return container


@pytest.fixture
def blocknet_handler_container(temp_workspace):
    """Container with extra options for BlocknetHandler tests"""
    container = MagicMock()
    container.conf_data.extra_option_blocknet_core_conf = [
        {"addnode": "node1.example.com:41412"},
        {"addnode": "node2.example.com:41412"},
        {"rpcallowip": "192.168.1.1"},
        {"addnode": "node3.example.com:41412"},
    ]
    container.system = "Linux"
    container.aio_folder = str(temp_workspace)  # Use temp_workspace directly
    return container


@pytest.fixture
def gui_manager_root():
    """Complete GUI root with all manager mocks"""
    root = MagicMock()
    root.time_disable_button = 3000
    root.tooltip_manager = MagicMock()

    # Add all manager mocks with utility attribute
    managers = ["blocknet_manager", "blockdx_manager", "xlite_manager"]
    for manager_name in managers:
        manager = MagicMock()
        manager.utility = MagicMock()
        setattr(root, manager_name, manager)

    # Add common image mocks
    image_attrs = [
        "install_greyed_img",
        "install_img",
        "delete_greyed_img",
        "delete_img",
        "stop_greyed_img",
        "stop_img",
        "start_greyed_img",
        "start_img",
    ]
    for img_attr in image_attrs:
        setattr(root, img_attr, MagicMock())

    return root


@pytest.fixture
def blocknet_handler_setup(blocknet_handler_container, unit_test_mocks):
    """Complete setup for BlocknetHandler tests"""
    with (
        patch("utilities.bin_handlers.blocknet_handler.get_container", return_value=blocknet_handler_container),
        patch("utilities.bin_handlers.blocknet_handler.threading.Thread"),
        patch("utilities.bin_handlers.blocknet_handler.parse_conf_file"),
        patch("utilities.bin_handlers.blocknet_handler.save_conf_to_file"),
        patch("utilities.bin_handlers.blocknet_handler.retrieve_xb_manifest"),
        patch("utilities.bin_handlers.blocknet_handler.retrieve_remote_blocknet_conf"),
        patch("utilities.bin_handlers.blocknet_handler.retrieve_remote_blocknet_xbridge_conf"),
    ):
        yield blocknet_handler_container


@pytest.fixture
def xlite_handler_setup(mock_app_container_base, unit_test_mocks):
    """Setup specifically for XliteHandler tests"""
    with (
        patch("utilities.app_container.get_container", return_value=mock_app_container_base),
        patch("utilities.bin_handlers.xlite_handler.os.path.exists", return_value=True),
        patch("utilities.bin_handlers.xlite_handler.os.makedirs"),
        patch("utilities.bin_handlers.xlite_handler.os.chmod"),
        patch("utilities.bin_handlers.xlite_handler.subprocess.Popen"),
    ):
        yield


@contextmanager
def _utils_test_env(container: MagicMock, temp_workspace: Path) -> Iterator[None]:
    """Apply the patch environment shared by utils test setups using a real temp workspace."""
    data_path = temp_workspace / "data"
    data_path.mkdir(exist_ok=True)

    def mock_exists_side_effect(path):
        path_str = str(path)
        return (
            path_str
            in [str(temp_workspace), str(data_path), str(data_path / "aio_settings.json"), str(data_path / "cfg.json")]
            or path_str.startswith(str(temp_workspace))
            or path_str.startswith(str(data_path))
        )

    with (
        patch("utilities.utils.get_container", return_value=container),
        patch("os.path.expanduser", return_value=str(data_path)),
        patch("os.path.expandvars", return_value=str(data_path)),
        patch("os.path.exists", side_effect=mock_exists_side_effect),
    ):
        yield


@pytest.fixture
def utils_test_setup(utils_test_container, utils_test_mocks, temp_workspace):
    """Complete setup for utils tests"""
    with _utils_test_env(utils_test_container, temp_workspace):
        yield


@pytest.fixture
def utils_test_setup_no_psutil_mock(utils_test_container, temp_workspace):
    """Setup for utils tests without psutil mocking (for process tests)"""
    utils_test_container.blocknet_bin = "blocknet"
    utils_test_container.blockdx_bin = "blockdx"
    utils_test_container.xlite_bin = "xlite"
    utils_test_container.xlite_daemon_bin = "xlite_daemon"
    with _utils_test_env(utils_test_container, temp_workspace):
        yield


@pytest.fixture
def button_test_utils():
    """Common utilities for button-related tests"""
    return {"enable_state": ctk.NORMAL, "disable_state": ctk.DISABLED, "mock_button": Mock()}


@pytest.fixture
def tooltip_test_utils():
    """Common utilities for tooltip-related tests"""
    return {"tooltip": Mock(), "sample_messages": ["test message", "another message", "same message"]}
