import os
import platform
import logging
import yaml
from pathlib import Path
from typing import Any, Dict

logging.basicConfig(level=logging.DEBUG)


SYSTEM_SPECIFIC_KEYS = [
    'blocknet_releases_urls',
    'blockdx_releases_urls',
    'xlite_releases_urls',
    'blocknet_default_paths',
    'blockdx_default_paths',
    'xlite_default_paths',
    'xlite_daemon_default_paths',
    'blocknet_bin_name',
    'blockdx_bin_name',
    'xlite_bin_name',
    'xlite_daemon_bin_name',
    'blocknet_bin_path',
    'blockdx_bin_path',
    'xlite_bin_path',
    'xlite_launch_options'
]

class ConfigManager:
    def __init__(self):
        self.system = platform.system()
        self.machine = platform.machine()
        self.aio_folder = None
        self.config_template = {
            'blocknet_bootstrap_url': "https://utils.blocknet.org/Blocknet.zip",
            'nodes_to_add': [
                "130.185.119.91:41412",
                "75.119.135.155:41412",
                "75.119.157.65:41412",
                "exrproxy1.airdns.org:42111"
            ],
            'blocknet_releases_urls': {
                ("Windows", "AMD64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-win64.zip",
                ("Linux", "x86_64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-x86_64-linux-gnu.tar.gz",
                ("Linux", "aarch64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-aarch64-linux-gnu.tar.gz",
                ("Linux", "riscv64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-riscv64-linux-gnu.tar.gz",
                ("Darwin", "x86_64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-osx64.tar.gz"
            },
            'blockdx_releases_urls': {
                ("Windows", "AMD64"): "https://github.com/blocknetdx/block-dx/releases/download/v1.9.5/BLOCK-DX-1.9.5-win-x64.zip",
                ("Linux", "x86_64"): "https://github.com/blocknetdx/block-dx/releases/download/v1.9.5/BLOCK-DX-1.9.5-linux-x64.tar.gz",
                ("Darwin", "x86_64"): "https://github.com/blocknetdx/block-dx/releases/download/v1.9.5/BLOCK-DX-1.9.5-mac.dmg"
            },
            'xlite_releases_urls': {
                ("Windows", "AMD64"): "https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-win-x64.zip",
                ("Linux", "x86_64"): "https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-linux.tar.gz",
                ("Darwin", "x86_64"): "https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.dmg"
            },
            'blocknet_default_paths': {
                "Windows": "%appdata%\\Blocknet",
                "Linux": "~/.blocknet",
                "Darwin": "~/Library/Application Support/Blocknet"
            },
            'blockdx_default_paths': {
                "Windows": "%userprofile%\\AppData\\Local\\BLOCK-DX",
                "Linux": "~/.config/BLOCK-DX",
                "Darwin": "~/Library/Application Support/BLOCK-DX"
            },
            'xlite_default_paths': {
                "Windows": "%appdata%\\xlite",
                "Linux": "~/.config/xlite",
                "Darwin": "~/Library/Application Support/xlite"
            },
            'xlite_daemon_default_paths': {
                "Windows": "%appdata%\\CloudChains",
                "Linux": "~/.config/CloudChains",
                "Darwin": "~/Library/Application Support/CloudChains"
            },
            'blocknet_bin_name': {
                "Windows": "blocknet-qt.exe",
                "Linux": "blocknet-qt",
                "Darwin": "blocknet-qt"
            },
            'blockdx_bin_name': {
                "Windows": "BLOCK DX.exe",
                "Linux": "block-dx",
                "Darwin": ["BLOCK DX.app", "Contents", "MacOS", "BLOCK DX"]
            },
            'xlite_bin_name': {
                "Windows": "XLite.exe",
                "Linux": "xlite",
                "Darwin": ["XLite.app", "Contents", "MacOS", "XLite"]
            },
            'xlite_daemon_bin_name': {
                ("Linux", "x86_64"): "xlite-daemon-linux64",
                ("Windows", "AMD64"): "xlite-daemon-win64.exe",
                ("Darwin", "x86_64"): "xlite-daemon-osx64"
            },
            'blocknet_bin_path': ["blocknet-4.4.1", "bin"],
            'blockdx_bin_path': {
                "Windows": "BLOCK-DX-1.9.5-win-x64",
                "Linux": "BLOCK-DX-1.9.5-linux-x64",
                "Darwin": "BLOCK-DX-1.9.5-mac"
            },
            'xlite_bin_path': {
                "Windows": "XLite-1.0.7-win-x64",
                "Linux": "XLite-1.0.7-linux",
                "Darwin": "XLite-1.0.7-mac"
            },
            'xlite_launch_options': {
                "Windows": ["--in-process-gpu"],
                "Linux": [],
                "Darwin": []
            },
            'base_xbridge_conf': {
                'ExchangeWallets': '',
                'FullLog': 'true',
                'ShowAllOrders': 'true'
            },
            'remote_blockchain_configuration_repo': "https://raw.githubusercontent.com/blocknetdx/blockchain-configuration-files/master",
            'manifest': "/manifest-latest.json",
            'remote_manifest_url': "https://raw.githubusercontent.com/blocknetdx/blockchain-configuration-files/master/manifest-latest.json",
            'remote_blocknet_xbridge': "/xbridge-confs/blocknet--v4.3.0.conf",
            'remote_blocknet_conf': "/wallet-confs/blocknet--v4.3.0.conf",
            'remote_blocknet_conf_url': "https://raw.githubusercontent.com/blocknetdx/blockchain-configuration-files/master/wallet-confs/blocknet--v4.3.0.conf",
            'remote_xbridge_conf_url': "https://raw.githubusercontent.com/blocknetdx/blockchain-configuration-files/master/xbridge-confs/blocknet--v4.3.0.conf",
            'blockdx_selectedWallets_blocknet': "blocknet--v4.2.0",
            'blockdx_base_conf': {
                "locale": "en",
                "zoomFactor": 1,
                "pricingSource": "CRYPTO_COMPARE",
                "apiKeys": {},
                "pricingUnit": "BTC",
                "pricingFrequency": 120000,
                "pricingEnabled": True,
                "showWallet": True,
                "confUpdaterDisabled": True,
                "tos": False,
                "autofillAddresses": False,
                "upgradedToV4": True
            },
            'vc_redist_win_url': "https://aka.ms/vs/17/release/vc_redist.x64.exe"
        }
        self._load_config()

    def _get_aio_path(self) -> Path:
        aio_path = os.path.expandvars(os.path.expanduser({
            "Windows": "%appdata%\\AIO_Blocknet",
            "Linux": "~/.AIO_Blocknet",
            "Darwin": "~/Library/AIO_Blocknet"
        }[self.system]))
        os.makedirs(aio_path, exist_ok=True)
        return Path(aio_path)

    def _load_config(self) -> None:
        self.aio_folder = self._get_aio_path()
        config_file = self.aio_folder / "aio_config.yaml"
        
        if config_file.exists():
            with open(config_file, "r") as f:
                filtered_config = yaml.safe_load(f) or {}
            # Start with template
            self.config = self._deep_merge(self.config_template.copy(), {})
            
            # Update with filtered_config, handling system-specific keys
            for key, value in filtered_config.items():
                if key in SYSTEM_SPECIFIC_KEYS:
                    self._set_system_value(key, value)
                else:
                    self.config[key] = value
            logging.info(f"Loaded existing config from {config_file}")
        else:
            self.config = self.config_template.copy()
            self._save_config()
            logging.info(f"Created new config from template at {config_file}")

    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def _get_system_value(self, key):
        """Get system-specific value from in-memory config"""
        current_system_key = (self.system, self.machine)
        value = self.config[key]
        if isinstance(value, dict):
            if current_system_key in value:
                return value[current_system_key]
            elif self.system in value:
                return value[self.system]
            else:
                return None
        return value

    def _set_system_value(self, key, value):
        """Set system-specific value in in-memory config"""
        current_system_key = (self.system, self.machine)
        if key in SYSTEM_SPECIFIC_KEYS:
            if isinstance(self.config[key], dict):
                if current_system_key in self.config[key]:
                    self.config[key][current_system_key] = value
                elif self.system in self.config[key]:
                    self.config[key][self.system] = value
                else:
                    self.config[key] = value
            else:
                self.config[key] = value
        else:
            self.config[key] = value

    def _filter_config_for_saving(self) -> dict:
        """Create config with system-specific values stored directly (no dict wrapping)"""
        filtered = {}
        for key in self.config:
            if key in SYSTEM_SPECIFIC_KEYS:
                # Store system-specific values directly (without dict nesting)
                system_value = self._get_system_value(key)
                filtered[key] = system_value
            else:
                filtered[key] = self.config[key]
        return filtered

    def _save_config(self) -> None:
        config_file = self.aio_folder / "aio_config.yaml"
        filtered_config = self._filter_config_for_saving()
        with open(config_file, "w") as f:
            yaml.dump(filtered_config, f, default_flow_style=False)
        logging.info(f"Saved filtered config to {config_file}")
