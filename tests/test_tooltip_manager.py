import unittest
import os
import sys
from unittest.mock import MagicMock, patch, call

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from gui.tooltip_manager import TooltipManager
from utilities import utils
import CTkToolTip

class TestTooltipManager(unittest.TestCase):
    def setUp(self):
        # Mock parent (root_gui)
        self.mock_parent = MagicMock()

        # Patch CTkToolTip and utils.configure_tooltip_text
        self.patcher_ctktooltip = patch('gui.tooltip_manager.CTkToolTip.CTkToolTip', autospec=True)
        self.patcher_configure_tooltip_text = patch('gui.tooltip_manager.configure_tooltip_text', autospec=True)

        self.MockCTkToolTip = self.patcher_ctktooltip.start()
        self.mock_configure_tooltip_text = self.patcher_configure_tooltip_text.start()

        # Initialize TooltipManager
        self.tooltip_manager = TooltipManager(self.mock_parent)

    def tearDown(self):
        self.patcher_ctktooltip.stop()
        self.patcher_configure_tooltip_text.stop()

    def test_init(self):
        self.assertEqual(self.tooltip_manager.parent, self.mock_parent)
        self.assertEqual(self.tooltip_manager.tooltips, {})

    def test_register_tooltip(self):
        mock_widget = MagicMock()
        test_msg = "Test Message"
        test_kwargs = {"delay": 1, "follow": True}

        # Simulate CTkToolTip returning a mock tooltip instance
        mock_tooltip_instance = MagicMock(spec=CTkToolTip.CTkToolTip)
        self.MockCTkToolTip.return_value = mock_tooltip_instance

        self.tooltip_manager.register_tooltip(mock_widget, test_msg, **test_kwargs)

        self.MockCTkToolTip.assert_called_once_with(mock_widget, message=test_msg, **test_kwargs)
        self.assertIn(mock_widget, self.tooltip_manager.tooltips)
        self.assertEqual(self.tooltip_manager.tooltips[mock_widget], mock_tooltip_instance)

    def test_update_tooltip_existing_widget(self):
        mock_widget = MagicMock()
        existing_tooltip = MagicMock(spec=CTkToolTip.CTkToolTip)
        self.tooltip_manager.tooltips[mock_widget] = existing_tooltip
        new_msg = "Updated Message"

        self.tooltip_manager.update_tooltip(mock_widget, new_msg)

        self.mock_configure_tooltip_text.assert_called_once_with(existing_tooltip, new_msg)

    def test_update_tooltip_non_existing_widget(self):
        mock_widget = MagicMock()
        new_msg = "Updated Message"

        self.tooltip_manager.update_tooltip(mock_widget, new_msg)

        self.mock_configure_tooltip_text.assert_not_called()
