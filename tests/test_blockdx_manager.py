import unittest
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock, call

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gui.blockdx_manager import BlockDXManager
from utilities import global_variables
import customtkinter as ctk
import asyncio # Added for asyncio.run

class TestBlockDXManager(unittest.TestCase):
    def setUp(self):
        # Mock global_variables
        self.mock_global_variables = MagicMock()
        self.mock_global_variables.blockdx_release_url = "https://github.com/blocknetdx/block-dx/releases/download/v1.0.0/blockdx.zip"

        # Mock root_gui and its managers
        self.mock_root_gui = MagicMock(spec=ctk.CTk)
        self.mock_root_gui.blocknet_manager = MagicMock()
        self.mock_root_gui.tk = MagicMock() # Add mock for .tk attribute
        self.mock_root_gui.children = {} # Add mock for .children attribute

        # Patch customtkinter components
        self.patcher_ctk_frame = patch('customtkinter.CTkFrame')
        self.MockCTkFrame = self.patcher_ctk_frame.start()
        self.patcher_ctk_label = patch('customtkinter.CTkLabel')
        self.MockCTkLabel = self.patcher_ctk_label.start()
        self.patcher_ctk_booleanvar = patch('customtkinter.BooleanVar')
        self.MockBooleanVar = self.patcher_ctk_booleanvar.start()
        self.patcher_ctk_stringvar = patch('customtkinter.StringVar')
        self.MockStringVar = self.patcher_ctk_stringvar.start()
        self.patcher_ctk_checkbox = patch('custom_tk_mods.ctkCheckBox.CTkCheckBox')
        self.MockCTkCheckBox = self.patcher_ctk_checkbox.start()


        # Patch BlockDXHandler
        self.patcher_blockdx_handler = patch('gui.blockdx_manager.BlockDXHandler')
        self.MockBlockDXHandler = self.patcher_blockdx_handler.start()

        # Patch global variables
        self.patcher_global_variables = patch('gui.blockdx_manager.global_variables', new=self.mock_global_variables)
        self.mock_global_variables = self.patcher_global_variables.start()

        # Initialize BlockDXManager
        self.blockdx_manager = BlockDXManager(self.mock_root_gui)
        self.blockdx_manager.utility = self.MockBlockDXHandler.return_value # Assign the mock instance
        self.blockdx_manager.frame_manager = MagicMock()

    def tearDown(self):
        self.patcher_global_variables.stop()
        self.patcher_blockdx_handler.stop()
        self.patcher_ctk_frame.stop()
        self.patcher_ctk_label.stop()
        self.patcher_ctk_booleanvar.stop()
        self.patcher_ctk_stringvar.stop()
        self.patcher_ctk_checkbox.stop()

    def test_init(self):
        self.assertIsNotNone(self.blockdx_manager.root_gui)
        self.assertIsNotNone(self.blockdx_manager.utility)
        self.assertEqual(self.blockdx_manager.version, ["v1.0.0"])
        self.assertFalse(self.blockdx_manager.process_running)
        self.assertIsNone(self.blockdx_manager.is_config_sync)

    def test_setup(self):
        import asyncio
        with patch('gui.blockdx_manager.BlockDxFrameManager') as MockBlockDxFrameManager:
            asyncio.run(self.blockdx_manager.setup())
            MockBlockDxFrameManager.assert_called_once_with(self.blockdx_manager)
            self.mock_root_gui.after.assert_called_once_with(0, self.blockdx_manager.update_status_blockdx)

    def test_blockdx_check_config_blocknet_not_available(self):
        self.mock_root_gui.blocknet_manager.utility.data_folder = None
        self.mock_root_gui.blocknet_manager.utility.blocknet_conf_local = None
        self.blockdx_manager.blockdx_check_config()
        self.blockdx_manager.utility.compare_and_update_local_conf.assert_not_called()

    def test_blockdx_check_config_blocknet_available(self):
        self.mock_root_gui.blocknet_manager.utility.data_folder = "/mock/blocknet_data"
        self.mock_root_gui.blocknet_manager.utility.blocknet_conf_local = {
            'global': {
                'rpcuser': 'testuser',
                'rpcpassword': 'testpassword'
            }
        }
        self.blockdx_manager.blockdx_check_config()
        expected_xbridge_conf_path = os.path.normpath(os.path.join("/mock/blocknet_data", "xbridge.conf"))
        self.blockdx_manager.utility.compare_and_update_local_conf.assert_called_once_with(
            expected_xbridge_conf_path, 'testuser', 'testpassword'
        )

    def test_update_status_blockdx(self):
        self.blockdx_manager.update_status_blockdx()
        self.blockdx_manager.frame_manager.update_blockdx_process_status_checkbox.assert_called_once()
        self.blockdx_manager.frame_manager.update_blockdx_config_button_checkbox.assert_called_once()
        self.mock_root_gui.after.assert_called_once_with(2000, self.blockdx_manager.update_status_blockdx)
