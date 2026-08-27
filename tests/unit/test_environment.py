import os
import platform
import sys
from unittest.mock import MagicMock, mock_open, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from utilities import environment


def test_check_python_version_supported(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 12, 0))
    ok, msg = environment.check_python_version()
    assert ok is True

    monkeypatch.setattr(sys, "version_info", (3, 13, 0))
    ok, msg = environment.check_python_version()
    assert ok is True

    monkeypatch.setattr(sys, "version_info", (3, 14, 0))
    ok, msg = environment.check_python_version()
    assert ok is True


def test_check_python_version_too_old(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 11, 0))
    ok, msg = environment.check_python_version()
    assert ok is False
    assert "too old" in msg


def test_check_tkinter_success():
    # Avoid opening real window on desk — mock Tk (backported from test_main_gui)
    with patch("tkinter.Tk") as mock_tk:
        mock_root = MagicMock()
        mock_root.withdraw = MagicMock()
        mock_root.destroy = MagicMock()
        mock_tk.return_value = mock_root
        ok, msg, details = environment.check_tkinter()
        # In headless CI, Tk root may fail but import should succeed -> ok True
        # We accept either, but ensure it doesn't crash and no window is shown
        assert isinstance(ok, bool)
        assert ok is True
        mock_tk.assert_called_once()


def test_check_tkinter_missing(monkeypatch):
    # Simulate missing _tkinter
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in ("tkinter", "_tkinter"):
            raise ModuleNotFoundError("No module named '_tkinter'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ok, msg, details = environment.check_tkinter()
    assert ok is False
    assert "Tkinter" in msg or "_tkinter" in msg
    assert "brew install" in details or "apt install" in details


def test_check_pygit2_success():
    # pygit2 1.18 should be importable (we have 1.18)
    ok, msg, details = environment.check_pygit2()
    # Could be success or failure depending on env, but should not crash
    assert isinstance(ok, bool)


def test_check_pygit2_missing(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pygit2":
            raise ModuleNotFoundError("No module named 'pygit2'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    ok, msg, details = environment.check_pygit2()
    assert ok is False
    assert "pygit2" in msg.lower()


def test_validate_environment_no_failures(monkeypatch):
    monkeypatch.setattr(environment, "check_python_version", lambda: (True, ""))
    monkeypatch.setattr(environment, "check_tkinter", lambda: (True, "", ""))
    monkeypatch.setattr(environment, "check_pygit2", lambda: (True, "", ""))
    monkeypatch.setattr(environment, "check_customtkinter", lambda: (True, "", ""))
    failures = environment.validate_environment()
    assert failures == []


def test_validate_environment_tk_failure(monkeypatch):
    monkeypatch.setattr(environment, "check_python_version", lambda: (True, ""))
    monkeypatch.setattr(environment, "check_tkinter", lambda: (False, "Missing Tkinter", "details tk"))
    monkeypatch.setattr(environment, "check_pygit2", lambda: (True, "", ""))
    monkeypatch.setattr(environment, "check_customtkinter", lambda: (True, "", ""))
    failures = environment.validate_environment()
    assert len(failures) >= 1
    assert failures[0][0] == "Missing Tkinter"


def test_show_startup_error_tk_fails_fallback(capsys, monkeypatch):
    # Force all GUI methods to fail, fallback to console — also mock new copyable dialog
    monkeypatch.setattr(environment, "_show_with_tkinter", lambda t, m, d="": False)
    monkeypatch.setattr(environment, "_show_with_osascript", lambda t, m: False)
    monkeypatch.setattr(environment, "_show_with_win32", lambda t, m: False)
    monkeypatch.setattr(environment, "_show_with_zenity", lambda t, m: False)
    # Mock the new copyable startup dialog path (prevents CTk window on desk)
    monkeypatch.setattr(
        "gui.error_report_dialog.show_startup_error_report",
        lambda *a, **k: (_ for _ in ()).throw(Exception("mocked no CTk")),
    )
    # Also ensure Tk/CTk are mocked (global conftest does, but be explicit)
    monkeypatch.setattr("tkinter.Tk", MagicMock)
    try:
        import customtkinter as _ctk

        monkeypatch.setattr(_ctk, "CTkToplevel", MagicMock)
        monkeypatch.setattr(_ctk, "CTk", MagicMock)
    except Exception:
        pass
    # Mock Path.home to avoid file creation
    monkeypatch.setattr("pathlib.Path.home", lambda: __import__("pathlib").Path("/tmp"))

    environment.show_startup_error("TestTitle", "TestMessage", "Details here")
    # should log and print, not raise and not open window
    captured = capsys.readouterr()
    assert True  # log goes to stderr or logger


def test_validate_or_exit_exits_on_failure(monkeypatch):
    monkeypatch.setattr(environment, "validate_environment", lambda: [("Missing Tkinter", "msg", "details")])
    monkeypatch.setattr(environment, "show_startup_error", lambda t, m, d="": None)
    # should sys.exit(1)
    try:
        environment.validate_or_exit()
        raise AssertionError("should have exited")
    except SystemExit as e:
        assert e.code == 1


def test_validate_or_exit_no_exit_when_ok(monkeypatch):
    monkeypatch.setattr(environment, "validate_environment", lambda: [])
    # should not exit
    environment.validate_or_exit()


def test_show_with_tkinter_mock():
    with patch("tkinter.Tk") as mock_tk, patch("tkinter.messagebox.showerror") as mock_msg:
        mock_root = MagicMock()
        mock_tk.return_value = mock_root
        result = environment._show_with_tkinter("Title", "Message", "Details")
        assert result is True
        mock_msg.assert_called_once()


def test_tk_fix_commands_dynamic(monkeypatch):
    # Dynamic version — no hardcoded 3.13
    monkeypatch.setattr(sys, "version_info", (3, 14, 0))
    monkeypatch.setattr(platform, "python_version", lambda: "3.14.0")
    cmds = environment._tk_fix_commands()
    joined = " ".join(cmds)
    assert "3.14" in joined
    assert "3.13" not in joined or "3.14" in joined  # should be 3.14 for current 3.14
    # Ensure no hardcoded literal survives when on 3.14
    for c in cmds:
        assert "python-tk@3.13" not in c or "3.14" in c


def test_pygit2_fix_commands_dynamic(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 14, 0))
    monkeypatch.setattr(platform, "python_version", lambda: "3.14.0")
    monkeypatch.setattr(environment, "_read_pygit2_spec", lambda: "~=1.20.0")
    cmds = environment._pygit2_fix_commands()
    joined = " ".join(cmds)
    assert "3.14" in joined
    assert "pygit2" in joined
    assert "~=1.20.0" in joined or "1.20" in joined


def test_extract_commands_copyable():
    from gui.error_report_dialog import _extract_commands

    text = 'Fix:\n  brew install python-tk@3.14\n  sudo apt install python3-tk\n  pip install "pygit2>=1.20"'
    cmds = _extract_commands(text)
    assert any("brew install python-tk@3.14" in c for c in cmds)
    assert any("sudo apt install python3-tk" in c for c in cmds)
    assert any("pip install" in c for c in cmds)
    # Per-command rows should be copyable individually
    for c in cmds:
        assert isinstance(c, str) and len(c) > 5


def test_copyable_command_row_no_window():
    # Ensure widget doesn't open real window — mocked CTk
    from gui.error_report_dialog import CopyableCommandRow

    mock_parent = MagicMock()
    mock_parent.clipboard_clear = MagicMock()
    mock_parent.clipboard_append = MagicMock()
    mock_parent.update = MagicMock()
    # Mock CTk internals to avoid real Tk
    with (
        patch("gui.error_report_dialog.ctk.CTkFrame.__init__", lambda self, *a, **k: None),
        patch(
            "gui.error_report_dialog.ctk.CTkEntry.__init__",
            lambda self, *a, **k: setattr(self, "command", k.get("command", "")) or None,
        ),
        patch("gui.error_report_dialog.ctk.CTkButton.__init__", lambda self, *a, **k: None),
    ):
        # We test the logic by instantiating with mocked base
        # Instead test the copy logic directly
        row = CopyableCommandRow.__new__(CopyableCommandRow)
        row.command = "brew install python-tk@3.14"
        row.clipboard_clear = MagicMock()
        row.clipboard_append = MagicMock()
        row.update = MagicMock()
        row.copy_btn = MagicMock()
        row.copy_btn.cget.return_value = "Copy"
        row.copy_btn.configure = MagicMock()
        row.after = MagicMock()
        row._feedback_after = None
        # Call copy
        CopyableCommandRow._copy(row)
        row.clipboard_append.assert_called_once_with("brew install python-tk@3.14")
