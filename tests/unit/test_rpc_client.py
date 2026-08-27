"""Tests for utilities/rpc_client.py"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add the project root to the sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.rpc_client import RPCClient

# Test constants
RPC_USER = "testuser"
RPC_PASSWORD = "testpass"
RPC_PORT = 8080


@pytest.fixture
def rpc_client():
    """Create an RPCClient instance for testing."""
    return RPCClient(RPC_USER, RPC_PASSWORD, RPC_PORT)


@pytest.fixture
def mock_response():
    """Create a mock response object."""
    mock = MagicMock()
    return mock


def test_init(rpc_client):
    """Test RPCClient initialization."""
    assert rpc_client.rpc_user == RPC_USER
    assert rpc_client.rpc_password == RPC_PASSWORD
    assert rpc_client.rpc_port == RPC_PORT
    assert rpc_client.session is not None


def test_close(rpc_client):
    """Test closing the session."""
    with patch.object(rpc_client.session, 'close') as mock_close:
        rpc_client.close()
        mock_close.assert_called_once()


@pytest.mark.parametrize("method,params,expected_result", [
    ("getbalance", None, {"balance": 100}),
    ("getbalance", ["account1"], {"balance": 200}),
    ("getinfo", None, {"version": 1000000}),
])
def test_send_rpc_request_success(method, params, expected_result, rpc_client, mock_response):
    """Test successful RPC requests with and without parameters."""
    with patch('utilities.rpc_client.requests.Session.post') as mock_post:
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": expected_result}
        mock_post.return_value = mock_response

        result = rpc_client.send_rpc_request(method, params)

        assert result == expected_result
        mock_post.assert_called_once()

        # Verify request details
        call_args = mock_post.call_args
        assert call_args[1]['json']['method'] == method
        assert call_args[1]['json']['params'] == (params if params is not None else [])
        assert call_args[1]['auth'] == (RPC_USER, RPC_PASSWORD)


@pytest.mark.parametrize("status_code", [400, 500, 503])
def test_send_rpc_request_non_200_status(status_code, rpc_client, mock_response):
    """Test RPC request failure with various non-200 status codes."""
    with patch('utilities.rpc_client.requests.Session.post') as mock_post:
        mock_response.status_code = status_code
        mock_post.return_value = mock_response

        result = rpc_client.send_rpc_request("getbalance")

        assert result is None


@pytest.mark.parametrize("exception", [
    Exception("Connection refused"),
    Exception("Timeout"),
    Exception("Network error"),
])
def test_send_rpc_request_connection_error(exception, rpc_client):
    """Test RPC request failure with various connection errors."""
    with patch('utilities.rpc_client.requests.Session.post') as mock_post:
        mock_post.side_effect = exception

        result = rpc_client.send_rpc_request("getbalance")

        assert result is None


def test_send_rpc_request_no_result_in_response(rpc_client, mock_response):
    """Test RPC request when response has no 'result' key."""
    with patch('utilities.rpc_client.requests.Session.post') as mock_post:
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": {"message": "Method not found"}}
        mock_post.return_value = mock_response

        result = rpc_client.send_rpc_request("invalid_method")

        assert result is None


def test_send_rpc_request_with_empty_params(rpc_client, mock_response):
    """Test RPC request with empty params list."""
    with patch('utilities.rpc_client.requests.Session.post') as mock_post:
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"status": "ok"}}
        mock_post.return_value = mock_response

        result = rpc_client.send_rpc_request("ping", [])

        assert result == {"status": "ok"}
        call_args = mock_post.call_args
        assert call_args[1]['json']['params'] == []


def test_send_rpc_request_default_params(rpc_client, mock_response):
    """Test RPC request with default None params."""
    with patch('utilities.rpc_client.requests.Session.post') as mock_post:
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"status": "ok"}}
        mock_post.return_value = mock_response

        result = rpc_client.send_rpc_request("ping")

        assert result == {"status": "ok"}
        call_args = mock_post.call_args
        assert call_args[1]['json']['params'] == []


def test_send_rpc_request_preserves_json_structure(rpc_client, mock_response):
    """Test that RPC request preserves proper JSON-RPC structure."""
    with patch('utilities.rpc_client.requests.Session.post') as mock_post:
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"data": "test"}}
        mock_post.return_value = mock_response

        rpc_client.send_rpc_request("test_method", ["param1", "param2"])

        call_args = mock_post.call_args
        json_data = call_args[1]['json']

        assert json_data['jsonrpc'] == "2.0"
        assert json_data['id'] == 1
        assert json_data['method'] == "test_method"
        assert json_data['params'] == ["param1", "param2"]


def test_send_rpc_request_uses_session_post(rpc_client, mock_response):
    """Test that RPC request uses session.post with correct arguments."""
    with patch('utilities.rpc_client.requests.Session.post') as mock_post:
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": {"data": "test"}}
        mock_post.return_value = mock_response

        rpc_client.send_rpc_request("test_method")

        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify all expected arguments
        assert 'json' in call_args[1]
        assert 'headers' in call_args[1]
        assert 'auth' in call_args[1]
        assert 'timeout' in call_args[1]
        assert call_args[1]['timeout'] == 10
        assert call_args[1]['headers'] == {'content-type': 'application/json'}
