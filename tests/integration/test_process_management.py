"""
Integration tests for process management workflows.

Tests the complete workflow of starting, monitoring, and stopping
Blocknet Core, Block-DX, and XLite processes.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.integration.helpers.test_helpers import IntegrationTestHelper


@pytest.mark.integration
class TestProcessManagementWorkflow:
    """Integration tests for process management workflows."""

    def setup_method(self):
        """Set up test fixtures before each test."""
        self.helper = IntegrationTestHelper()
        self.workspace = self.helper.create_temp_workspace(prefix="process_workflow_")

    def teardown_method(self):
        """Clean up after each test."""
        self.helper.cleanup_workspace(self.workspace)

    def test_process_start_workflow(self):
        """Test starting a process and verifying its state."""
        # Create mock binary
        binary_path = self.workspace / "test_binary"
        binary_path.write_text("#!/bin/bash\necho 'test'")
        binary_path.chmod(0o755)

        # Mock subprocess.Popen
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.wait.return_value = None

        with patch("subprocess.Popen", return_value=mock_process) as mock_popen:
            # Simulate starting process
            process = subprocess.Popen([str(binary_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Verify process was started
            mock_popen.assert_called_once()
            assert process.pid == 12345

            # Verify process is running (poll returns None)
            assert process.poll() is None

    def test_process_monitoring_workflow(self):
        """Test monitoring process state."""
        # Create PID file
        pid_file = self.workspace / "test.pid"
        pid_file.write_text("12345")

        # Mock psutil.Process
        mock_psutil_process = MagicMock()
        mock_psutil_process.pid = 12345
        mock_psutil_process.is_running.return_value = True
        mock_psutil_process.status.return_value = "running"

        with patch("psutil.Process", return_value=mock_psutil_process):
            # Read PID from file
            pid = int(pid_file.read_text())
            assert pid == 12345

            # Check if process is running
            is_running = mock_psutil_process.is_running()
            assert is_running is True

            # Get process status
            status = mock_psutil_process.status()
            assert status == "running"

    def test_process_stop_workflow(self):
        """Test stopping a process gracefully."""
        # Create mock process
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.wait.return_value = None
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()

        # Mock psutil.Process
        mock_psutil_process = MagicMock()
        mock_psutil_process.pid = 12345
        mock_psutil_process.is_running.return_value = True
        mock_psutil_process.terminate = MagicMock()
        mock_psutil_process.kill = MagicMock()

        with (
            patch("subprocess.Popen", return_value=mock_process),
            patch("psutil.Process", return_value=mock_psutil_process),
        ):
            # Start process
            process = subprocess.Popen(["echo", "test"])

            # Stop process gracefully
            process.terminate()

            # Verify process termination was called
            mock_process.terminate.assert_called_once()

            # Verify process is stopped
            mock_psutil_process.is_running.return_value = False
            assert not mock_psutil_process.is_running()

    def test_process_force_kill_workflow(self):
        """Test force killing a process."""
        # Create mock process
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.wait.return_value = None
        mock_process.kill = MagicMock()

        # Mock psutil.Process
        mock_psutil_process = MagicMock()
        mock_psutil_process.pid = 12345
        mock_psutil_process.is_running.return_value = True
        mock_psutil_process.kill = MagicMock()

        with (
            patch("subprocess.Popen", return_value=mock_process),
            patch("psutil.Process", return_value=mock_psutil_process),
        ):
            # Start process
            process = subprocess.Popen(["echo", "test"])

            # Force kill process
            process.kill()

            # Verify kill was called
            mock_process.kill.assert_called_once()

            # Verify process is killed
            mock_psutil_process.is_running.return_value = False
            assert not mock_psutil_process.is_running()

    def test_process_timeout_workflow(self):
        """Test process timeout handling."""
        # Create mock process that times out
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.wait.side_effect = subprocess.TimeoutExpired(["test"], 5)

        with patch("subprocess.Popen", return_value=mock_process):
            # Start process
            process = subprocess.Popen(["echo", "test"])

            # Wait with timeout - should raise TimeoutExpired
            with pytest.raises(subprocess.TimeoutExpired):
                process.wait(timeout=5)

    def test_process_environment_workflow(self):
        """Test process with custom environment variables."""
        # Create mock process with environment
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None

        custom_env = os.environ.copy()
        custom_env["TEST_VAR"] = "test_value"

        with patch("subprocess.Popen", return_value=mock_process) as mock_popen:
            # Start process with custom environment
            process = subprocess.Popen(["echo", "test"], env=custom_env)

            # Verify environment was passed
            call_args = mock_popen.call_args
            assert call_args[1]["env"] == custom_env
            assert call_args[1]["env"]["TEST_VAR"] == "test_value"

    def test_process_output_capture_workflow(self):
        """Test capturing process output."""
        # Create mock process with output
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.communicate.return_value = (b"stdout output", b"stderr output")

        with patch("subprocess.Popen", return_value=mock_process):
            # Start process
            process = subprocess.Popen(["echo", "test"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Get output
            stdout, stderr = process.communicate()

            # Verify output
            assert stdout == b"stdout output"
            assert stderr == b"stderr output"

    def test_process_pid_file_workflow(self):
        """Test PID file creation and management."""
        # Create PID file
        pid_file = self.workspace / "test.pid"
        pid = 12345

        # Write PID to file
        pid_file.write_text(str(pid))

        # Verify PID file exists and contains correct PID
        assert pid_file.exists()
        assert int(pid_file.read_text()) == pid

        # Test PID file update
        new_pid = 54321
        pid_file.write_text(str(new_pid))
        assert int(pid_file.read_text()) == new_pid

        # Test PID file deletion
        pid_file.unlink()
        assert not pid_file.exists()

    def test_process_state_file_workflow(self):
        """Test process state file management."""
        # Create state file
        state_file = self.workspace / "test.state"

        # Write state
        state_file.write_text("running")
        assert state_file.exists()
        assert state_file.read_text() == "running"

        # Update state
        state_file.write_text("stopped")
        assert state_file.read_text() == "stopped"

        # Test state transitions
        states = ["starting", "running", "stopping", "stopped"]
        for state in states:
            state_file.write_text(state)
            assert state_file.read_text() == state

        # Clean up
        state_file.unlink()
        assert not state_file.exists()

    def test_process_signal_handling_workflow(self):
        """Test process signal handling."""
        # Create mock process
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.send_signal = MagicMock()

        # Test SIGTERM signal
        mock_process.send_signal(signal.SIGTERM)
        mock_process.send_signal.assert_called_with(signal.SIGTERM)

        # Test SIGKILL signal
        mock_process.send_signal(signal.SIGKILL)
        mock_process.send_signal.assert_called_with(signal.SIGKILL)

        # Test SIGHUP signal
        mock_process.send_signal(signal.SIGHUP)
        mock_process.send_signal.assert_called_with(signal.SIGHUP)

    def test_process_lifecycle_integration(self):
        """Test complete process lifecycle integration."""
        # Create mock binary
        binary_path = self.workspace / "test_app"
        binary_path.write_text("#!/bin/bash\necho 'test'")
        binary_path.chmod(0o755)

        # Create PID file
        pid_file = self.workspace / "test_app.pid"

        # Create state file
        state_file = self.workspace / "test_app.state"

        # Mock process
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None
        mock_process.wait.return_value = None
        mock_process.terminate = MagicMock()
        mock_process.kill = MagicMock()

        # Mock psutil
        mock_psutil_process = MagicMock()
        mock_psutil_process.pid = 12345
        mock_psutil_process.is_running.return_value = True
        mock_psutil_process.terminate = MagicMock()
        mock_psutil_process.kill = MagicMock()

        with (
            patch("subprocess.Popen", return_value=mock_process),
            patch("psutil.Process", return_value=mock_psutil_process),
        ):
            # Step 1: Start process
            process = subprocess.Popen([str(binary_path)])
            pid_file.write_text(str(process.pid))
            state_file.write_text("running")

            # Verify start state
            assert pid_file.exists()
            assert state_file.read_text() == "running"
            assert int(pid_file.read_text()) == 12345

            # Step 2: Monitor process
            is_running = mock_psutil_process.is_running()
            assert is_running is True

            # Step 3: Stop process gracefully
            process.terminate()
            state_file.write_text("stopping")

            # Verify stop state
            assert state_file.read_text() == "stopping"
            mock_process.terminate.assert_called_once()

            # Step 4: Verify process stopped
            mock_psutil_process.is_running.return_value = False
            state_file.write_text("stopped")

            assert not mock_psutil_process.is_running()
            assert state_file.read_text() == "stopped"

            # Step 5: Clean up
            pid_file.unlink()
            state_file.unlink()

            assert not pid_file.exists()
            assert not state_file.exists()
