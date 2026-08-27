"""
Integration tests for RPC and network communication.

Tests the complete workflow of RPC communication between
Blocknet Core, Block-DX, and XLite.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.integration.helpers.test_helpers import IntegrationTestHelper
from utilities.rpc_client import RPCClient


@pytest.mark.integration
class TestRPCNetworkWorkflow:
    """Integration tests for RPC and network communication."""

    def setup_method(self):
        """Set up test fixtures before each test."""
        self.helper = IntegrationTestHelper()
        self.workspace = self.helper.create_temp_workspace(prefix="rpc_network_")

        # Test RPC credentials
        self.rpc_user = "testuser"
        self.rpc_password = "testpass"
        self.rpc_port = 41414

    def teardown_method(self):
        """Clean up after each test."""
        self.helper.cleanup_workspace(self.workspace)

    def test_rpc_client_initialization_workflow(self):
        """Test RPC client initialization workflow."""
        # Create RPC client
        rpc_client = RPCClient(self.rpc_user, self.rpc_password, self.rpc_port)

        # Verify initialization
        assert rpc_client.rpc_user == self.rpc_user
        assert rpc_client.rpc_password == self.rpc_password
        assert rpc_client.rpc_port == self.rpc_port
        assert rpc_client.session is not None

    def test_rpc_request_workflow(self):
        """Test RPC request workflow."""
        # Create RPC client
        rpc_client = RPCClient(self.rpc_user, self.rpc_password, self.rpc_port)

        # Mock requests.Session.post
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"balance": 100.0},
            "error": None,
            "id": 1
        }

        with patch('requests.Session.post', return_value=mock_response):
            # Send RPC request
            result = rpc_client.send_rpc_request("getbalance")

            # Verify result
            assert result == {"balance": 100.0}

            # Verify request was made
            requests.Session.post.assert_called_once()

    def test_rpc_getbalance_workflow(self):
        """Test RPC getbalance workflow."""
        # Create RPC client
        rpc_client = RPCClient(self.rpc_user, self.rpc_password, self.rpc_port)

        # Mock getbalance response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": 150.5,
            "error": None,
            "id": 1
        }

        with patch('requests.Session.post', return_value=mock_response):
            # Get balance
            balance = rpc_client.send_rpc_request("getbalance")

            # Verify balance
            assert balance == 150.5

    def test_rpc_getinfo_workflow(self):
        """Test RPC getinfo workflow."""
        # Create RPC client
        rpc_client = RPCClient(self.rpc_user, self.rpc_password, self.rpc_port)

        # Mock getinfo response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "version": 1000000,
                "protocolversion": 70015,
                "blocks": 1000,
                "timeoffset": 0,
                "connections": 8,
                "proxy": "",
                "difficulty": 1000.0,
                "testnet": False,
                "moneysupply": 1000000.0,
                "balance": 100.0,
                "newmint": 0.0,
                "stake": 0.0
            },
            "error": None,
            "id": 1
        }

        with patch('requests.Session.post', return_value=mock_response):
            # Get info
            info = rpc_client.send_rpc_request("getinfo")

            # Verify info
            assert info["version"] == 1000000
            assert info["blocks"] == 1000
            assert info["balance"] == 100.0

    def test_rpc_getblockcount_workflow(self):
        """Test RPC getblockcount workflow."""
        # Create RPC client
        rpc_client = RPCClient(self.rpc_user, self.rpc_password, self.rpc_port)

        # Mock getblockcount response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": 1500,
            "error": None,
            "id": 1
        }

        with patch('requests.Session.post', return_value=mock_response):
            # Get block count
            block_count = rpc_client.send_rpc_request("getblockcount")

            # Verify block count
            assert block_count == 1500

    def test_rpc_error_handling_workflow(self):
        """Test RPC error handling workflow."""
        # Create RPC client
        rpc_client = RPCClient(self.rpc_user, self.rpc_password, self.rpc_port)

        # Test various error scenarios

        # 1. HTTP error (non-200 status)
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch('requests.Session.post', return_value=mock_response):
            result = rpc_client.send_rpc_request("getbalance")
            assert result is None

        # 2. Connection error
        with patch('requests.Session.post', side_effect=requests.ConnectionError("Connection refused")):
            result = rpc_client.send_rpc_request("getbalance")
            assert result is None

        # 3. Timeout error
        with patch('requests.Session.post', side_effect=requests.Timeout("Request timeout")):
            result = rpc_client.send_rpc_request("getbalance")
            assert result is None

        # 4. JSON decode error
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

        with patch('requests.Session.post', return_value=mock_response):
            result = rpc_client.send_rpc_request("getbalance")
            assert result is None

    def test_rpc_authentication_workflow(self):
        """Test RPC authentication workflow."""
        # Create RPC client
        rpc_client = RPCClient(self.rpc_user, self.rpc_password, self.rpc_port)

        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"balance": 100.0},
            "error": None,
            "id": 1
        }

        with patch('requests.Session.post', return_value=mock_response) as mock_post:
            # Send request
            rpc_client.send_rpc_request("getbalance")

            # Verify authentication was included
            call_args = mock_post.call_args
            assert call_args[1]['auth'] == (self.rpc_user, self.rpc_password)

    def test_rpc_session_management_workflow(self):
        """Test RPC session management workflow."""
        # Create RPC client
        rpc_client = RPCClient(self.rpc_user, self.rpc_password, self.rpc_port)

        # Verify session exists
        assert rpc_client.session is not None
        assert isinstance(rpc_client.session, requests.Session)

        # Test session close
        with patch.object(rpc_client.session, 'close') as mock_close:
            rpc_client.close()
            mock_close.assert_called_once()

    def test_rpc_request_format_workflow(self):
        """Test RPC request format workflow."""
        # Create RPC client
        rpc_client = RPCClient(self.rpc_user, self.rpc_password, self.rpc_port)

        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"balance": 100.0},
            "error": None,
            "id": 1
        }

        with patch('requests.Session.post', return_value=mock_response) as mock_post:
            # Send request with parameters
            rpc_client.send_rpc_request("getbalance", ["account1"])

            # Verify request format
            call_args = mock_post.call_args
            json_data = call_args[1]['json']

            assert json_data['method'] == 'getbalance'
            assert json_data['params'] == ["account1"]
            assert json_data['jsonrpc'] == '2.0'
            assert 'id' in json_data

    def test_network_request_workflow(self):
        """Test network request workflow."""
        # Mock network response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Length': '1024'}
        mock_response.iter_content = lambda chunk_size: [b'x' * chunk_size]

        with patch('requests.get', return_value=mock_response):
            # Make network request
            response = requests.get(
                "https://github.com/blocknetdx/blocknet/releases/download/v4.4.1/blocknet-4.4.1-linux.tar.gz")

            # Verify response
            assert response.status_code == 200
            assert response.headers['Content-Length'] == '1024'

    def test_network_error_handling_workflow(self):
        """Test network error handling workflow."""
        # Test various network errors

        # 1. Connection error
        with patch('requests.get', side_effect=requests.ConnectionError("Connection refused")):
            with pytest.raises(requests.ConnectionError):
                requests.get("https://example.com")

        # 2. Timeout error
        with patch('requests.get', side_effect=requests.Timeout("Request timeout")):
            with pytest.raises(requests.Timeout):
                requests.get("https://example.com")

        # 3. HTTP error
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status = MagicMock(side_effect=requests.HTTPError("404 Not Found"))

        with patch('requests.get', return_value=mock_response):
            response = requests.get("https://example.com")
            with pytest.raises(requests.HTTPError):
                response.raise_for_status()

    def test_file_download_workflow(self):
        """Test file download workflow."""
        # Mock download response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Length': '1024'}
        mock_response.iter_content = lambda chunk_size: [b'x' * chunk_size]

        download_path = self.workspace / "downloaded_file.tar.gz"

        with patch('requests.get', return_value=mock_response):
            # Simulate download
            response = requests.get("https://example.com/file.tar.gz")

            # Write to file
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Verify download
            assert download_path.exists()
            # The actual size will be 8192 because iter_content returns 8192 bytes
            assert download_path.stat().st_size == 8192

    def test_multiple_rpc_calls_workflow(self):
        """Test multiple RPC calls workflow."""
        # Create RPC client
        rpc_client = RPCClient(self.rpc_user, self.rpc_password, self.rpc_port)

        # Mock multiple responses
        responses = [
            {"result": {"balance": 100.0}, "error": None, "id": 1},
            {"result": {"version": 1000000}, "error": None, "id": 2},
            {"result": 1500, "error": None, "id": 3}
        ]

        mock_post = MagicMock()
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.side_effect = responses

        with patch('requests.Session.post', mock_post):
            # Make multiple calls
            balance = rpc_client.send_rpc_request("getbalance")
            version = rpc_client.send_rpc_request("getinfo")
            block_count = rpc_client.send_rpc_request("getblockcount")

            # Verify results
            assert balance == {"balance": 100.0}
            assert version == {"version": 1000000}
            assert block_count == 1500

            # Verify multiple calls were made
            assert mock_post.call_count == 3

    def test_rpc_with_params_workflow(self):
        """Test RPC calls with parameters."""
        # Create RPC client
        rpc_client = RPCClient(self.rpc_user, self.rpc_password, self.rpc_port)

        # Mock response for getbalance with account
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": 200.0,
            "error": None,
            "id": 1
        }

        with patch('requests.Session.post', return_value=mock_response) as mock_post:
            # Call with parameters
            balance = rpc_client.send_rpc_request("getbalance", ["account1"])

            # Verify result
            assert balance == 200.0

            # Verify parameters were included
            call_args = mock_post.call_args
            assert call_args[1]['json']['params'] == ["account1"]

    def test_rpc_response_parsing_workflow(self):
        """Test RPC response parsing workflow."""
        # Create RPC client
        rpc_client = RPCClient(self.rpc_user, self.rpc_password, self.rpc_port)

        # Test various response formats

        # 1. Success response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"balance": 100.0},
            "error": None,
            "id": 1
        }

        with patch('requests.Session.post', return_value=mock_response):
            result = rpc_client.send_rpc_request("getbalance")
            assert result == {"balance": 100.0}

        # 2. Error response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": None,
            "error": {"code": -32601, "message": "Method not found"},
            "id": 1
        }

        with patch('requests.Session.post', return_value=mock_response):
            result = rpc_client.send_rpc_request("invalid_method")
            # Error responses still return the result (which is None)
            assert result is None

        # 3. Empty result
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": None,
            "error": None,
            "id": 1
        }

        with patch('requests.Session.post', return_value=mock_response):
            result = rpc_client.send_rpc_request("getinfo")
            assert result is None
