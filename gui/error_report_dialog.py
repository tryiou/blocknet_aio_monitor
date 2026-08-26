import logging
import os
import platform
import webbrowser
from typing import Optional

import customtkinter as ctk

import widgets_strings

logger = logging.getLogger(__name__)


class ErrorReportDialog(ctk.CTkToplevel):
    """Copy-paste friendly error report dialog for launch failures."""

    def __init__(
        self,
        parent,
        title: str = "Launch failed",
        report_text: str = "",
        app_name: str = "",
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.report_text = report_text
        self.app_name = app_name

        self.title(title)
        self.geometry("700x520")
        self.lift()
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.resizable(False, False)
        self.grab_set()

        self.after(10, self._create_widgets)

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkLabel(
            master=self,
            text=f"{self.app_name} failed to start" if self.app_name else "Launch failed",
            font=ctk.CTkFont(size=16, weight="bold"),
            wraplength=660,
            justify="left",
        )
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        hint = ctk.CTkLabel(
            master=self,
            text=widgets_strings.launch_failed_hint,
            wraplength=660,
            justify="left",
            text_color="gray",
        )
        hint.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        # adjust row weight after hint
        self.grid_rowconfigure(2, weight=1)

        self.textbox = ctk.CTkTextbox(master=self, width=660, height=360, wrap="word")
        self.textbox.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.textbox.insert("0.0", self.report_text)
        self.textbox.configure(state="disabled")

        btn_frame = ctk.CTkFrame(master=self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.copy_btn = ctk.CTkButton(
            master=btn_frame, text="Copy to Clipboard", command=self._copy_to_clipboard, width=140
        )
        self.copy_btn.grid(row=0, column=0, padx=5, sticky="ew")

        self.save_btn = ctk.CTkButton(
            master=btn_frame, text="Save to File", command=self._save_to_file, width=140
        )
        self.save_btn.grid(row=0, column=1, padx=5, sticky="ew")

        self.github_btn = ctk.CTkButton(
            master=btn_frame, text="Open GitHub Issues", command=self._open_github, width=140
        )
        self.github_btn.grid(row=0, column=2, padx=5, sticky="ew")

        self.close_btn = ctk.CTkButton(
            master=btn_frame, text="Close", command=self._on_close, width=140, fg_color="gray"
        )
        self.close_btn.grid(row=0, column=3, padx=5, sticky="ew")

        self.status_label = ctk.CTkLabel(master=self, text="", text_color="green")
        self.status_label.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="w")

    def _copy_to_clipboard(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.report_text)
            self.update()
            self.status_label.configure(text="Copied to clipboard", text_color="green")
            self.after(2000, lambda: self.status_label.configure(text=""))
            logger.info("Error report copied to clipboard")
        except Exception as e:
            logger.error(f"Clipboard copy failed: {e}")
            self.status_label.configure(text=f"Copy failed: {e}", text_color="red")

    def _save_to_file(self):
        try:
            from utilities.app_container import get_container

            container = get_container()
            aio_folder = container.aio_folder or os.path.expanduser("~")
            safe_name = "".join(c for c in self.app_name.lower() if c.isalnum() or c in ("-", "_")) or "app"
            path = os.path.join(aio_folder, f"error_report_{safe_name}.txt")
            # ensure unique with exclusive create to avoid symlink race
            base, ext = os.path.splitext(path)
            counter = 1
            target = path
            while os.path.exists(target):
                target = f"{base}_{counter}{ext}"
                counter += 1
                if counter > 20:
                    break
            # use exclusive create
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            f = None
            try:
                f = os.fdopen(fd, "w", encoding="utf-8")
                f.write(self.report_text)
                f.close()
                f = None
                fd = None
            finally:
                if f is not None:
                    try:
                        f.close()
                    except Exception:
                        pass
                elif fd is not None:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
            self.status_label.configure(text=f"Saved to {target}", text_color="green")
            logger.info(f"Error report saved to {target}")
        except Exception as e:
            logger.error(f"Failed to save report: {e}", exc_info=True)
            self.status_label.configure(text=f"Save failed: {e}", text_color="red")

    def _open_github(self):
        try:
            webbrowser.open(widgets_strings.github_issue_url)
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")

    def _on_close(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


def build_report(
    app_name: str,
    returncode: Optional[int],
    command: Optional[list],
    cwd: Optional[str],
    stderr_text: Optional[str],
    executable_path: Optional[str] = None,
    extra_info: Optional[str] = None,
) -> str:
    """Build a copy-pasteable report for GitHub issues."""
    lines = []
    lines.append(f"App: {app_name}")
    lines.append(f"Return code: {returncode}")
    lines.append(f"System: {platform.system()} {platform.machine()} / Python {platform.python_version()}")
    lines.append(f"Executable: {executable_path or 'unknown'}")
    if command:
        safe_cmd = " ".join(str(c) for c in command if c is not None)
        lines.append(f"Command: {safe_cmd or 'unknown'}")
    else:
        lines.append("Command: unknown")
    lines.append(f"CWD: {cwd or 'unknown'}")
    lines.append("")
    lines.append("Stderr / meaningful error:")
    if stderr_text and stderr_text.strip():
        # limit to last 80 lines to avoid huge dumps
        stderr_lines = stderr_text.strip().splitlines()
        if len(stderr_lines) > 80:
            stderr_lines = stderr_lines[-80:]
            lines.append("(truncated, showing last 80 lines)")
        lines.extend(stderr_lines)
    else:
        lines.append("(no stderr captured — check console log)")
    if extra_info:
        lines.append("")
        lines.append("Extra:")
        lines.append(extra_info)
    lines.append("")
    lines.append("Please attach this report to a new GitHub issue:")
    lines.append(widgets_strings.github_issue_url)
    return "\n".join(lines)


def show_error_report(
    parent,
    app_name: str,
    returncode: Optional[int],
    command: Optional[list],
    cwd: Optional[str],
    stderr_text: Optional[str],
    executable_path: Optional[str] = None,
    extra_info: Optional[str] = None,
) -> None:
    """Thread-safe helper: schedule dialog on main thread if needed."""
    report = build_report(app_name, returncode, command, cwd, stderr_text, executable_path, extra_info)
    title = f"{app_name} failed to start (code {returncode})" if returncode is not None else f"{app_name} launch error"

    def _show():
        try:
            # avoid opening multiple dialogs for same failure; check existing
            ErrorReportDialog(parent, title=title, report_text=report, app_name=app_name)
            logger.info(f"Showing error report dialog for {app_name} code {returncode}")
        except Exception as e:
            logger.error(f"Failed to show error dialog: {e}", exc_info=True)
            # fallback to console
            logger.error(report)

    try:
        # Use after to ensure main thread
        parent.after(0, _show)
    except Exception:
        # parent may not have after (mock); call directly
        _show()
