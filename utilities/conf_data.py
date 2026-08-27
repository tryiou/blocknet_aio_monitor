from .config_manager import ConfigManager

# Singleton config manager instance
_cfg = ConfigManager()
config = _cfg.config

# Expose config values through original variable names
aio_blocknet_data_path = {
    "Windows": "%appdata%\\AIO_Blocknet",
    "Linux": "~/.AIO_Blocknet",
    "Darwin": "~/Library/AIO_Blocknet",
}

blocknet_bootstrap_url = config["blocknet_bootstrap_url"]
blocknet_releases_urls = config["blocknet_releases_urls"]
blockdx_releases_urls = config["blockdx_releases_urls"]
xlite_releases_urls = config["xlite_releases_urls"]
blocknet_default_paths = config["blocknet_default_paths"]
blockdx_default_paths = config["blockdx_default_paths"]
xlite_default_paths = config["xlite_default_paths"]
xlite_daemon_default_paths = config["xlite_daemon_default_paths"]
blocknet_bin_name = config["blocknet_bin_name"]
blockdx_bin_name = config["blockdx_bin_name"]
xlite_bin_name = config["xlite_bin_name"]
xlite_daemon_bin_name = config["xlite_daemon_bin_name"]
blocknet_bin_path = config["blocknet_bin_path"]
blockdx_bin_path = config["blockdx_bin_path"]
xlite_bin_path = config["xlite_bin_path"]
xlite_launch_options = config["xlite_launch_options"]
base_xbridge_conf = config["base_xbridge_conf"]
remote_blockchain_configuration_repo = config["remote_blockchain_configuration_repo"]
manifest = config["manifest"]
remote_manifest_url = config["remote_manifest_url"]
remote_blocknet_xbridge = config["remote_blocknet_xbridge"]
remote_blocknet_conf = config["remote_blocknet_conf"]
remote_blocknet_conf_url = config["remote_blocknet_conf_url"]
remote_xbridge_conf_url = config["remote_xbridge_conf_url"]
blockdx_selectedWallets_blocknet = config["blockdx_selectedWallets_blocknet"]
blockdx_base_conf = config["blockdx_base_conf"]
vc_redist_win_url = config["vc_redist_win_url"]
extra_option_blocknet_core_conf = config["extra_option_blocknet_core_conf"]
xlite_reverse_proxy_releases_urls = config["xlite_reverse_proxy_releases_urls"]
xlite_reverse_proxy_bin_name = config["xlite_reverse_proxy_bin_name"]
