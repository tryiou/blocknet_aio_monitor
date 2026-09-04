"""Unit tests for utilities/logging_setup.py (rotating app log file)."""

import contextlib
import logging
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utilities.logging_setup import LOG_BACKUP_COUNT, LOG_FILENAME, LOG_MAX_BYTES, setup_file_logging


class TestLoggingSetup(unittest.TestCase):
    """Test suite for rotating file logging setup."""

    def setUp(self):
        """Isolated root logger per test (never touch the real root handlers)."""
        self.log = logging.getLogger(f"test_logging_setup_{id(self)}")
        self.log.setLevel(logging.DEBUG)
        self.log.propagate = False
        self.addCleanup(self._close_handlers)
        # conftest sets AIO_NO_FILE_LOG=1 for the session; these tests need
        # real file logging, so neutralize it (empty is falsy -> enabled).
        env_patch = patch.dict(os.environ, {"AIO_NO_FILE_LOG": ""})
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def _close_handlers(self):
        for handler in list(self.log.handlers):
            with contextlib.suppress(Exception):
                handler.close()
            with contextlib.suppress(Exception):
                self.log.removeHandler(handler)

    def _log_path(self, tmp_path):
        return os.path.join(str(tmp_path), LOG_FILENAME)

    def test_returns_none_for_missing_folder(self):
        """None/empty folder never raises, returns None."""
        self.assertIsNone(setup_file_logging(None, root_logger=self.log))
        self.assertIsNone(setup_file_logging("", root_logger=self.log))
        self.assertEqual(self.log.handlers, [])

    def test_returns_none_for_mocked_path(self):
        """MagicMock paths (test isolation guard) are skipped."""
        self.assertIsNone(setup_file_logging(MagicMock(), root_logger=self.log))
        self.assertEqual(self.log.handlers, [])

    def test_creates_log_file_and_writes(self):
        """Handler writes records to aio_folder/aio_monitor.log."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            path = setup_file_logging(tmpdir, root_logger=self.log)
            self.assertEqual(path, self._log_path(tmpdir))
            self.log.info("hello-cold-check")
            for handler in self.log.handlers:
                handler.flush()
            with open(path, encoding="utf-8") as f:
                self.assertIn("hello-cold-check", f.read())

    def test_idempotent_second_call_attaches_nothing(self):
        """Calling twice for the same folder adds exactly one handler."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            first = setup_file_logging(tmpdir, root_logger=self.log)
            second = setup_file_logging(tmpdir, root_logger=self.log)
            self.assertEqual(first, second)
            self.assertEqual(len(self.log.handlers), 1)

    def test_rotation_caps_at_three_files(self):
        """Forced tiny rotation keeps live + 2 backups, never a .3 file."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            setup_file_logging(tmpdir, root_logger=self.log, max_bytes=200, backup_count=2)
            for i in range(60):
                self.log.info(f"rotation-probe-line-{i:03d}-padding-xxxxxxxxxx")
            for handler in self.log.handlers:
                handler.flush()
            base = self._log_path(tmpdir)
            self.assertTrue(os.path.exists(base))
            self.assertTrue(os.path.exists(base + ".1"))
            self.assertTrue(os.path.exists(base + ".2"))
            self.assertFalse(os.path.exists(base + ".3"))

    def test_unwritable_folder_returns_none(self):
        """os.makedirs failure is swallowed, returns None."""
        with patch("utilities.logging_setup.os.makedirs", side_effect=OSError("read-only")):
            self.assertIsNone(setup_file_logging("/definitely/not/writable", root_logger=self.log))
        self.assertEqual(self.log.handlers, [])

    def test_handler_open_failure_returns_none(self):
        """RotatingFileHandler constructor failure is swallowed."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("utilities.logging_setup.RotatingFileHandler", side_effect=OSError("locked")):
                self.assertIsNone(setup_file_logging(tmpdir, root_logger=self.log))
            self.assertEqual(self.log.handlers, [])

    def test_production_constants(self):
        """5MB cap and 3-files-total contract."""
        self.assertEqual(LOG_MAX_BYTES, 5 * 1024 * 1024)
        self.assertEqual(LOG_BACKUP_COUNT, 2)
        self.assertEqual(LOG_FILENAME, "aio_monitor.log")

    def test_env_opt_out_disables_file_logging(self):
        """AIO_NO_FILE_LOG set -> no handler attached, returns None."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AIO_NO_FILE_LOG": "1"}):
                self.assertIsNone(setup_file_logging(tmpdir, root_logger=self.log))
            self.assertEqual(self.log.handlers, [])


if __name__ == "__main__":
    unittest.main()
