import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import customtkinter as ctk

from gui.xlite_manager import XliteManager
from utilities.app_container import AppContainer


class TestXliteManager:
    """Test suite for XliteManager class following DRY/SOC/KISS principles."""

    @staticmethod
    def _create_mock_root_gui():
        """Create a mock root GUI with required attributes."""
        mock_root_gui = MagicMock(spec=ctk.CTk)
        mock_root_gui.tk = MagicMock()
        mock_root_gui.children = {}
        mock_root_gui.blocknet_manager = MagicMock()
        mock_root_gui.disable_daemons_conf_check = False
        return mock_root_gui

    @staticmethod
    def _create_mock_container():
        """Create mock AppContainer."""
        mock_container = MagicMock()
        mock_container.xlite_release_url = (
            "https://github.com/BlocknetDX/Xlite/releases/download/v1.0.0/Xlite-v1.0.0-linux-x64.tar.gz"
        )
        return mock_container

    @staticmethod
    def _create_xlite_manager_with_mocks(mock_root_gui, mock_container):
        """Create XliteManager instance with mocked dependencies."""
        with patch("gui.xlite_manager.get_container", return_value=mock_container):
            with patch("gui.xlite_manager.XliteHandler") as mock_xlite_handler:
                mock_handler = MagicMock()
                mock_xlite_handler.return_value = mock_handler
                manager = XliteManager(mock_root_gui)
                manager.utility = mock_handler
                manager.frame_manager = MagicMock()
                return manager, mock_xlite_handler

    def test_init(self):
        """Test XliteManager initialization."""
        mock_root_gui = self._create_mock_root_gui()
        mock_container = self._create_mock_container()

        with patch("gui.xlite_manager.get_container", return_value=mock_container):
            with patch("gui.xlite_manager.XliteHandler") as mock_xlite_handler:
                manager = XliteManager(mock_root_gui)

                assert manager.root_gui is mock_root_gui
                assert manager.utility is not None
                assert manager.version == ["v1.0.0"]
                assert manager.process_running is False
                assert manager.daemon_process_running is False
                mock_xlite_handler.assert_called_once()

    def test_setup(self):
        """Test setup method initializes frame manager and schedules status update."""
        mock_root_gui = self._create_mock_root_gui()
        mock_container = self._create_mock_container()

        manager, _ = self._create_xlite_manager_with_mocks(mock_root_gui, mock_container)

        with patch("gui.xlite_manager.XliteFrameManager") as mock_xlite_frame_manager:
            asyncio.run(manager.setup())
            mock_xlite_frame_manager.assert_called_once_with(manager)
            mock_root_gui.after.assert_called_once_with(0, manager.update_status_xlite)

    def test_refresh_xlite_confs(self):
        """Test refresh_xlite_confs calls utility methods."""
        mock_root_gui = self._create_mock_root_gui()
        mock_container = self._create_mock_container()

        manager, _ = self._create_xlite_manager_with_mocks(mock_root_gui, mock_container)

        manager.refresh_xlite_confs()

        manager.utility.parse_xlite_conf.assert_called_once()
        manager.utility.parse_xlite_daemon_conf.assert_called_once()

    def test_detect_new_xlite_install_and_add_to_xbridge_valid_coins_rpc(self):
        """Test detection when valid coins RPC and blocknet process is running."""
        mock_root_gui = self._create_mock_root_gui()
        mock_container = self._create_mock_container()

        manager, _ = self._create_xlite_manager_with_mocks(mock_root_gui, mock_container)

        manager.utility.valid_coins_rpc = True
        mock_root_gui.blocknet_manager.blocknet_process_running = True
        mock_root_gui.blocknet_manager.utility.valid_rpc = True
        manager.utility.xlite_daemon_confs_local = {"test": "conf"}

        manager.detect_new_xlite_install_and_add_to_xbridge()

        mock_root_gui.blocknet_manager.utility.check_xbridge_conf.assert_called_once_with({"test": "conf"})
        mock_root_gui.blocknet_manager.utility.blocknet_rpc.send_rpc_request.assert_called_once_with(
            "dxloadxbridgeConf"
        )
        assert mock_root_gui.disable_daemons_conf_check is True

    def test_detect_new_xlite_install_and_add_to_xbridge_invalid_coins_rpc(self):
        """Test detection when invalid coins RPC resets disable_daemons_conf_check."""
        mock_root_gui = self._create_mock_root_gui()
        mock_container = self._create_mock_container()

        manager, _ = self._create_xlite_manager_with_mocks(mock_root_gui, mock_container)

        manager.utility.valid_coins_rpc = False
        mock_root_gui.disable_daemons_conf_check = True

        manager.detect_new_xlite_install_and_add_to_xbridge()

        mock_root_gui.blocknet_manager.utility.check_xbridge_conf.assert_not_called()
        mock_root_gui.blocknet_manager.utility.blocknet_rpc.send_rpc_request.assert_not_called()
        assert mock_root_gui.disable_daemons_conf_check is False

    def test_update_status_xlite(self):
        """Test update_status_xlite calls all frame manager updates and schedules next update."""
        mock_root_gui = self._create_mock_root_gui()
        mock_container = self._create_mock_container()

        manager, _ = self._create_xlite_manager_with_mocks(mock_root_gui, mock_container)

        manager.reverse_proxy = MagicMock()
        manager.reverse_proxy_running = False

        with patch.object(manager, "detect_new_xlite_install_and_add_to_xbridge") as mock_detect:
            manager.update_status_xlite()

            mock_detect.assert_called_once()
            manager.frame_manager.update_xlite_process_status_checkbox.assert_called_once()
            manager.frame_manager.update_xlite_store_password_button.assert_called_once()
            manager.frame_manager.update_xlite_daemon_process_status.assert_called_once()
            manager.frame_manager.update_xlite_valid_config_checkbox.assert_called_once()
            manager.frame_manager.update_xlite_daemon_valid_config_checkbox.assert_called_once()
            manager.frame_manager.update_xlite_reverse_proxy_process_status.assert_called_once()
            mock_root_gui.after.assert_called_once_with(2000, manager.update_status_xlite)
