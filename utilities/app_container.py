"""
Centralized application container for managing shared state and configuration.

This module provides a thread-safe singleton container offering better 
encapsulation, dependency injection, and testability.
"""

import logging
import os
import platform
import threading
from dataclasses import dataclass, field
from typing import Any

try:
    import utilities.conf_data as conf_data
except ModuleNotFoundError:
    import conf_data

logger = logging.getLogger(__name__)


@dataclass
class SystemInfo:
    """System information container."""
    system: str = field(default_factory=lambda: platform.system())
    machine: str = field(default_factory=lambda: platform.machine())
    dirpath: str = field(default_factory=lambda: os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    ))


@dataclass
class PathConfig:
    """Path configuration container."""
    aio_folder: str | None = None
    theme_path: str | None = None

    def __post_init__(self):
        if self.aio_folder is None:
            self.aio_folder = os.path.expandvars(
                os.path.expanduser(conf_data.aio_blocknet_data_path[platform.system()])
            )
        if self.theme_path is None:
            self.theme_path = os.path.join(
                os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
                "theme",
                "aio.json"
            )


def _get_value_from_config(config_dict, system: str, machine: str) -> Any | None:
    """
    Get a value from a system-specific config dict.
    
    For dict configs, returns value for (system, machine) or system key.
    For non-dict configs (lists, strings), returns the value directly.
    Returns None if value not found or config is corrupted.
    """
    if not isinstance(config_dict, dict):
        return config_dict

    # Try (system, machine) tuple key first
    key = (system, machine)
    value = config_dict.get(key)
    if value is not None and value != "":
        return value

    # Rosetta fallback for Darwin arm64 -> x86_64
    if system == "Darwin" and machine == "arm64":
        fallback = (system, "x86_64")
        fv = config_dict.get(fallback)
        if fv not in (None, ""):
            logger.info(f"Using Rosetta fallback {fallback} for {(system, machine)}")
            return fv

    # Alias aarch64 <-> arm64
    alias_map = {"aarch64": "arm64", "arm64": "aarch64"}
    if machine in alias_map:
        alias_key = (system, alias_map[machine])
        av = config_dict.get(alias_key)
        if av not in (None, ""):
            return av

    # Try system-only key
    v = config_dict.get(system)
    if v not in (None, ""):
        return v
    return None


@dataclass
class BinaryConfig:
    """Binary configuration container."""
    blocknet_bin: str | None = None
    xlite_daemon_bin: str | None = None
    blockdx_bin: str | None = None
    xlite_bin: str | None = None
    xlite_reverse_proxy_bin: str | None = None

    def __post_init__(self):
        system = platform.system()
        machine = platform.machine()

        if self.blocknet_bin is None:
            self.blocknet_bin = _get_value_from_config(conf_data.blocknet_bin_name, system, machine)
        if self.xlite_daemon_bin is None:
            self.xlite_daemon_bin = _get_value_from_config(conf_data.xlite_daemon_bin_name, system, machine)
        if self.blockdx_bin is None:
            self.blockdx_bin = _get_value_from_config(conf_data.blockdx_bin_name, system, machine)
        if self.xlite_bin is None:
            self.xlite_bin = _get_value_from_config(conf_data.xlite_bin_name, system, machine)
        if self.xlite_reverse_proxy_bin is None:
            self.xlite_reverse_proxy_bin = _get_value_from_config(conf_data.xlite_reverse_proxy_bin_name, system, machine)


@dataclass
class ReleaseConfig:
    """Release URL configuration container."""
    blocknet_release_url: str | None = None
    blockdx_release_url: str | None = None
    xlite_release_url: str | None = None
    xlite_reverse_proxy_release_url: str | None = None

    def __post_init__(self):
        system = platform.system()
        machine = platform.machine()

        if self.blocknet_release_url is None:
            self.blocknet_release_url = _get_value_from_config(
                conf_data.blocknet_releases_urls, system, machine
            )
        if self.blockdx_release_url is None:
            self.blockdx_release_url = _get_value_from_config(
                conf_data.blockdx_releases_urls, system, machine
            )
        if self.xlite_release_url is None:
            self.xlite_release_url = _get_value_from_config(
                conf_data.xlite_releases_urls, system, machine
            )
        if self.xlite_reverse_proxy_release_url is None:
            self.xlite_reverse_proxy_release_url = _get_value_from_config(
                conf_data.xlite_reverse_proxy_releases_urls, system, machine
            )


@dataclass
class PathInfo:
    """Additional path information."""
    blockdx_curpath: str | None = None
    xlite_curpath: str | None = None

    def __post_init__(self):
        system = platform.system()
        machine = platform.machine()
        if self.blockdx_curpath is None:
            self.blockdx_curpath = _get_value_from_config(conf_data.blockdx_bin_path, system, machine)
        if self.xlite_curpath is None:
            self.xlite_curpath = _get_value_from_config(conf_data.xlite_bin_path, system, machine)


@dataclass
class VolumeInfo:
    """macOS volume information for DMG files."""
    blockdx_volume_name: str | None = None
    xlite_volume_name: str | None = None

    def __post_init__(self):
        system = platform.system()
        machine = platform.machine()
        if system == "Darwin":
            blockdx_url = _get_value_from_config(conf_data.blockdx_releases_urls, system, machine)
            if blockdx_url:
                self.blockdx_volume_name = ' '.join(
                    os.path.splitext(os.path.basename(blockdx_url))[0].split('-')[:-1]
                )

            xlite_url = _get_value_from_config(conf_data.xlite_releases_urls, system, machine)
            if xlite_url:
                self.xlite_volume_name = ' '.join(
                    os.path.splitext(os.path.basename(xlite_url))[0].split('-')[:-1]
                )


class AppContainer:
    """
    Thread-safe singleton container for managing application state and configuration.
    
    This class provides proper encapsulation, dependency injection capabilities,
    and thread safety for application state management.
    """

    _instance = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls) -> 'AppContainer':
        """Ensure singleton pattern with thread safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the container with lazy loading."""
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._initialize()
                    AppContainer._initialized = True

    def _initialize(self):
        """Initialize all configuration containers."""
        logger.debug("Initializing AppContainer")

        self._system_info = SystemInfo()
        self._path_config = PathConfig()
        self._binary_config = BinaryConfig()
        self._release_config = ReleaseConfig()
        self._path_info = PathInfo()
        self._volume_info = VolumeInfo()

        # Cache for computed values
        self._computed_cache: dict[str, Any] = {}

        logger.info(f"AppContainer initialized for {self._system_info.system} {self._system_info.machine}")

    @property
    def system(self) -> str:
        """Get the operating system name."""
        return self._system_info.system

    @system.setter
    def system(self, value: str) -> None:
        """Set the operating system name (for testing)."""
        self._system_info.system = value

    @property
    def machine(self) -> str:
        """Get the machine architecture."""
        return self._system_info.machine

    @machine.setter
    def machine(self, value: str) -> None:
        """Set the machine architecture (for testing)."""
        self._system_info.machine = value

    @property
    def dirpath(self) -> str:
        """Get the application directory path."""
        return self._system_info.dirpath

    @dirpath.setter
    def dirpath(self, value: str) -> None:
        """Set the application directory path (for testing)."""
        self._system_info.dirpath = value

    @property
    def aio_folder(self) -> str | None:
        """Get the AIO data folder path."""
        return self._path_config.aio_folder

    @aio_folder.setter
    def aio_folder(self, value: str | None) -> None:
        """Set the AIO data folder path (for testing)."""
        self._path_config.aio_folder = value

    @property
    def theme_path(self) -> str | None:
        """Get the theme file path."""
        return self._path_config.theme_path

    @theme_path.setter
    def theme_path(self, value: str | None) -> None:
        """Set the theme file path (for testing)."""
        self._path_config.theme_path = value

    @property
    def blocknet_bin(self) -> str | None:
        """Get the Blocknet binary name."""
        return self._binary_config.blocknet_bin

    @blocknet_bin.setter
    def blocknet_bin(self, value: str | None) -> None:
        """Set the Blocknet binary name (for testing)."""
        self._binary_config.blocknet_bin = value

    @property
    def xlite_daemon_bin(self) -> str | None:
        """Get the XLite daemon binary name."""
        return self._binary_config.xlite_daemon_bin

    @xlite_daemon_bin.setter
    def xlite_daemon_bin(self, value: str | None) -> None:
        """Set the XLite daemon binary name (for testing)."""
        self._binary_config.xlite_daemon_bin = value

    @property
    def blockdx_bin(self) -> str | None:
        """Get the Block-DX binary name."""
        return self._binary_config.blockdx_bin

    @blockdx_bin.setter
    def blockdx_bin(self, value: str | None) -> None:
        """Set the Block-DX binary name (for testing)."""
        self._binary_config.blockdx_bin = value

    @property
    def xlite_bin(self) -> str | None:
        """Get the XLite binary name."""
        return self._binary_config.xlite_bin

    @xlite_bin.setter
    def xlite_bin(self, value: str | None) -> None:
        """Set the XLite binary name (for testing)."""
        self._binary_config.xlite_bin = value

    @property
    def xlite_reverse_proxy_bin(self) -> str | None:
        """Get the XLite reverse proxy binary name."""
        return self._binary_config.xlite_reverse_proxy_bin

    @xlite_reverse_proxy_bin.setter
    def xlite_reverse_proxy_bin(self, value: str | None) -> None:
        """Set the XLite reverse proxy binary name (for testing)."""
        self._binary_config.xlite_reverse_proxy_bin = value

    @property
    def blocknet_release_url(self) -> str | None:
        """Get the Blocknet release URL."""
        return self._release_config.blocknet_release_url

    @blocknet_release_url.setter
    def blocknet_release_url(self, value: str | None) -> None:
        """Set the Blocknet release URL (for testing)."""
        self._release_config.blocknet_release_url = value

    @property
    def blockdx_release_url(self) -> str | None:
        """Get the Block-DX release URL."""
        return self._release_config.blockdx_release_url

    @blockdx_release_url.setter
    def blockdx_release_url(self, value: str | None) -> None:
        """Set the Block-DX release URL (for testing)."""
        self._release_config.blockdx_release_url = value

    @property
    def xlite_release_url(self) -> str | None:
        """Get the XLite release URL."""
        return self._release_config.xlite_release_url

    @xlite_release_url.setter
    def xlite_release_url(self, value: str | None) -> None:
        """Set the XLite release URL (for testing)."""
        self._release_config.xlite_release_url = value

    @property
    def xlite_reverse_proxy_release_url(self) -> str | None:
        """Get the XLite reverse proxy release URL."""
        return self._release_config.xlite_reverse_proxy_release_url

    @xlite_reverse_proxy_release_url.setter
    def xlite_reverse_proxy_release_url(self, value: str | None) -> None:
        """Set the XLite reverse proxy release URL (for testing)."""
        self._release_config.xlite_reverse_proxy_release_url = value

    @property
    def blockdx_curpath(self) -> str | None:
        """Get the Block-DX current path."""
        return self._path_info.blockdx_curpath

    @blockdx_curpath.setter
    def blockdx_curpath(self, value: str | None) -> None:
        """Set the Block-DX current path (for testing)."""
        self._path_info.blockdx_curpath = value

    @property
    def xlite_curpath(self) -> str | None:
        """Get the XLite current path."""
        return self._path_info.xlite_curpath

    @xlite_curpath.setter
    def xlite_curpath(self, value: str | None) -> None:
        """Set the XLite current path (for testing)."""
        self._path_info.xlite_curpath = value

    @property
    def blockdx_volume_name(self) -> str | None:
        """Get the Block-DX volume name (macOS only)."""
        return self._volume_info.blockdx_volume_name

    @blockdx_volume_name.setter
    def blockdx_volume_name(self, value: str | None) -> None:
        """Set the Block-DX volume name (for testing)."""
        self._volume_info.blockdx_volume_name = value

    @property
    def xlite_volume_name(self) -> str | None:
        """Get the XLite volume name (macOS only)."""
        return self._volume_info.xlite_volume_name

    @xlite_volume_name.setter
    def xlite_volume_name(self, value: str | None) -> None:
        """Set the XLite volume name (for testing)."""
        self._volume_info.xlite_volume_name = value

    @property
    def conf_data(self) -> Any:
        """Get access to conf_data for backward compatibility."""
        return conf_data

    def get_blocknet_executable_path(self) -> str:
        """
        Get the full path to the Blocknet executable.
        
        Returns:
            Full path to the Blocknet binary.
        
        Raises:
            ValueError: If required configuration is missing.
        """
        cache_key = 'blocknet_executable_path'
        if cache_key not in self._computed_cache:
            if not self.blocknet_bin or not self.aio_folder:
                raise ValueError("Blocknet binary not configured for this platform")

            # Get blocknet_bin_path, handling corrupted config
            blocknet_bin_path = _get_value_from_config(
                conf_data.blocknet_bin_path, self.system, self.machine
            )
            if not blocknet_bin_path:
                raise ValueError(f"Blocknet binary path not configured for {self.system} {self.machine}")

            self._computed_cache[cache_key] = os.path.join(
                self.aio_folder,
                *blocknet_bin_path,
                self.blocknet_bin
            )
        return self._computed_cache[cache_key]

    def get_blockdx_executable_path(self) -> str:
        """
        Get the full path to the Block-DX executable.
        
        Returns:
            Full path to the Block-DX binary.
            
        Raises:
            ValueError: If required configuration is missing.
        """
        if self.system == "Darwin":
            if not self.blockdx_release_url or not self.aio_folder:
                raise ValueError("Block-DX release URL not configured for this platform")
            return os.path.join(
                self.aio_folder,
                os.path.basename(self.blockdx_release_url)
            )
        else:
            blockdx_bin_path = _get_value_from_config(
                conf_data.blockdx_bin_path, self.system, self.machine
            )
            blockdx_bin_name = _get_value_from_config(
                conf_data.blockdx_bin_name, self.system, self.machine
            )

            if not blockdx_bin_path or not blockdx_bin_name or not self.aio_folder:
                raise ValueError(f"Block-DX configuration not available for {self.system} {self.machine}")
            return os.path.join(
                self.aio_folder,
                blockdx_bin_path,
                blockdx_bin_name
            )

    def get_xlite_executable_path(self) -> str:
        """
        Get the full path to the XLite executable.
        
        Returns:
            Full path to the XLite binary.
            
        Raises:
            ValueError: If required configuration is missing.
        """
        if self.system == "Darwin":
            if not self.xlite_release_url or not self.aio_folder:
                raise ValueError("XLite release URL not configured for this platform")
            return os.path.join(
                self.aio_folder,
                os.path.basename(self.xlite_release_url)
            )
        else:
            xlite_bin_path = _get_value_from_config(
                conf_data.xlite_bin_path, self.system, self.machine
            )
            xlite_bin_name = _get_value_from_config(
                conf_data.xlite_bin_name, self.system, self.machine
            )

            if not xlite_bin_path or not xlite_bin_name or not self.aio_folder:
                raise ValueError(f"XLite configuration not available for {self.system} {self.machine}")
            return os.path.join(
                self.aio_folder,
                xlite_bin_path,
                xlite_bin_name
            )

    def validate_configuration(self) -> tuple[bool, list]:
        """
        Validate the current configuration.
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        # Check required binaries
        if not self.blocknet_bin:
            errors.append("Blocknet binary not configured for this platform")

        if not self.blockdx_bin:
            errors.append("Block-DX binary not configured for this platform")

        if not self.xlite_bin:
            errors.append("XLite binary not configured for this platform")

        # Check release URLs
        if not self.blocknet_release_url:
            errors.append("Blocknet release URL not configured for this platform")

        if not self.blockdx_release_url:
            errors.append("Block-DX release URL not configured for this platform")

        if not self.xlite_release_url:
            errors.append("XLite release URL not configured for this platform")

        # Check paths
        if not self.aio_folder:
            errors.append("AIO folder path not configured")

        return len(errors) == 0, errors

    def reset(self):
        """
        Reset the container to its initial state.
        Mainly used for testing purposes.
        """
        global _container
        with self._lock:
            AppContainer._instance = None
            AppContainer._initialized = False
            _container = None

    def __repr__(self) -> str:
        """String representation of the container."""
        return (
            f"AppContainer(system={self.system}, machine={self.machine}, "
            f"aio_folder={self.aio_folder})"
        )


# Global container instance
_container = None

def get_container() -> AppContainer:
    """
    Get the singleton AppContainer instance.
    
    Returns:
        The global AppContainer instance.
    """
    global _container
    if _container is None:
        _container = AppContainer()
    return _container
