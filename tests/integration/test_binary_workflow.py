"""
Integration tests for binary download and installation workflows.

Tests the complete workflow from downloading binaries to installation,
including file system operations, extraction, and configuration.
"""

import os
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gui.binary_manager import BinaryManager
from tests.integration.helpers.test_helpers import IntegrationTestHelper, WorkflowSimulator
from utilities.bin_handlers.base_binutil import BaseBinUtil


@pytest.mark.integration
@pytest.mark.filesystem
class TestBinaryDownloadWorkflow:
    """Integration tests for binary download and installation workflows."""

    def setup_method(self):
        """Set up test fixtures before each test."""
        self.helper = IntegrationTestHelper()
        self.workspace = self.helper.create_temp_workspace(prefix="binary_workflow_")
        self.simulator = WorkflowSimulator(self.workspace)

    def teardown_method(self):
        """Clean up after each test."""
        self.helper.cleanup_workspace(self.workspace)

    @pytest.mark.network
    def test_blocknet_download_and_install_workflow(self):
        """Test complete Blocknet download and installation workflow."""
        # Setup
        aio_folder = self.workspace / "AIO_Blocknet"
        aio_folder.mkdir(parents=True, exist_ok=True)

        # Mock AppContainer
        patches = self.helper.patch_app_container(
            self.workspace, aio_folder=str(aio_folder), system="Linux", machine="x86_64"
        )

        try:
            # Simulate the workflow
            workflow_result = self.simulator.simulate_blocknet_install_workflow()

            # Verify workflow steps
            assert self.helper.verify_directory_exists(workflow_result["download_dir"], "Download directory")
            assert self.helper.verify_file_exists(workflow_result["archive"], "Archive file")
            assert self.helper.verify_directory_exists(workflow_result["binary"].parent, "Extract directory")
            assert self.helper.verify_file_exists(workflow_result["binary"], "Binary file")
            assert self.helper.verify_executable(workflow_result["binary"], "Blocknet binary")
            assert self.helper.verify_directory_exists(workflow_result["config_dir"], "Config directory")
            assert self.helper.verify_file_exists(workflow_result["config"], "Config file")

            # Verify binary content
            binary_content = workflow_result["binary"].read_text()
            assert "Blocknet Qt" in binary_content

            # Verify config content
            config_content = workflow_result["config"].read_text()
            assert "rpcuser=testuser" in config_content
            assert "addnode=node1.example.com:41412" in config_content

        finally:
            self.helper.cleanup_patches(patches)

    @pytest.mark.network
    def test_blockdx_download_and_install_workflow(self):
        """Test complete Block-DX download and installation workflow."""
        # Setup
        aio_folder = self.workspace / "AIO_Blocknet"
        aio_folder.mkdir(parents=True, exist_ok=True)

        # Mock AppContainer
        patches = self.helper.patch_app_container(
            self.workspace, aio_folder=str(aio_folder), system="Linux", machine="x86_64"
        )

        try:
            # Simulate the workflow
            workflow_result = self.simulator.simulate_blockdx_install_workflow()

            # Verify workflow steps
            assert self.helper.verify_directory_exists(workflow_result["download_dir"], "Download directory")
            assert self.helper.verify_file_exists(workflow_result["archive"], "Archive file")
            assert self.helper.verify_directory_exists(workflow_result["binary"].parent, "Extract directory")
            assert self.helper.verify_file_exists(workflow_result["binary"], "Binary file")
            assert self.helper.verify_executable(workflow_result["binary"], "Block-DX binary")
            assert self.helper.verify_directory_exists(workflow_result["config_dir"], "Config directory")
            assert self.helper.verify_file_exists(workflow_result["config"], "Config file")

            # Verify binary content
            binary_content = workflow_result["binary"].read_text()
            assert "Block-DX" in binary_content

            # Verify config content
            config_content = workflow_result["config"].read_text()
            assert "rpcuser=testuser" in config_content
            assert "selectedWallets_blocknet=BLOCK" in config_content

        finally:
            self.helper.cleanup_patches(patches)

    @pytest.mark.network
    def test_xlite_download_and_install_workflow(self):
        """Test complete XLite download and installation workflow."""
        # Setup
        aio_folder = self.workspace / "AIO_Blocknet"
        aio_folder.mkdir(parents=True, exist_ok=True)

        # Mock AppContainer
        patches = self.helper.patch_app_container(
            self.workspace, aio_folder=str(aio_folder), system="Linux", machine="x86_64"
        )

        try:
            # Simulate the workflow
            workflow_result = self.simulator.simulate_xlite_install_workflow()

            # Verify workflow steps
            assert self.helper.verify_directory_exists(workflow_result["download_dir"], "Download directory")
            assert self.helper.verify_file_exists(workflow_result["archive"], "Archive file")
            assert self.helper.verify_directory_exists(workflow_result["binary"].parent, "Extract directory")
            assert self.helper.verify_file_exists(workflow_result["binary"], "Binary file")
            assert self.helper.verify_executable(workflow_result["binary"], "XLite binary")
            assert self.helper.verify_directory_exists(workflow_result["config_dir"], "Config directory")
            assert self.helper.verify_file_exists(workflow_result["config"], "Config file")

            # Verify binary content
            binary_content = workflow_result["binary"].read_text()
            assert "XLite" in binary_content

            # Verify config content
            config_content = workflow_result["config"].read_text()
            assert "rpcuser=testuser" in config_content

        finally:
            self.helper.cleanup_patches(patches)

    def test_archive_extraction_zip(self):
        """Test ZIP archive extraction workflow."""
        # Create a mock ZIP file
        zip_path = self.workspace / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test/file1.txt", "content1")
            zf.writestr("test/file2.txt", "content2")

        # Extract to target directory
        extract_dir = self.workspace / "extracted"
        extract_dir.mkdir()

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)  # noqa: S202 # test fixture

        # Verify extraction
        assert (extract_dir / "test" / "file1.txt").exists()
        assert (extract_dir / "test" / "file2.txt").exists()
        assert (extract_dir / "test" / "file1.txt").read_text() == "content1"

    def test_archive_extraction_tar_gz(self):
        """Test TAR.GZ archive extraction workflow."""
        # Create a mock TAR.GZ file
        tar_path = self.workspace / "test.tar.gz"
        with tarfile.open(tar_path, "w:gz") as tf:
            # Create temporary files to add
            temp_file = self.workspace / "temp_file.txt"
            temp_file.write_text("test content")

            tf.add(temp_file, arcname="test/file1.txt")
            temp_file.unlink()

        # Extract to target directory
        extract_dir = self.workspace / "extracted"
        extract_dir.mkdir()

        with tarfile.open(tar_path, "r:gz") as tf:
            tf.extractall(extract_dir, filter="data")

        # Verify extraction
        assert (extract_dir / "test" / "file1.txt").exists()
        assert (extract_dir / "test" / "file1.txt").read_text() == "test content"

    def test_file_system_operations_integration(self):
        """Test file system operations integration."""
        # Create directory structure
        base_dir = self.workspace / "test_structure"
        base_dir.mkdir()

        # Create nested directories
        (base_dir / "level1" / "level2").mkdir(parents=True)

        # Create files
        (base_dir / "file1.txt").write_text("content1")
        (base_dir / "level1" / "file2.txt").write_text("content2")
        (base_dir / "level1" / "level2" / "file3.txt").write_text("content3")

        # Verify structure
        assert (base_dir / "file1.txt").exists()
        assert (base_dir / "level1" / "file2.txt").exists()
        assert (base_dir / "level1" / "level2" / "file3.txt").exists()

        # Test file permissions
        exec_file = base_dir / "executable.sh"
        exec_file.write_text("#!/bin/bash\necho 'test'")
        exec_file.chmod(0o755)

        assert os.access(exec_file, os.X_OK)

        # Test file deletion
        (base_dir / "file1.txt").unlink()
        assert not (base_dir / "file1.txt").exists()

    def test_version_validation_workflow(self):
        """Test version validation in workflow."""
        # Create version file
        version_file = self.workspace / "version.txt"
        version_file.write_text("1.0.0")

        # Read and validate version
        version = version_file.read_text().strip()
        assert version == "1.0.0"

        # Test version comparison
        from packaging import version as pkg_version

        assert pkg_version.parse(version) >= pkg_version.parse("1.0.0")

    def test_error_handling_in_workflow(self):
        """Test error handling in workflow operations."""
        # Test non-existent file
        non_existent = self.workspace / "nonexistent.txt"
        assert not non_existent.exists()

        # Test extraction with corrupted archive
        corrupted_zip = self.workspace / "corrupted.zip"
        corrupted_zip.write_bytes(b"not a valid zip file")

        with pytest.raises(zipfile.BadZipFile), zipfile.ZipFile(corrupted_zip, "r") as zf:
            zf.extractall(self.workspace)  # noqa: S202 # test corrupted

        # Test permission denied (POSIX only - Windows chmod is no-op)
        if sys.platform == "win32":
            pytest.skip("chmod read-only not enforced on Windows")
        restricted_dir = self.workspace / "restricted"
        restricted_dir.mkdir()
        restricted_file = restricted_dir / "test.txt"
        restricted_file.write_text("test")

        # Make directory read-only (simulating permission issues)
        restricted_dir.chmod(0o444)

        try:
            # Try to create file in read-only directory
            with pytest.raises((PermissionError, OSError)):
                new_file = restricted_dir / "new.txt"
                new_file.write_text("new content")
        finally:
            # Restore permissions for cleanup
            restricted_dir.chmod(0o755)
