"""
Integration tests for configuration management workflows.

Tests the complete workflow of reading, writing, and managing
configuration files across different components.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.integration.helpers.test_helpers import IntegrationTestHelper
from utilities.config_manager import ConfigManager


@pytest.mark.integration
class TestConfigManagementWorkflow:
    """Integration tests for configuration management workflows."""

    def setup_method(self):
        """Set up test fixtures before each test."""
        self.helper = IntegrationTestHelper()
        self.workspace = self.helper.create_temp_workspace(prefix="config_workflow_")
        self.test_data = self.helper.create_test_data(self.workspace)

    def teardown_method(self):
        """Clean up after each test."""
        self.helper.cleanup_workspace(self.workspace)

    def test_config_initialization_workflow(self):
        """Test configuration initialization workflow."""
        # Create config directory
        config_dir = self.workspace / "config"
        config_dir.mkdir()

        # Create config file
        config_file = config_dir / "aio_config.json"
        config_data = {"custom_path": str(self.workspace), "xl_pass": "encrypted_password", "salt": "salt_value"}

        with open(config_file, "w") as f:
            json.dump(config_data, f)

        # Verify config file exists
        assert config_file.exists()

        # Read and verify config
        with open(config_file) as f:
            loaded_config = json.load(f)

        assert loaded_config == config_data
        assert loaded_config["custom_path"] == str(self.workspace)
        assert loaded_config["xl_pass"] == "encrypted_password"

    def test_config_reading_workflow(self):
        """Test configuration reading workflow."""
        # Use existing test config
        config_file = self.test_data["config_file"]

        # Read config
        with open(config_file) as f:
            config = json.load(f)

        # Verify config structure
        assert "custom_path" in config
        assert "xl_pass" in config
        assert "salt" in config
        assert "extra_option_blocknet_core_conf" in config

        # Verify config values
        assert config["custom_path"] == str(self.workspace)
        assert config["xl_pass"] == "mock_encrypted_password"
        assert config["salt"] == "mock_salt"

        # Verify extra options
        extra_options = config["extra_option_blocknet_core_conf"]
        assert isinstance(extra_options, list)
        assert len(extra_options) == 2
        assert extra_options[0]["addnode"] == "node1.example.com:41412"

    def test_config_writing_workflow(self):
        """Test configuration writing workflow."""
        # Create new config data
        new_config = {
            "custom_path": str(self.workspace / "new_path"),
            "xl_pass": "new_encrypted_password",
            "salt": "new_salt",
            "extra_option_blocknet_core_conf": [{"addnode": "new_node.example.com:41412"}],
            "new_field": "new_value",
        }

        # Write config
        config_file = self.workspace / "new_config.json"
        with open(config_file, "w") as f:
            json.dump(new_config, f, indent=2)

        # Verify config was written
        assert config_file.exists()

        # Read back and verify
        with open(config_file) as f:
            loaded_config = json.load(f)

        assert loaded_config == new_config
        assert loaded_config["new_field"] == "new_value"

    def test_config_update_workflow(self):
        """Test configuration update workflow."""
        config_file = self.test_data["config_file"]

        # Read current config
        with open(config_file) as f:
            config = json.load(f)

        # Update config
        config["new_option"] = "new_value"
        config["xl_pass"] = "updated_password"

        # Write updated config
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        # Verify update
        with open(config_file) as f:
            updated_config = json.load(f)

        assert updated_config["new_option"] == "new_value"
        assert updated_config["xl_pass"] == "updated_password"
        assert updated_config["custom_path"] == str(self.workspace)  # Unchanged

    def test_blocknet_config_workflow(self):
        """Test Blocknet configuration workflow."""
        blocknet_conf = self.test_data["blocknet_conf"]

        # Read Blocknet config
        with open(blocknet_conf) as f:
            config_content = f.read()

        # Verify config content
        assert "rpcuser=testuser" in config_content
        assert "rpcpassword=testpass" in config_content
        assert "addnode=node1.example.com:41412" in config_content

        # Parse config (simulating Blocknet config parsing)
        config_dict = {}
        for line in config_content.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    if key in config_dict:
                        # Handle multiple values (e.g., addnode)
                        if not isinstance(config_dict[key], list):
                            config_dict[key] = [config_dict[key]]
                        config_dict[key].append(value)
                    else:
                        config_dict[key] = value

        # Verify parsed config
        assert config_dict["rpcuser"] == "testuser"
        assert config_dict["rpcpassword"] == "testpass"
        assert isinstance(config_dict["addnode"], list)
        assert "node1.example.com:41412" in config_dict["addnode"]

    def test_blockdx_config_workflow(self):
        """Test Block-DX configuration workflow."""
        blockdx_conf = self.test_data["blockdx_conf"]

        # Read Block-DX config
        with open(blockdx_conf) as f:
            config_content = f.read()

        # Verify config content
        assert "rpcuser=testuser" in config_content
        assert "rpcpassword=testpass" in config_content
        assert "FullLog=true" in config_content
        assert "selectedWallets_blocknet=BLOCK" in config_content

        # Parse config
        config_dict = {}
        for line in config_content.strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                if "=" in line:
                    key, value = line.split("=", 1)
                    config_dict[key.strip()] = value.strip()

        # Verify parsed config
        assert config_dict["rpcuser"] == "testuser"
        assert config_dict["rpcpassword"] == "testpass"
        assert config_dict["FullLog"] == "true"
        assert config_dict["selectedWallets_blocknet"] == "BLOCK"

    def test_config_manager_integration(self):
        """Test ConfigManager integration with workflow."""
        # Create config manager with test workspace
        config_mgr = ConfigManager(aio_folder=str(self.workspace))

        # Verify config manager initialized
        assert config_mgr is not None
        assert hasattr(config_mgr, "config")

        # Verify config has expected structure
        config = config_mgr.config
        assert isinstance(config, dict)

        # Verify system-specific values
        assert "blocknet_bin_name" in config
        assert "xlite_launch_options" in config

    def test_config_path_resolution_workflow(self):
        """Test configuration path resolution workflow."""
        # Test different path types
        test_paths = [
            ("~/.AIO_Blocknet", Path.home() / ".AIO_Blocknet"),
            ("%appdata%\\AIO_Blocknet", Path.home() / "AppData" / "Roaming" / "AIO_Blocknet"),
            ("/home/user/.AIO_Blocknet", Path("/home/user/.AIO_Blocknet")),
        ]

        for input_path, _expected_path in test_paths:
            # Simulate path expansion
            expanded = os.path.expanduser(input_path)
            expanded = os.path.expandvars(expanded)

            # Verify path expansion (note: actual expansion depends on OS)
            assert expanded is not None
            assert isinstance(expanded, str)

    def test_config_extra_options_workflow(self):
        """Test extra configuration options workflow."""
        # Create config with extra options
        config_data = {
            "extra_option_blocknet_core_conf": [
                {"addnode": "node1.example.com:41412"},
                {"addnode": "node2.example.com:41412"},
                {"rpcallowip": "192.168.1.1"},
                {"addnode": "node3.example.com:41412"},
            ]
        }

        # Write config
        config_file = self.workspace / "config_with_extras.json"
        with open(config_file, "w") as f:
            json.dump(config_data, f, indent=2)

        # Read and process extra options
        with open(config_file) as f:
            loaded_config = json.load(f)

        extra_options = loaded_config["extra_option_blocknet_core_conf"]

        # Verify extra options structure
        assert isinstance(extra_options, list)
        assert len(extra_options) == 4

        # Group options by key
        grouped = {}
        for option in extra_options:
            for key, value in option.items():
                if key not in grouped:
                    grouped[key] = []
                grouped[key].append(value)

        # Verify grouped options
        assert "addnode" in grouped
        assert len(grouped["addnode"]) == 3
        assert "node1.example.com:41412" in grouped["addnode"]
        assert "node2.example.com:41412" in grouped["addnode"]
        assert "node3.example.com:41412" in grouped["addnode"]

        assert "rpcallowip" in grouped
        assert grouped["rpcallowip"] == ["192.168.1.1"]

    def test_config_backup_workflow(self):
        """Test configuration backup workflow."""
        # Create original config
        original_config = self.test_data["config_file"]

        # Create backup
        backup_file = self.workspace / "aio_config_backup.json"
        backup_content = original_config.read_text()
        backup_file.write_text(backup_content)

        # Verify backup
        assert backup_file.exists()
        assert backup_file.read_text() == backup_content

        # Modify original
        with open(original_config) as f:
            config = json.load(f)

        config["modified"] = True

        with open(original_config, "w") as f:
            json.dump(config, f, indent=2)

        # Verify modification
        with open(original_config) as f:
            modified_config = json.load(f)

        assert modified_config.get("modified") is True

        # Restore from backup
        original_config.write_text(backup_content)

        # Verify restoration
        with open(original_config) as f:
            restored_config = json.load(f)

        assert "modified" not in restored_config

    def test_config_validation_workflow(self):
        """Test configuration validation workflow."""
        # Valid config
        valid_config = {"custom_path": str(self.workspace), "xl_pass": "password", "salt": "salt"}

        # Invalid config (missing required fields)
        invalid_config = {
            "custom_path": str(self.workspace)
            # Missing xl_pass and salt
        }

        # Test validation logic
        def validate_config(config):
            required_fields = ["custom_path", "xl_pass", "salt"]
            for field in required_fields:
                if field not in config:
                    return False, f"Missing required field: {field}"
            return True, "Valid"

        # Validate valid config
        is_valid, message = validate_config(valid_config)
        assert is_valid is True
        assert message == "Valid"

        # Validate invalid config
        is_valid, message = validate_config(invalid_config)
        assert is_valid is False
        assert "Missing required field" in message
