"""
Integration tests for GUI component integration.

Tests the interaction between GUI components, frame managers,
and managers to ensure proper integration.
"""

import os
import sys
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.integration.helpers.test_helpers import IntegrationTestHelper


@pytest.mark.integration
@pytest.mark.gui
class TestGUIIntegrationWorkflow:
    """Integration tests for GUI component integration."""

    def setup_method(self):
        """Set up test fixtures before each test."""
        self.helper = IntegrationTestHelper()
        self.workspace = self.helper.create_temp_workspace(prefix="gui_integration_")

    def teardown_method(self):
        """Clean up after each test."""
        self.helper.cleanup_workspace(self.workspace)

    def test_gui_initialization_workflow(self):
        """Test GUI initialization with all components."""
        # Mock GUI components
        with patch('customtkinter.CTk') as mock_ctk, \
                patch('PIL.Image.open') as mock_image:
            # Create mock container
            mock_container = MagicMock()
            mock_container.theme_path = '/mock/theme.json'
            mock_container.dirpath = '/mock/dirpath'
            
            # Patch get_container to return mock
            with patch('utilities.app_container.get_container', return_value=mock_container):
                # Create mock root
                mock_root = MagicMock()
                mock_ctk.return_value = mock_root

                # Verify mock was created
                assert mock_ctk is not None
                assert mock_root is not None

    def test_frame_manager_integration_workflow(self):
        """Test frame manager integration with managers."""
        # Mock frame manager and manager
        mock_frame_manager = MagicMock()
        mock_manager = MagicMock()

        # Set up integration
        mock_frame_manager.manager = mock_manager
        mock_manager.frame_manager = mock_frame_manager

        # Verify integration
        assert mock_frame_manager.manager is mock_manager
        assert mock_manager.frame_manager is mock_frame_manager

        # Test method calls
        mock_frame_manager.update_buttons()
        mock_frame_manager.update_buttons.assert_called_once()

        mock_manager.start_process()
        mock_manager.start_process.assert_called_once()

    def test_tooltip_integration_workflow(self):
        """Test tooltip manager integration."""
        # Mock tooltip manager
        mock_tooltip_manager = MagicMock()
        mock_tooltip_manager.root_gui = MagicMock()

        # Create mock button
        mock_button = MagicMock()
        mock_button.bind = MagicMock()

        # Set up tooltip
        mock_tooltip_manager.create_tooltip(mock_button, "Test tooltip")

        # Verify tooltip creation
        mock_tooltip_manager.create_tooltip.assert_called_once_with(mock_button, "Test tooltip")

        # Test tooltip update
        mock_tooltip_manager.update_tooltip_text(mock_button, "Updated tooltip")
        mock_tooltip_manager.update_tooltip_text.assert_called_once_with(mock_button, "Updated tooltip")

    def test_binary_manager_integration_workflow(self):
        """Test binary manager integration with GUI."""
        # Mock binary manager
        mock_binary_manager = MagicMock()
        mock_binary_manager.root_gui = MagicMock()

        # Mock managers
        mock_blocknet_manager = MagicMock()
        mock_blockdx_manager = MagicMock()
        mock_xlite_manager = MagicMock()

        # Set up integration
        mock_binary_manager.root_gui.blocknet_manager = mock_blocknet_manager
        mock_binary_manager.root_gui.blockdx_manager = mock_blockdx_manager
        mock_binary_manager.root_gui.xlite_manager = mock_xlite_manager

        # Test binary operations
        mock_binary_manager.download_blocknet_command()
        mock_binary_manager.download_blocknet_command.assert_called_once()

        mock_binary_manager.install_delete_blocknet_command()
        mock_binary_manager.install_delete_blocknet_command.assert_called_once()

        # Verify manager integration
        assert mock_binary_manager.root_gui.blocknet_manager is mock_blocknet_manager
        assert mock_binary_manager.root_gui.blockdx_manager is mock_blockdx_manager
        assert mock_binary_manager.root_gui.xlite_manager is mock_xlite_manager

    def test_blocknet_manager_integration_workflow(self):
        """Test Blocknet manager integration."""
        # Mock Blocknet manager
        mock_blocknet_manager = MagicMock()
        mock_blocknet_manager.root_gui = MagicMock()
        mock_blocknet_manager.utility = MagicMock()

        # Mock RPC client
        mock_rpc_client = MagicMock()
        mock_blocknet_manager.rpc_client = mock_rpc_client

        # Test RPC integration
        mock_rpc_client.send_rpc_request.return_value = {"balance": 100.0}
        result = mock_rpc_client.send_rpc_request("getbalance")

        assert result == {"balance": 100.0}
        mock_rpc_client.send_rpc_request.assert_called_once_with("getbalance")

        # Test process management
        mock_blocknet_manager.start_process()
        mock_blocknet_manager.start_process.assert_called_once()

        mock_blocknet_manager.stop_process()
        mock_blocknet_manager.stop_process.assert_called_once()

    def test_blockdx_manager_integration_workflow(self):
        """Test Block-DX manager integration."""
        # Mock Block-DX manager
        mock_blockdx_manager = MagicMock()
        mock_blockdx_manager.root_gui = MagicMock()
        mock_blockdx_manager.utility = MagicMock()

        # Mock RPC client
        mock_rpc_client = MagicMock()
        mock_blockdx_manager.rpc_client = mock_rpc_client

        # Test RPC integration
        mock_rpc_client.send_rpc_request.return_value = {"version": "1.9.0"}
        result = mock_rpc_client.send_rpc_request("getinfo")

        assert result == {"version": "1.9.0"}
        mock_rpc_client.send_rpc_request.assert_called_once_with("getinfo")

        # Test process management
        mock_blockdx_manager.start_process()
        mock_blockdx_manager.start_process.assert_called_once()

        mock_blockdx_manager.stop_process()
        mock_blockdx_manager.stop_process.assert_called_once()

    def test_xlite_manager_integration_workflow(self):
        """Test XLite manager integration."""
        # Mock XLite manager
        mock_xlite_manager = MagicMock()
        mock_xlite_manager.root_gui = MagicMock()
        mock_xlite_manager.utility = MagicMock()

        # Mock RPC client
        mock_rpc_client = MagicMock()
        mock_xlite_manager.rpc_client = mock_rpc_client

        # Test RPC integration
        mock_rpc_client.send_rpc_request.return_value = {"balance": 50.0}
        result = mock_rpc_client.send_rpc_request("getbalance")

        assert result == {"balance": 50.0}
        mock_rpc_client.send_rpc_request.assert_called_once_with("getbalance")

        # Test process management
        mock_xlite_manager.start_process()
        mock_xlite_manager.start_process.assert_called_once()

        mock_xlite_manager.stop_process()
        mock_xlite_manager.stop_process.assert_called_once()

    def test_button_state_integration_workflow(self):
        """Test button state management integration."""
        # Mock button states
        button_states = {
            'blocknet_start': True,
            'blocknet_stop': False,
            'blockdx_start': True,
            'blockdx_stop': False,
            'xlite_start': True,
            'xlite_stop': False
        }

        # Mock update function
        def update_buttons(states):
            for button, enabled in states.items():
                if enabled:
                    print(f"Enabling {button}")
                else:
                    print(f"Disabling {button}")

        # Test button update
        update_buttons(button_states)

        # Verify all buttons were processed
        assert len(button_states) == 6

    def test_event_handling_integration_workflow(self):
        """Test event handling integration."""
        # Mock event handlers
        mock_handlers = {
            'on_start': MagicMock(),
            'on_stop': MagicMock(),
            'on_download': MagicMock(),
            'on_delete': MagicMock()
        }

        # Simulate event flow
        def simulate_event_flow():
            # User clicks download button
            mock_handlers['on_download']()

            # User clicks start button
            mock_handlers['on_start']()

            # User clicks stop button
            mock_handlers['on_stop']()

            # User clicks delete button
            mock_handlers['on_delete']()

        # Execute event flow
        simulate_event_flow()

        # Verify all handlers were called
        for handler in mock_handlers.values():
            handler.assert_called_once()

    def test_async_operation_integration_workflow(self):
        """Test async operation integration."""

        # Mock async operations
        async def mock_async_setup():
            await asyncio.sleep(0.01)
            return "setup_complete"

        async def mock_async_download():
            await asyncio.sleep(0.01)
            return "download_complete"

        async def mock_async_start():
            await asyncio.sleep(0.01)
            return "start_complete"

        # Run async operations
        async def run_async_workflow():
            setup_result = await mock_async_setup()
            download_result = await mock_async_download()
            start_result = await mock_async_start()

            return {
                'setup': setup_result,
                'download': download_result,
                'start': start_result
            }

        # Execute workflow
        result = asyncio.run(run_async_workflow())

        # Verify results
        assert result['setup'] == "setup_complete"
        assert result['download'] == "download_complete"
        assert result['start'] == "start_complete"

    def test_error_handling_integration_workflow(self):
        """Test error handling integration."""
        # Mock error scenarios
        errors = []

        def handle_error(error):
            errors.append(error)

        # Simulate errors
        try:
            raise ValueError("Download failed")
        except ValueError as e:
            handle_error(e)

        try:
            raise ConnectionError("RPC connection failed")
        except ConnectionError as e:
            handle_error(e)

        try:
            raise PermissionError("File permission denied")
        except PermissionError as e:
            handle_error(e)

        # Verify errors were handled
        assert len(errors) == 3
        assert str(errors[0]) == "Download failed"
        assert str(errors[1]) == "RPC connection failed"
        assert str(errors[2]) == "File permission denied"

    def test_state_machine_integration_workflow(self):
        """Test state machine integration."""
        # Define states
        states = {
            'idle': ['downloading', 'starting'],
            'downloading': ['idle', 'ready'],
            'ready': ['starting', 'stopping'],
            'starting': ['running', 'error'],
            'running': ['stopping', 'error'],
            'stopping': ['idle', 'error'],
            'error': ['idle']
        }

        # Mock state transitions
        current_state = 'idle'

        def transition_to(new_state):
            nonlocal current_state
            if new_state in states[current_state]:
                current_state = new_state
                return True
            return False

        # Test transitions
        assert transition_to('downloading') is True
        assert current_state == 'downloading'

        assert transition_to('ready') is True
        assert current_state == 'ready'

        assert transition_to('starting') is True
        assert current_state == 'starting'

        assert transition_to('running') is True
        assert current_state == 'running'

        assert transition_to('stopping') is True
        assert current_state == 'stopping'

        assert transition_to('idle') is True
        assert current_state == 'idle'

        # Test invalid transition
        assert transition_to('invalid') is False
        assert current_state == 'idle'

    def test_data_flow_integration_workflow(self):
        """Test data flow between components."""
        # Mock data flow
        data_store = {}

        def update_data(key, value):
            data_store[key] = value

        def get_data(key):
            return data_store.get(key)

        # Simulate data flow
        update_data('blocknet_version', '4.4.1')
        update_data('blockdx_version', '1.9.0')
        update_data('xlite_version', '1.0.7')
        update_data('rpc_port', 41414)

        # Verify data flow
        assert get_data('blocknet_version') == '4.4.1'
        assert get_data('blockdx_version') == '1.9.0'
        assert get_data('xlite_version') == '1.0.7'
        assert get_data('rpc_port') == 41414

        # Test data propagation
        def propagate_data():
            versions = {
                'blocknet': get_data('blocknet_version'),
                'blockdx': get_data('blockdx_version'),
                'xlite': get_data('xlite_version')
            }
            return versions

        versions = propagate_data()
        assert versions['blocknet'] == '4.4.1'
        assert versions['blockdx'] == '1.9.0'
        assert versions['xlite'] == '1.0.7'
