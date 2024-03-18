from conf_data import (blocknet_bin_name, blockdx_bin_name, xlite_bin_name, xlite_daemon_bin_name,
                       blocknet_releases_urls, blockdx_releases_urls, xlite_releases_urls, aio_blocknet_data_path)
import platform
import os

system = platform.system()
machine = platform.machine()
blocknet_bin = blocknet_bin_name.get(system, None)
xlite_daemon_bin = xlite_daemon_bin_name.get((system, machine))
blockdx_bin = blockdx_bin_name.get(system, None)
xlite_bin = xlite_bin_name.get(system, None)
aio_folder = os.path.expandvars(os.path.expanduser(aio_blocknet_data_path[system]))
blocknet_release_url = blocknet_releases_urls.get((system, machine))
blockdx_release_url = blockdx_releases_urls.get((system, machine))
xlite_release_url = xlite_releases_urls.get((system, machine))

blockdx_url = blockdx_releases_urls.get((system, machine))
if system == "Darwin":
    blockdx_volume_name = ' '.join(os.path.splitext(os.path.basename(blockdx_url))[0].split('-')[:-1])

xlite_url = xlite_releases_urls.get((system, machine))
if system == "Darwin":
    xlite_volume_name = ' '.join(os.path.splitext(os.path.basename(xlite_url))[0].split('-')[:-1])



DIRPATH = os.path.dirname(os.path.abspath(__file__))
themepath = os.path.join(DIRPATH, "theme", "aio.json")
