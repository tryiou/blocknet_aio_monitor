# AIO data folder
aio_blocknet_data_path = {
    "Windows": "%appdata%\\AIO_Blocknet",
    "Linux": "~/.AIO_Blocknet",
    "Darwin": "~/Library/Application Support/AIO_Blocknet"
}

blocknet_bootstrap_url = "https://utils.blocknet.org/Blocknet.zip"
nodes_to_add = [
    "130.185.119.91:41412",
    "75.119.135.155:41412",
    "75.119.157.65:41412",
    "exrproxy1.airdns.org:42111"
]
# Releases links
blocknet_releases_urls = {
    ("Windows", "AMD64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-win64.zip",
    ("Linux",
     "x86_64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-x86_64-linux-gnu.tar.gz",
    ("Linux",
     "aarch64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-aarch64-linux-gnu.tar.gz",
    ("Linux",
     "riscv64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-riscv64-linux-gnu.tar.gz",
    ("Darwin", "x86_64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-osx64.tar.gz"
}
blockdx_releases_urls = {
    ("Windows", "AMD64"): "https://github.com/blocknetdx/block-dx/releases/download/v1.9.5/BLOCK-DX-1.9.5-win-x64.zip",
    ("Linux",
     "x86_64"): "https://github.com/blocknetdx/block-dx/releases/download/v1.9.5/BLOCK-DX-1.9.5-linux-x64.tar.gz",
    ("Darwin", "x86_64"): "https://github.com/blocknetdx/block-dx/releases/download/v1.9.5/BLOCK-DX-1.9.5-mac.dmg"
}
xlite_releases_urls = {
    ("Windows", "AMD64"): "https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-win-x64.zip",
    ("Linux", "x86_64"): "https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-linux.tar.gz",
    ("Darwin", "x86_64"): "https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.dmg"
}

# apps default data path
blocknet_default_paths = {
    "Windows": "%appdata%\\Blocknet",
    "Linux": "~/.blocknet",
    "Darwin": "~/Library/Application Support/Blocknet"
}
blockdx_default_paths = {
    "Windows": "%userprofile%\\AppData\\Local\\BLOCK-DX",
    "Linux": "~/.config/BLOCK-DX",
    "Darwin": "~/Library/Application Support/BLOCK-DX"
}
xlite_default_paths = {
    "Windows": "%appdata%\\xlite",
    "Linux": "~/.config/xlite",
    "Darwin": "~/Library/Application Support/xlite"
}
xlite_daemon_default_paths = {
    "Windows": "%appdata%\\CloudChains",
    "Linux": "~/.config/CloudChains",
    "Darwin": "~/Library/Application Support/CloudChains"
}

# binaries names
blocknet_bin_name = {
    "Windows": "blocknet-qt.exe",
    "Linux": "blocknet-qt",
    "Darwin": "blocknet-qt"
}
blockdx_bin_name = {
    "Windows": "BLOCK DX.exe",
    "Linux": "block-dx",
    "Darwin": ["BLOCK DX.app", "Contents", "MacOS", "BLOCK DX"]
}
xlite_bin_name = {
    "Windows": "XLite.exe",
    "Linux": "xlite",
    "Darwin": ["XLite.app", "Contents", "MacOS", "XLite"]
    # ["BLOCK-DX-1.9.5-mac", "BLOCK DX.app", "Contents", "MacOS"]  # List of folders for Darwin
}
xlite_daemon_bin_name = {
    ("Linux", "x86_64"): "xlite-daemon-linux64",
    ("Windows", "AMD64"): "xlite-daemon-win64.exe",
    ("Darwin", "x86_64"): "xlite-daemon-osx64"
}

# binaries path
blocknet_bin_path = ["blocknet-4.4.1", "bin"]
blockdx_bin_path = {
    "Windows": "BLOCK-DX-1.9.5-win-x64",
    "Linux": "BLOCK-DX-1.9.5-linux-x64",
    "Darwin": "BLOCK-DX-1.9.5-mac"

}
# , "BLOCK DX.app"]
# , "Contents", "MacOS"]  # List of folders for Darwin
xlite_bin_path = {
    "Windows": "XLite-1.0.7-win-x64",
    "Linux": "XLite-1.0.7-linux",
    "Darwin": "XLite-1.0.7-mac"
}

base_xbridge_conf = {
    'ExchangeWallets': '',
    'FullLog': 'true',
    'ShowAllOrders': 'true'
}

remote_blockchain_configuration_repo = "https://raw.githubusercontent.com/blocknetdx/blockchain-configuration-files/master"
manifest = "/manifest-latest.json"
remote_manifest_url = f"{remote_blockchain_configuration_repo}{manifest}"
remote_blocknet_xbridge = "/xbridge-confs/blocknet--v4.3.0.conf"
remote_blocknet_conf = "/wallet-confs/blocknet--v4.3.0.conf"
# manifest-latest.json
# xbridge-confs/ColossusXT--v1.2.3.conf
# wallet-confs/ColossusXT--v1.2.3.conf
remote_blocknet_conf_url = f"{remote_blockchain_configuration_repo}{remote_blocknet_conf}"
remote_xbridge_conf_url = f"{remote_blockchain_configuration_repo}{remote_blocknet_xbridge}"

blockdx_selectedWallets_blocknet = "blocknet--v4.2.0"

blockdx_base_conf = {
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
}

vc_redist_win_url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"