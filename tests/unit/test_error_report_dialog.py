import os
import platform
from unittest.mock import MagicMock, patch, mock_open, call

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from gui.error_report_dialog import build_report, show_error_report, ErrorReportDialog


def test_build_report_contains_fields():
    report = build_report(
        app_name="Block-DX",
        returncode=127,
        command=["/tmp/block-dx", "--test"],
        cwd="/tmp",
        stderr_text="error: libXss missing",
        executable_path="/tmp/block-dx",
        extra_info="extra detail",
    )
    assert "App: Block-DX" in report
    assert "Return code: 127" in report
    assert "Command: /tmp/block-dx --test" in report
    assert "CWD: /tmp" in report
    assert "Executable: /tmp/block-dx" in report
    assert "error: libXss missing" in report
    assert "extra detail" in report
    assert "System:" in report
    assert platform.system() in report
    assert "https://github.com/tryiou/blocknet_aio_monitor/issues/new" in report


def test_build_report_truncates_long_stderr():
    long_stderr = "\n".join([f"line {i}" for i in range(100)])
    report = build_report("XLite", 1, ["xlite"], "/tmp", long_stderr)
    assert "(truncated" in report
    assert "line 99" in report
    # should show last 80 lines, not first
    assert "line 0" not in report
    assert "line 20" in report  # 100-80=20


def test_build_report_no_stderr():
    report = build_report("Blocknet Core", 1, None, None, "")
    assert "(no stderr captured" in report
    assert "Command: unknown" in report


def test_show_error_report_schedules_dialog():
    mock_parent = MagicMock()
    mock_parent.after = MagicMock(side_effect=lambda delay, func: func())
    with patch("gui.error_report_dialog.ErrorReportDialog") as mock_dialog:
        show_error_report(
            mock_parent,
            app_name="Block-DX",
            returncode=127,
            command=["block-dx"],
            cwd="/tmp",
            stderr_text="some error",
        )
        mock_parent.after.assert_called_once()
        mock_dialog.assert_called_once()
        kwargs = mock_dialog.call_args[1]
        assert kwargs["app_name"] == "Block-DX"
        assert "127" in kwargs["title"]
        assert "some error" in kwargs["report_text"]


def test_base_binutil_get_stderr_snippet(tmp_path):
    from utilities.bin_handlers.base_binutil import BaseBinUtil
    from unittest.mock import MagicMock

    mock_container = MagicMock()
    mock_container.aio_folder = str(tmp_path)
    mock_container.system = "Linux"
    util = BaseBinUtil("TestApp", container=mock_container)
    # simulate Popen creating log file
    log_path = tmp_path / "testapp_launch.log"
    log_path.write_text("stderr line1\nstderr line2\n")
    util._stderr_log_path = str(log_path)
    util._stderr_file_handle = None
    snippet = util.get_stderr_snippet()
    assert "stderr line1" in snippet
    assert "stderr line2" in snippet


def test_base_binutil_get_launch_context(tmp_path):
    from utilities.bin_handlers.base_binutil import BaseBinUtil

    mock_container = MagicMock()
    mock_container.aio_folder = str(tmp_path)
    mock_container.system = "Linux"
    util = BaseBinUtil("TestApp", container=mock_container)
    util.executable_path = "/tmp/fake"
    util._last_command = ["fake", "--arg"]
    util._last_cwd = "/tmp"
    util._stderr_log_path = str(tmp_path / "nonexistent.log")
    ctx = util.get_launch_context()
    assert ctx["command"] == ["fake", "--arg"]
    assert ctx["cwd"] == "/tmp"
    assert ctx["executable"] == "/tmp/fake"
    assert ctx["app_name"] == "TestApp"


def test_binary_manager_check_launch_failure_shows_dialog():
    from gui.binary_manager import BinaryManager

    mock_root = MagicMock()
    mock_root.after = MagicMock()
    mock_container = MagicMock()
    mock_container.aio_folder = "/tmp"
    mock_container.system = "Linux"
    mock_container.blockdx_release_url = "http://example.com/blockdx"
    mock_container.xlite_release_url = "http://example.com/xlite"
    mock_container.blocknet_release_url = "http://example.com/blocknet"
    mock_container.blockdx_curpath = "BLOCK-DX"
    mock_container.xlite_curpath = "XLite"
    mock_container.conf_data.blocknet_bin_path = ["blocknet"]

    with patch("gui.binary_manager.get_container", return_value=mock_container), \
         patch("gui.binary_manager.Observer"), \
         patch("gui.binary_manager.BinaryFileHandler"):
        mgr = BinaryManager(mock_root)
        mgr.frame_manager = MagicMock()
        mgr.root_gui = mock_root

        handler = MagicMock()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 127
        handler.process = mock_proc
        handler.get_launch_context.return_value = {
            "command": ["block-dx"],
            "cwd": "/tmp",
            "stderr": "missing lib",
            "executable": "/tmp/block-dx",
        }

        with patch("gui.error_report_dialog.show_error_report") as mock_show:
            mgr._check_launch_failure("Block-DX", handler)
            mock_show.assert_called_once()
            kwargs = mock_show.call_args[1]
            assert kwargs["returncode"] == 127
            assert kwargs["app_name"] == "Block-DX"
            assert "missing lib" in kwargs["stderr_text"]


def test_binary_manager_check_launch_failure_no_dialog_when_running():
    from gui.binary_manager import BinaryManager

    mock_root = MagicMock()
    mock_container = MagicMock()
    mock_container.aio_folder = "/tmp"
    mock_container.system = "Linux"
    mock_container.blockdx_release_url = "http://example.com/blockdx"
    mock_container.xlite_release_url = "http://example.com/xlite"
    mock_container.blocknet_release_url = "http://example.com/blocknet"
    mock_container.blockdx_curpath = "BLOCK-DX"
    mock_container.xlite_curpath = "XLite"
    mock_container.conf_data.blocknet_bin_path = ["blocknet"]

    with patch("gui.binary_manager.get_container", return_value=mock_container), \
         patch("gui.binary_manager.Observer"), \
         patch("gui.binary_manager.BinaryFileHandler"):
        mgr = BinaryManager(mock_root)
        mgr.root_gui = mock_root
        handler = MagicMock()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # still running
        handler.process = mock_proc

        with patch("gui.error_report_dialog.show_error_report") as mock_show:
            mgr._check_launch_failure("Block-DX", handler)
            mock_show.assert_not_called()


def test_binary_manager_check_launch_failure_zero_exit_no_dialog():
    from gui.binary_manager import BinaryManager

    mock_root = MagicMock()
    mock_container = MagicMock()
    mock_container.aio_folder = "/tmp"
    mock_container.system = "Linux"
    mock_container.blockdx_release_url = "http://example.com/blockdx"
    mock_container.xlite_release_url = "http://example.com/xlite"
    mock_container.blocknet_release_url = "http://example.com/blocknet"
    mock_container.blockdx_curpath = "BLOCK-DX"
    mock_container.xlite_curpath = "XLite"
    mock_container.conf_data.blocknet_bin_path = ["blocknet"]

    with patch("gui.binary_manager.get_container", return_value=mock_container), \
         patch("gui.binary_manager.Observer"), \
         patch("gui.binary_manager.BinaryFileHandler"):
        mgr = BinaryManager(mock_root)
        mgr.root_gui = mock_root
        handler = MagicMock()
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        handler.process = mock_proc
        handler.get_launch_context.return_value = {"command": [], "cwd": "", "stderr": "", "executable": ""}

        with patch("gui.error_report_dialog.show_error_report") as mock_show:
            mgr._check_launch_failure("XLite", handler)
            mock_show.assert_not_called()
