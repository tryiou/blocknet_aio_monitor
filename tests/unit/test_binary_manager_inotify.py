import errno
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import gui.binary_manager as bm_module
from gui.binary_manager import BinaryManager


def _make_mock_root():
    mock_root = MagicMock()
    mock_root.after = MagicMock()
    mock_root.tooltip_manager = MagicMock()
    mock_root.winfo_exists = MagicMock(return_value=True)
    for mgr in ["blocknet_manager", "blockdx_manager", "xlite_manager"]:
        m = MagicMock()
        m.utility = MagicMock()
        m.version = ["v1.0.0"]
        m.blocknet_process_running = False
        m.process_running = False
        setattr(mock_root, mgr, m)
    return mock_root


def _make_mock_container(tmp_path="/tmp"):
    mock_container = MagicMock()
    mock_container.aio_folder = tmp_path
    mock_container.system = "Linux"
    mock_container.blockdx_release_url = "http://example.com/blockdx"
    mock_container.xlite_release_url = "http://example.com/xlite"
    mock_container.blocknet_release_url = "http://example.com/blocknet"
    mock_container.blockdx_curpath = "BLOCK-DX"
    mock_container.xlite_curpath = "XLite"
    mock_container.conf_data.blocknet_bin_path = ["blocknet"]
    return mock_container


def test_inotify_enospc_fallback_to_polling():
    """When inotify hits ENOSPC, should fall back to PollingObserver (2.0s)."""
    mock_root = _make_mock_root()
    mock_container = _make_mock_container()
    with (
        patch("gui.binary_manager.get_container", return_value=mock_container),
        patch(
            "gui.binary_manager.Observer", side_effect=OSError(errno.ENOSPC, "inotify watch limit reached")
        ) as mock_obs,
        patch("gui.binary_manager.PollingObserver") as mock_poll,
        patch("gui.binary_manager.BinaryFileHandler"),
        patch("gui.error_report_dialog.show_error_report"),
    ):
        mock_poll_instance = MagicMock()
        mock_poll.return_value = mock_poll_instance
        mgr = BinaryManager(mock_root)
        assert mgr.observer is mock_poll_instance
        assert mgr._inotify_fallback_active is True
        mock_poll.assert_called_once_with(timeout=2.0)
        mock_poll_instance.schedule.assert_called_once()
        mock_poll_instance.start.assert_called_once()
        # Should not have scheduled periodic poll as observer exists (polling)
        # Check that after was called for process_file_changes but not for _poll_aio_folder as observer exists
        # The fallback hint should have been scheduled via after(1500, ...)
        assert any(call.args[0] == 1500 for call in mock_root.after.call_args_list)


def test_inotify_both_observers_fail_fallback_to_periodic_poll():
    """When both observers fail with ENOSPC, should fall back to periodic mtime poll (2000ms)."""
    mock_root = _make_mock_root()
    mock_container = _make_mock_container()
    with (
        patch("gui.binary_manager.get_container", return_value=mock_container),
        patch("gui.binary_manager.Observer", side_effect=OSError(errno.ENOSPC, "limit")),
        patch("gui.binary_manager.PollingObserver", side_effect=OSError(errno.ENOSPC, "limit")),
        patch("gui.binary_manager.BinaryFileHandler"),
        patch("gui.error_report_dialog.show_error_report"),
    ):
        mgr = BinaryManager(mock_root)
        assert mgr.observer is None
        assert mgr._inotify_fallback_active is True
        # Should have scheduled periodic poll (2000ms)
        assert any(call.args[0] == 2000 for call in mock_root.after.call_args_list)


def test_inotify_success_no_fallback():
    """Normal case: inotify succeeds, no fallback, no periodic poll extra."""
    mock_root = _make_mock_root()
    mock_container = _make_mock_container()
    with (
        patch("gui.binary_manager.get_container", return_value=mock_container),
        patch("gui.binary_manager.Observer") as mock_obs,
        patch("gui.binary_manager.BinaryFileHandler"),
    ):
        mock_instance = MagicMock()
        mock_obs.return_value = mock_instance
        mgr = BinaryManager(mock_root)
        assert mgr.observer is mock_instance
        assert mgr._inotify_fallback_active is False
        mock_instance.schedule.assert_called_once()
        mock_instance.start.assert_called_once()


def test_stop_cleans_observer():
    mock_root = _make_mock_root()
    mock_container = _make_mock_container()
    with (
        patch("gui.binary_manager.get_container", return_value=mock_container),
        patch("gui.binary_manager.Observer") as mock_obs,
        patch("gui.binary_manager.BinaryFileHandler"),
    ):
        mock_instance = MagicMock()
        mock_obs.return_value = mock_instance
        mgr = BinaryManager(mock_root)
        mgr.stop()
        mock_instance.stop.assert_called_once()
        mock_instance.join.assert_called_once_with(0.5)
        assert mgr.observer is None


def test_poll_aio_folder_no_window():
    """Periodic poll should not open window and should call check_and_update."""
    mock_root = _make_mock_root()
    mock_container = _make_mock_container()
    with (
        patch("gui.binary_manager.get_container", return_value=mock_container),
        patch("gui.binary_manager.Observer") as mock_obs,
        patch("gui.binary_manager.BinaryFileHandler"),
    ):
        mock_instance = MagicMock()
        mock_obs.return_value = mock_instance
        mgr = BinaryManager(mock_root)
        # Mock check_and_update to avoid file system
        mgr.check_and_update_aio_folder = MagicMock()
        # Call poll
        mgr._poll_aio_folder()
        mgr.check_and_update_aio_folder.assert_called_once()
        # Should reschedule
        assert any(call.args[0] == 2000 for call in mock_root.after.call_args_list)
