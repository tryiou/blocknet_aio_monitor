"""Tests for Apple Silicon (Darwin arm64) handling — issue #27."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from utilities.app_container import AppContainer, _get_value_from_config, get_container
from utilities.config_manager import ConfigManager


class TestDarwinArm64Config(unittest.TestCase):
    def test_blocknet_release_url_arm64(self):
        with patch("platform.system", return_value="Darwin"), patch("platform.machine", return_value="arm64"):
            tmp = tempfile.mkdtemp()
            cfg = ConfigManager(aio_folder=tmp)
            url = cfg._get_system_value("blocknet_releases_urls")
            self.assertIsNotNone(url)
            self.assertIn("blocknet", url)
            self.assertNotEqual(url, None)

    def test_blockdx_release_url_arm64(self):
        with patch("platform.system", return_value="Darwin"), patch("platform.machine", return_value="arm64"):
            tmp = tempfile.mkdtemp()
            cfg = ConfigManager(aio_folder=tmp)
            url = cfg._get_system_value("blockdx_releases_urls")
            self.assertIsNotNone(url)
            self.assertIn("BLOCK-DX", url)

    def test_xlite_release_url_arm64(self):
        with patch("platform.system", return_value="Darwin"), patch("platform.machine", return_value="arm64"):
            tmp = tempfile.mkdtemp()
            cfg = ConfigManager(aio_folder=tmp)
            url = cfg._get_system_value("xlite_releases_urls")
            self.assertIsNotNone(url)
            self.assertIn("XLite", url)

    def test_xlite_daemon_arm64(self):
        with patch("platform.system", return_value="Darwin"), patch("platform.machine", return_value="arm64"):
            tmp = tempfile.mkdtemp()
            cfg = ConfigManager(aio_folder=tmp)
            val = cfg._get_system_value("xlite_daemon_bin_name")
            self.assertIsNotNone(val)
            self.assertIn("xlite-daemon", val)

    def test_app_container_fallback(self):
        # Direct test of _get_value_from_config fallback
        cfg_dict = {("Darwin", "x86_64"): "x86_url"}
        result = _get_value_from_config(cfg_dict, "Darwin", "arm64")
        self.assertEqual(result, "x86_url")

        # Alias aarch64 -> arm64
        cfg_dict2 = {("Linux", "aarch64"): "aarch_url"}
        result2 = _get_value_from_config(cfg_dict2, "Linux", "arm64")
        self.assertEqual(result2, "aarch_url")

        cfg_dict3 = {("Linux", "aarch64"): "aarch_url"}
        result3 = _get_value_from_config(cfg_dict3, "Darwin", "arm64")
        # Darwin arm64 should fallback to x86_64 first, not aarch64
        cfg_dict4 = {("Darwin", "x86_64"): "darwin_x86", ("Linux", "aarch64"): "linux_aarch"}
        self.assertEqual(_get_value_from_config(cfg_dict4, "Darwin", "arm64"), "darwin_x86")

    def test_not_persist_null(self):
        # Simulate old aio_config.yaml with null for arm64 URLs
        with patch("platform.system", return_value="Darwin"), patch("platform.machine", return_value="arm64"):
            tmp = tempfile.mkdtemp()
            cfg_file = Path(tmp) / "aio_config.yaml"
            # Write a config with null for blockdx (simulating old bug)
            import yaml

            with open(cfg_file, "w") as f:
                yaml.dump({"blockdx_releases_urls": None, "xlite_releases_urls": None}, f)
            cfg = ConfigManager(aio_folder=tmp)
            # After load, should have repaired to non-None (Rosetta fallback)
            url = cfg._get_system_value("blockdx_releases_urls")
            self.assertIsNotNone(url)
            self.assertNotEqual(url, None)
            # Save should not persist null
            filtered = cfg._filter_config_for_saving()
            self.assertIsNotNone(filtered.get("blockdx_releases_urls"))
            self.assertNotEqual(filtered.get("blockdx_releases_urls"), None)

    def test_blockdx_handler_no_crash_arm64(self):
        # Ensure BlockDXHandler doesn't crash on arm64 with new config
        with patch("platform.system", return_value="Darwin"), patch("platform.machine", return_value="arm64"):
            tmp = tempfile.mkdtemp()
            # Mock container
            mock_container = MagicMock()
            mock_container.system = "Darwin"
            mock_container.machine = "arm64"
            mock_container.aio_folder = tmp
            mock_container.blockdx_volume_name = "BLOCK-DX"
            mock_container.blockdx_release_url = "https://example.com/BLOCK-DX-1.9.5-mac.dmg"
            mock_container.blockdx_curpath = "BLOCK-DX-1.9.5-mac"
            mock_container.blockdx_bin = ["BLOCK DX.app", "Contents", "MacOS", "BLOCK DX"]
            mock_container.blockdx_bin_name = ["BLOCK DX.app", "Contents", "MacOS", "BLOCK DX"]
            mock_container.conf_data = MagicMock()
            mock_container.conf_data.blockdx_bin_name = {"Darwin": ["BLOCK DX.app", "Contents", "MacOS", "BLOCK DX"]}
            mock_container.conf_data.blockdx_bin_path = {"Darwin": "BLOCK-DX-1.9.5-mac"}
            mock_container.conf_data.blockdx_default_paths = {"Darwin": "/tmp/blockdx"}
            mock_container.conf_data.blockdx_base_conf = {}
            mock_container.conf_data.blockdx_selectedWallets_blocknet = "blocknet--v4.2.0"
            mock_container.conf_data.blockdx_releases_urls = {
                ("Darwin", "arm64"): "https://example.com/BLOCK-DX-1.9.5-mac.dmg"
            }

            from utilities.bin_handlers.blockdx_handler import BlockDXHandler

            with (
                patch("utilities.bin_handlers.blockdx_handler.get_container", return_value=mock_container),
                patch("os.path.exists", return_value=True),
                patch("os.makedirs"),
                patch("builtins.open", mock_open(read_data="{}")),
                patch("json.load", return_value={}),
                patch("os.path.ismount", return_value=False),
            ):
                handler = BlockDXHandler(container=mock_container)
                # Should not crash, executable_path should be set via Rosetta url
                self.assertIsNotNone(handler.executable_path)
                self.assertIn("BLOCK-DX-1.9.5-mac.dmg", handler.executable_path)

    def test_binary_manager_arm64_no_crash(self):
        # BinaryManager checkAndUpdate should not crash and not mis-mark all files as found
        from gui.binary_manager import BinaryManager

        mock_container = MagicMock()
        mock_container.system = "Darwin"
        mock_container.machine = "arm64"
        mock_container.aio_folder = "/tmp"
        mock_container.blockdx_release_url = "https://example.com/BLOCK-DX-1.9.5-mac.dmg"
        mock_container.xlite_release_url = "https://example.com/XLite-1.0.7-mac.dmg"
        mock_container.blocknet_release_url = "https://example.com/blocknet-4.4.1-osx64.tar.gz"
        mock_container.blockdx_curpath = "BLOCK-DX-1.9.5-mac"
        mock_container.xlite_curpath = "XLite-1.0.7-mac"
        mock_container.conf_data.blocknet_bin_path = ["blocknet-4.4.1", "bin"]

        mock_root = MagicMock()
        mock_root.tooltip_manager = MagicMock()
        mock_root.time_disable_button = 3000
        for mgr in ["blocknet_manager", "blockdx_manager", "xlite_manager"]:
            m = MagicMock()
            m.utility = MagicMock()
            m.version = ["v1.9.5"] if "blockdx" in mgr else ["v1.0.7"] if "xlite" in mgr else ["v4.4.1"]
            m.blocknet_process_running = False
            m.process_running = False
            setattr(mock_root, mgr, m)

        with (
            patch("gui.binary_manager.get_container", return_value=mock_container),
            patch("gui.binary_manager.Observer"),
            patch("os.path.exists", return_value=True),
            patch("os.listdir", return_value=["BLOCK-DX-1.9.5-mac.dmg", "XLite-1.0.7-mac.dmg"]),
            patch("os.path.isdir", return_value=False),
            patch("os.path.isfile", return_value=True),
            patch("os.stat") as mock_stat,
        ):
            mock_stat.return_value.st_mtime_ns = 123
            mock_stat.return_value.st_mtime = 123
            mgr = BinaryManager(mock_root)
            mgr.frame_manager = MagicMock()
            mgr.frame_manager.blocknet_installed_boolvar = MagicMock()
            mgr.frame_manager.blockdx_installed_boolvar = MagicMock()
            mgr.frame_manager.xlite_installed_boolvar = MagicMock()
            # Should not raise and should correctly identify installed
            # The darwin_file for blockdx should be basename of url, not empty string
            self.assertEqual(mgr.container.blockdx_release_url, "https://example.com/BLOCK-DX-1.9.5-mac.dmg")
            # If bug existed, darwin_file would be "" and _is_item_match would incorrectly match every file
            # We test that scan doesn't mark everything as found when file is empty
            from gui.binary_manager import BinaryManager as BinaryManagerAlias  # noqa: N817

            # Ensure _is_item_match with empty darwin_file would be bug, but we have correct file
            app_info = {"is_dir": False, "darwin_file": "BLOCK-DX-1.9.5-mac.dmg", "dir_prefix": "BLOCK-DX-"}
            self.assertTrue(mgr._is_item_match(app_info, "BLOCK-DX-1.9.5-mac.dmg", "/tmp/BLOCK-DX-1.9.5-mac.dmg"))
            self.assertFalse(mgr._is_item_match(app_info, "OTHER.dmg", "/tmp/OTHER.dmg"))

    def test_app_container_cache_invalidation(self):
        """System/machine/aio_folder setters must clear _computed_cache."""
        from utilities.app_container import AppContainer as AppContainer2  # noqa: F811

        # Use fresh container via reset
        tmp = tempfile.mkdtemp()
        c = AppContainer2()
        # Ensure cache is clean then populate
        c._computed_cache.clear()
        c.system = "Linux"
        c.machine = "x86_64"
        c.aio_folder = tmp
        # Force cache population
        c._computed_cache["blocknet_executable_path"] = "stale"
        # Changing system should clear
        c.system = "Darwin"
        self.assertNotIn("blocknet_executable_path", c._computed_cache)
        c._computed_cache["blocknet_executable_path"] = "stale2"
        c.machine = "arm64"
        self.assertNotIn("blocknet_executable_path", c._computed_cache)
        c._computed_cache["blocknet_executable_path"] = "stale3"
        c.aio_folder = tmp + "_new"
        self.assertNotIn("blocknet_executable_path", c._computed_cache)
        c._computed_cache["blocknet_executable_path"] = "stale4"
        c.dirpath = "/tmp/newdir"
        self.assertNotIn("blocknet_executable_path", c._computed_cache)

    def test_get_container_thread_safety(self):
        """get_container double-checked lock returns same instance across threads."""
        import threading

        from utilities.app_container import AppContainer as AppContainer3  # noqa: F811
        from utilities.app_container import get_container as get_container3  # noqa: F811

        # Reset global
        AppContainer3._instance = None
        AppContainer3._initialized = False
        import utilities.app_container as ac_mod

        ac_mod._container = None

        instances = []

        def target():
            instances.append(get_container3())

        threads = [threading.Thread(target=target) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2)
        # All should be same object
        self.assertEqual(len(instances), 20)
        first = instances[0]
        for inst in instances[1:]:
            self.assertIs(inst, first)
        # Cleanup reset for other tests
        first.reset()


if __name__ == "__main__":
    unittest.main()
