"""Startup environment validation without requiring console debugging.

Provides checks for Python version, Tkinter, and pygit2 that can run
before any GUI imports, and shows errors via native dialogs when Tk
is unavailable (issue #26). No hardcoded Python versions.
"""

import logging
import os
import platform
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

MIN_PYTHON = (3, 12)

# For copy-paste reports
GITHUB_ISSUE_URL = "https://github.com/tryiou/blocknet_aio_monitor/issues/new"


def _current_py_mm() -> str:
    try:
        return f"{sys.version_info.major}.{sys.version_info.minor}"  # type: ignore
    except AttributeError:
        return f"{sys.version_info[0]}.{sys.version_info[1]}"  # type: ignore


def _current_py_version() -> str:
    try:
        return platform.python_version()
    except Exception:
        try:
            return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"  # type: ignore
        except AttributeError:
            return f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"  # type: ignore


def _python_exe() -> str:
    # Prefer sys.executable basename for venv recreation; fallback to pythonX.Y
    try:
        exe = Path(sys.executable).name if sys.executable else ""
    except Exception:
        exe = ""
    if not exe or exe in ("python", "python3"):
        exe = f"python{_current_py_mm()}"
    return exe


def _read_pygit2_spec() -> str:
    """Read pygit2 spec from requirements.txt dynamically, fallback to >=1.20."""
    try:
        req_path = Path(__file__).parent.parent / "requirements.txt"
        if req_path.exists():
            for line in req_path.read_text(encoding="utf-8").splitlines():
                # Strip inline comments
                line = line.split("#", 1)[0].strip()
                if line.startswith("pygit2"):
                    # line like 'pygit2~=1.20.0' or 'pygit2==1.18.0'
                    spec = line[len("pygit2") :].strip()
                    if spec:
                        return spec
    except Exception as e:
        logger.debug(f"Failed to read pygit2 spec: {e}")
    return ">=1.20"


def _tk_fix_commands() -> list[str]:
    py_mm = _current_py_mm()
    py_exe = _python_exe()
    system = platform.system()
    cmds: list[str] = []
    if system == "Darwin":
        cmds.append(f"brew install python-tk@{py_mm}")
        cmds.append(f"{py_exe} -m venv venv  # or: python{py_mm} -m venv venv")
        cmds.append(f"{py_exe} -m pip install -r requirements.txt  # or venv/bin/pip install -r requirements.txt")
    elif system == "Linux":
        # Try to give distro-specific but generic fallback
        cmds.append(
            f"sudo apt update && sudo apt install python{py_mm}-tk  # Debian/Ubuntu; fallback: sudo apt install python3-tk"  # noqa: E501
        )
        cmds.append(f"sudo dnf install python{py_mm}-tkinter  # Fedora/RHEL fallback: sudo dnf install python3-tkinter")
        cmds.append(f"{py_exe} -m venv venv && {py_exe} -m pip install -r requirements.txt")
    elif system == "Windows":
        cmds.append("Reinstall Python from python.org with 'tcl/tk and IDLE' checked")
        cmds.append(f"{py_exe} -m venv venv")
    else:
        cmds.append(f"Install Tk for Python {py_mm} for {system}")
        cmds.append(f"{py_exe} -m venv venv")
    return cmds


def _pygit2_fix_commands() -> list[str]:
    _current_py_mm()
    py_ver = _current_py_version()
    spec = _read_pygit2_spec()
    cmds: list[str] = []
    # Prefer upgrading to spec from requirements
    cmds.append(f'{_python_exe()} -m pip install --upgrade "pygit2{spec}"  # for Python {py_ver}')
    cmds.append(f"{_python_exe()} -m pip install -r requirements.txt  # recreate venv first if needed")
    # Fallback suggestion for wheel missing — dynamic, no hardcoded version
    fallback = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
    cmds.append(
        f"# If wheel still missing for {py_ver}, try Python {fallback}: brew install python@{fallback} && python{fallback} -m venv venv"  # noqa: E501
    )
    cmds.append("brew install libgit2  # macOS source build deps")
    cmds.append("sudo apt install libgit2-dev  # Debian/Ubuntu source build deps")
    return cmds


def check_python_version() -> tuple[bool, str]:
    ver = sys.version_info
    try:
        cur = (ver.major, ver.minor)  # type: ignore
        cur_str = f"{ver.major}.{ver.minor}"
    except AttributeError:
        # tests may monkeypatch to plain tuple
        cur = (ver[0], ver[1])  # type: ignore
        cur_str = f"{ver[0]}.{ver[1]}"
    if cur < MIN_PYTHON:
        return (
            False,
            f"Python {cur_str} is too old. Requires >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]}. "
            f"Current: {cur_str}, please install Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer.",
        )
    # No upper bound — allow any newer
    return True, ""


def check_tkinter() -> tuple[bool, str, str]:
    """Check Tkinter availability. Returns (ok, error_message, details)."""
    py_ver = _current_py_version()
    sys_info = f"System: {platform.system()} {platform.machine()}"
    py_info = f"Python: {py_ver} ({sys.executable})"
    try:
        import _tkinter  # noqa: F401
        import tkinter  # noqa: F401

        try:
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            root.destroy()
        except Exception as e:
            logger.debug(f"Tkinter root creation failed (headless?): {e}")
        return True, "", ""
    except ModuleNotFoundError as e:
        msg = str(e)
        if "_tkinter" in msg or "tkinter" in msg.lower():
            cmds = _tk_fix_commands()
            details = (
                f"Python Tkinter not found: {e}\n"
                f"{sys_info}\n"
                f"{py_info}\n\n"
                "Fix — run one of these (click to copy):\n" + "\n".join(f"  {c}" for c in cmds)
            )
            return False, "Tkinter / _tkinter not found — GUI cannot start", details
        return False, f"Tkinter import failed: {e}", str(e)
    except Exception as e:
        return False, f"Tkinter check failed: {e}", str(e)


def check_pygit2() -> tuple[bool, str, str]:
    """Check pygit2 importability (covers missing libgit2 / git2.h and Python version mismatch)."""
    py_ver = _current_py_version()
    sys_info = f"Python: {py_ver} on {platform.system()} {platform.machine()} ({sys.executable})"
    spec = _read_pygit2_spec()
    try:
        import pygit2  # noqa: F401

        return True, "", f"pygit2 {pygit2.__version__} ok"
    except ModuleNotFoundError as e:
        cmds = _pygit2_fix_commands()
        details = f"pygit2 not installed or missing dependency: {e}\n{sys_info}\n\nFix — click to copy:\n" + "\n".join(
            f"  {c}" for c in cmds
        )
        return False, "pygit2 not available — blockchain config sync will fail", details
    except ImportError as e:
        msg = str(e)
        cmds = _pygit2_fix_commands()
        details = (
            f"pygit2 import error: {e}\n"
            f"{sys_info}\n"
            f"Current requirements spec: pygit2{spec}\n\n"
            "This often happens when Python version doesn't have a wheel.\n"
            "Fix — click to copy:\n" + "\n".join(f"  {c}" for c in cmds)
        )
        return False, "pygit2 failed to load", details + f"\nOriginal: {msg}"
    except Exception as e:
        return False, f"pygit2 check failed: {e}", str(e)


def check_customtkinter() -> tuple[bool, str, str]:
    try:
        import customtkinter  # noqa: F401

        return True, "", ""
    except Exception as e:
        return False, f"customtkinter not available: {e}", str(e)


def validate_environment() -> list[tuple[str, str, str]]:
    """Run all checks, return list of (title, message, details) for failures that should block startup."""
    failures = []
    ok, msg = check_python_version()
    if not ok:
        failures.append(("Unsupported Python version", msg, f"Python {_current_py_version()}"))

    ok, msg, details = check_tkinter()
    if not ok:
        failures.append(("Missing Tkinter", msg, details))

    # Only check pygit2/customtkinter if Tk passed, otherwise error would be noisy
    if not any("Tkinter" in f[0] for f in failures):
        ok, msg, details = check_pygit2()
        if not ok:
            failures.append(("Missing pygit2", msg, details))

        ok, msg, details = check_customtkinter()
        if not ok:
            failures.append(("Missing GUI dependency", msg, details))

    return failures


def _show_with_tkinter(title: str, message: str, details: str = "") -> bool:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        full = message
        if details:
            full += "\n\nDetails:\n" + details
        full += f"\n\nReport: {GITHUB_ISSUE_URL}"
        messagebox.showerror(title, full, parent=root)
        root.destroy()
        return True
    except Exception as e:
        logger.debug(f"Tkinter dialog failed: {e}")
        return False


def _show_with_osascript(title: str, message: str) -> bool:
    if platform.system() != "Darwin":
        return False
    try:
        safe_msg = message.replace('"', "'").replace("\n", "\\n")[:1800]
        safe_title = title.replace('"', "'")
        script = f'display dialog "{safe_msg}" with title "{safe_title}" buttons {{"OK"}} default button "OK"'
        subprocess.run(["osascript", "-e", script], check=False, timeout=5)
        return True
    except Exception as e:
        logger.debug(f"osascript failed: {e}")
        return False


def _show_with_zenity(title: str, message: str) -> bool:
    if platform.system() not in ("Linux",):
        return False
    for cmd in [
        ["zenity", "--error", f"--title={title}", f"--text={message[:2000]}", "--width=600"],
        ["kdialog", "--sorry", message[:2000], "--title", title],
        ["xmessage", "-center", f"{title}: {message[:2000]}"],
    ]:
        try:
            subprocess.run(cmd, check=False, timeout=5)
            return True
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.debug(f"zenity/kdialog failed {cmd[0]}: {e}")
            continue
    return False


def _show_with_win32(title: str, message: str) -> bool:
    if platform.system() != "Windows":
        return False
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, message[:4000], title, 0x10)
        return True
    except Exception as e:
        logger.debug(f"Win32 MessageBox failed: {e}")
        return False


def show_startup_error(title: str, message: str, details: str = "") -> None:
    """Show startup error without requiring prior GUI setup. Always logs."""
    full_msg = f"{title}: {message}"
    if details:
        full_msg += f"\n\n{details}"
    logger.error(full_msg)
    try:
        from pathlib import Path

        log_path = Path.home() / ".AIO_Blocknet_startup_error.log"
        # Mitigate symlink attack: don't follow symlink, use O_NOFOLLOW where available
        try:
            # Check and remove symlink if it exists (avoid truncating target)
            if log_path.is_symlink():
                try:
                    log_path.unlink()
                except Exception:
                    pass
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            # O_NOFOLLOW available on Linux/macOS
            try:
                flags |= os.O_NOFOLLOW
            except AttributeError:
                pass
            fd = os.open(str(log_path), flags, 0o600)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(
                        full_msg
                        + f"\n\nPython: {_current_py_version()} {platform.system()} "
                        f"{platform.machine()} ({sys.executable})\n"
                    )
                    f.write(f"Report: {GITHUB_ISSUE_URL}\n")
                    fd = None
            finally:
                if fd is not None:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
        except Exception:
            pass
    except Exception:
        pass

    combined = f"{message}\n\n{details}" if details else message
    # Try CTk copyable dialog if Tk is actually available (even though check failed for other reason)
    # We attempt to show a copyable dialog via ErrorReportDialog if possible
    try:
        # Check if we can import CTk (means Tk is partially available)
        import tkinter as _tk  # noqa: F401

        # Use the copyable startup dialog
        from gui.error_report_dialog import show_startup_error_report

        # Extract commands from details for per-row copy
        show_startup_error_report(title, message, details)
        return
    except Exception as e:
        logger.debug(f"Copyable startup dialog not available: {e}")

    if _show_with_tkinter(title, message, details):
        return
    if _show_with_osascript(title, combined):
        return
    if _show_with_win32(title, combined):
        return
    if _show_with_zenity(title, combined):
        return
    try:
        print(f"ERROR: {title}: {message}", file=sys.stderr)
        if details:
            print(details, file=sys.stderr)
    except Exception:
        pass


def validate_or_exit() -> None:
    """Validate and exit with dialog if critical failures found. For #26, non-zero exit after dialog."""
    failures = validate_environment()
    if failures:
        title, msg, details = failures[0]
        if len(failures) > 1:
            details += "\n\nAdditional issues:\n" + "\n".join(f"- {t}: {m}" for t, m, _ in failures[1:])
        show_startup_error(title, msg, details)
        sys.exit(1)
