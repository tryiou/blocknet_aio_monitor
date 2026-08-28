import logging

import requests

from gui.constants import RPC_TIMEOUT_S

logger = logging.getLogger(__name__)


class RPCClient:
    """
    Unified RPC client for Blocknet and Xlite handlers.
    Provides connection pooling and consistent error handling.
    """

    def __init__(self, rpc_user, rpc_password, rpc_port):
        """
        Initialize the RPC client.

        Args:
            rpc_user: RPC username
            rpc_password: RPC password
            rpc_port: RPC port number
        """
        self.rpc_user = rpc_user
        self.rpc_password = rpc_password
        self.rpc_port = rpc_port
        self.session = requests.Session()

        # Configure connection pooling for better performance
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def send_rpc_request(self, method=None, params=None):
        """
        Send an RPC request to the local daemon.

        Args:
            method: RPC method name
            params: List of parameters for the RPC method

        Returns:
            RPC result on success, None on failure
        """
        url = f"http://localhost:{self.rpc_port}"
        headers = {"content-type": "application/json"}
        auth = (self.rpc_user, self.rpc_password)
        data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params if params is not None else [],
            "id": 1,
        }

        try:
            response = self.session.post(url, json=data, headers=headers, auth=auth, timeout=RPC_TIMEOUT_S)
            if response.status_code != 200:
                return None

            json_answer = response.json()
            if "result" in json_answer:
                return json_answer["result"]
            else:
                return None

        except requests.RequestException:
            # Connection refused/failed - daemon not running (expected behavior)
            return None
        except Exception as ex:
            logger.exception(f"An unexpected error occurred while sending RPC request: {ex}")
            return None

    def close(self):
        """Close the session and release resources."""
        if self.session:
            self.session.close()
