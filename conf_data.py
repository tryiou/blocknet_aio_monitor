aio_blocknet_data_path = {
    "Windows": "%appdata%\\AIO_Blocknet",
    "Darwin": "~/Library/Application Support/AIO_Blocknet",
    "Linux": "~/.AIO_Blocknet"
}

blocknet_releases_urls = {
    ("Linux", "x86_64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-x86_64-linux-gnu.tar.gz",
    ("Linux", "aarch64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-aarch64-linux-gnu.tar.gz",
    ("Linux", "riscv64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-riscv64-linux-gnu.tar.gz",
    ("Darwin", "x86_64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-osx64.tar.gz",
    ("Windows", "AMD64"): "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-win64.zip"
}

blocknet_bin_name = "blocknet-qt"

base_xbridge_conf = {
    'ExchangeWallets': '',
    'FullLog': 'true',
    'ShowAllOrders': 'true'
}
blocknet_default_paths = {
    "Windows": "%appdata%\\Blocknet",
    "Darwin": "~/Library/Application Support/Blocknet",
    "Linux": "~/.blocknet"
}

remote_blocknet_conf_url = "https://raw.githubusercontent.com/blocknetdx/block-dx/master/blockchain-configuration-files/wallet-confs/blocknet--v4.3.0.conf"
remote_xbridge_conf_url = "https://raw.githubusercontent.com/blocknetdx/blockchain-configuration-files/master/xbridge-confs/blocknet--v4.3.0.conf"

blockdx_releases_urls = {
    ("Linux", "x86_64"): "https://github.com/blocknetdx/block-dx/releases/download/v1.9.5/BLOCK-DX-1.9.5-linux-x64.tar.gz",
    ("Darwin", "x86_64"): "https://github.com/blocknetdx/block-dx/releases/download/v1.9.5/BLOCK-DX-1.9.5-mac.zip",
    ("Windows", "AMD64"): "https://github.com/blocknetdx/block-dx/releases/download/v1.9.5/BLOCK-DX-1.9.5-win-x64.zip"
}

blockdx_selectedWallets_blocknet = "blocknet--v4.2.0"

blockdx_default_paths = {
    "Windows": "%userprofile%\\AppData\\Local\\BLOCK-DX",
    "Darwin": "~/Library/Application Support/BLOCK-DX",
    "Linux": "~/.config/BLOCK-DX"
}

blockdx_bin_name = {
    "Windows": "BLOCK DX.exe",
    "Linux": "block-dx",
    "Darwin": "BLOCK DX"
}
blockdx_bin_path = {
    "Windows": "BLOCK-DX-1.9.5-win-x64",
    "Linux": "BLOCK-DX-1.9.5-linux-x64",
    "Darwin": ["BLOCK-DX-1.9.5-mac", "BLOCK DX.app", "Contents", "MacOS"]  # List of folders for Darwin
}
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
    "upgradedToV4": True
}

xlite_bin_name = {
    "Windows": "Xlite.exe",
    "Linux": "xlite",
    "Darwin": "xlite"  # ["BLOCK-DX-1.9.5-mac", "BLOCK DX.app", "Contents", "MacOS"]  # List of folders for Darwin
}
xlite_bin_path = {
    "Windows": "XLite-1.0.7-win-x64",
    "Linux": "XLite-1.0.7-linux",
    "Darwin": "XLite-1.0.7-mac"
}

xlite_default_paths = {
    "Windows": "%appdata%\\xlite",
    "Darwin": "~/Library/Application Support/xlite",
    "Linux": "~/.config/xlite"
}
xlite_daemon_default_paths = {
    "Windows": "%appdata%\\CloudChains",
    "Darwin": "~/Library/Application Support/CloudChains",
    "Linux": "~/.config/CloudChains"
}

xlite_releases_urls = {
    ("Linux", "x86_64"): "https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-linux.tar.gz",
    ("Darwin", "x86_64"): "https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-mac.zip",
    ("Windows", "AMD64"): "https://github.com/blocknetdx/xlite/releases/download/v1.0.7/XLite-1.0.7-win-x64.zip"
}

xlite_daemon_bin_name = {
    ("Linux", "x86_64"): "xlite-daemon-linux64",
    ("Darwin", "x86_64"): "xlite-daemon-osx64",
    ("Windows", "AMD64"): "xlite-daemon-win64.exe"
}