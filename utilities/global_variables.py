import os
import platform
try:
    import utilities.conf_data as conf_data
except ModuleNotFoundError:
    import conf_data

# from utilities.conf_data import (blocknet_bin_name, blockdx_bin_name, xlite_bin_name, xlite_daemon_bin_name,
#                                  blocknet_releases_urls, blockdx_releases_urls, xlite_releases_urls,
#                                  aio_blocknet_data_path)

system = platform.system()
aio_folder = os.path.expandvars(os.path.expanduser(conf_data.aio_blocknet_data_path[system]))
machine = platform.machine()
blocknet_bin = conf_data.blocknet_bin_name.get(system, None)
xlite_daemon_bin = conf_data.xlite_daemon_bin_name.get((system, machine))
blockdx_bin = conf_data.blockdx_bin_name.get(system, None)
blockdx_curpath = conf_data.blockdx_bin_path.get(system)
xlite_bin = conf_data.xlite_bin_name.get(system, None)
xlite_curpath = conf_data.xlite_bin_path.get(system)
blocknet_release_url = conf_data.blocknet_releases_urls.get((system, machine))
blockdx_release_url = conf_data.blockdx_releases_urls.get((system, machine))
xlite_release_url = conf_data.xlite_releases_urls.get((system, machine))

blockdx_url = conf_data.blockdx_releases_urls.get((system, machine))
if system == "Darwin":
    blockdx_volume_name = ' '.join(os.path.splitext(os.path.basename(blockdx_url))[0].split('-')[:-1])

xlite_url = conf_data.xlite_releases_urls.get((system, machine))
if system == "Darwin":
    xlite_volume_name = ' '.join(os.path.splitext(os.path.basename(xlite_url))[0].split('-')[:-1])

DIRPATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
themepath = os.path.join(DIRPATH, "theme", "aio.json")
