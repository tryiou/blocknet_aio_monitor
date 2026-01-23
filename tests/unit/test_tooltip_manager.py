"""Tests for TooltipManager class."""
import pytest
from unittest.mock import MagicMock, patch

from gui.tooltip_manager import TooltipManager
import CTkToolTip

# Test data constants
TEST_MESSAGE = "Test Message"
UPDATED_MESSAGE = "Updated Message"


@pytest.fixture
def mock_parent():
    """Create a mock parent (root_gui)."""
    return MagicMock()


@pytest.fixture
def mock_widget():
    """Create a mock widget."""
    return MagicMock()


@pytest.fixture
def tooltip_manager(mock_parent):
    """Create a TooltipManager instance with mocked dependencies."""
    with patch('gui.tooltip_manager.CTkToolTip.CTkToolTip', autospec=True) as mock_ctktooltip, \
            patch('gui.tooltip_manager.configure_tooltip_text', autospec=True) as mock_configure:
        manager = TooltipManager(mock_parent)
        yield manager, mock_ctktooltip, mock_configure


class TestTooltipManager:
    """Test suite for TooltipManager class."""

    def test_init(self, mock_parent, tooltip_manager):
        """Test TooltipManager initialization."""
        manager, _, _ = tooltip_manager

        assert manager.parent == mock_parent
        assert manager.tooltips == {}

    def test_register_tooltip_creates_tooltip(self, mock_widget, tooltip_manager):
        """Test that register_tooltip creates a new CTkToolTip instance."""
        manager, mock_ctktooltip, _ = tooltip_manager
        mock_tooltip_instance = MagicMock(spec=CTkToolTip.CTkToolTip)
        mock_ctktooltip.return_value = mock_tooltip_instance

        manager.register_tooltip(mock_widget, TEST_MESSAGE)

        mock_ctktooltip.assert_called_once_with(mock_widget, message=TEST_MESSAGE)
        assert mock_widget in manager.tooltips
        assert manager.tooltips[mock_widget] == mock_tooltip_instance

    def test_register_tooltip_with_kwargs(self, mock_widget, tooltip_manager):
        """Test that register_tooltip passes kwargs to CTkToolTip."""
        manager, mock_ctktooltip, _ = tooltip_manager
        mock_tooltip_instance = MagicMock(spec=CTkToolTip.CTkToolTip)
        mock_ctktooltip.return_value = mock_tooltip_instance
        kwargs = {"delay": 1, "follow": True}

        manager.register_tooltip(mock_widget, TEST_MESSAGE, **kwargs)

        mock_ctktooltip.assert_called_once_with(mock_widget, message=TEST_MESSAGE, **kwargs)
        assert manager.tooltips[mock_widget] == mock_tooltip_instance

    def test_register_tooltip_stores_multiple_widgets(self, tooltip_manager):
        """Test that register_tooltip can store multiple widgets."""
        manager, mock_ctktooltip, _ = tooltip_manager
        widget1 = MagicMock()
        widget2 = MagicMock()
        mock_ctktooltip.return_value = MagicMock(spec=CTkToolTip.CTkToolTip)

        manager.register_tooltip(widget1, TEST_MESSAGE)
        manager.register_tooltip(widget2, UPDATED_MESSAGE)

        assert len(manager.tooltips) == 2
        assert widget1 in manager.tooltips
        assert widget2 in manager.tooltips

    def test_update_tooltip_existing_widget(self, mock_widget, tooltip_manager):
        """Test that update_tooltip updates an existing widget's tooltip."""
        manager, _, mock_configure = tooltip_manager
        existing_tooltip = MagicMock(spec=CTkToolTip.CTkToolTip)
        manager.tooltips[mock_widget] = existing_tooltip

        manager.update_tooltip(mock_widget, UPDATED_MESSAGE)

        mock_configure.assert_called_once_with(existing_tooltip, UPDATED_MESSAGE)

    def test_update_tooltip_non_existing_widget(self, mock_widget, tooltip_manager):
        """Test that update_tooltip does nothing for non-existing widget."""
        manager, _, mock_configure = tooltip_manager

        manager.update_tooltip(mock_widget, UPDATED_MESSAGE)

        mock_configure.assert_not_called()

    def test_update_tooltip_with_empty_message(self, mock_widget, tooltip_manager):
        """Test that update_tooltip handles empty message."""
        manager, _, mock_configure = tooltip_manager
        existing_tooltip = MagicMock(spec=CTkToolTip.CTkToolTip)
        manager.tooltips[mock_widget] = existing_tooltip

        manager.update_tooltip(mock_widget, "")

        mock_configure.assert_called_once_with(existing_tooltip, "")

    def test_update_tooltip_preserves_other_widgets(self, mock_widget, tooltip_manager):
        """Test that update_tooltip only affects the specified widget."""
        manager, _, mock_configure = tooltip_manager
        other_widget = MagicMock()
        other_tooltip = MagicMock(spec=CTkToolTip.CTkToolTip)

        manager.tooltips[mock_widget] = MagicMock(spec=CTkToolTip.CTkToolTip)
        manager.tooltips[other_widget] = other_tooltip

        manager.update_tooltip(mock_widget, UPDATED_MESSAGE)

        mock_configure.assert_called_once_with(manager.tooltips[mock_widget], UPDATED_MESSAGE)
        assert manager.tooltips[other_widget] == other_tooltip

    def test_register_tooltip_overwrites_existing(self, mock_widget, tooltip_manager):
        """Test that register_tooltip overwrites existing tooltip for same widget."""
        manager, mock_ctktooltip, _ = tooltip_manager
        first_tooltip = MagicMock(spec=CTkToolTip.CTkToolTip)
        second_tooltip = MagicMock(spec=CTkToolTip.CTkToolTip)
        mock_ctktooltip.side_effect = [first_tooltip, second_tooltip]

        manager.register_tooltip(mock_widget, TEST_MESSAGE)
        manager.register_tooltip(mock_widget, UPDATED_MESSAGE)

        assert len(manager.tooltips) == 1
        assert manager.tooltips[mock_widget] == second_tooltip
        assert manager.tooltips[mock_widget] != first_tooltip
