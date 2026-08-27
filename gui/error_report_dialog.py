import logging
import os
import platform
import re
import webbrowser
from typing import List, Optional

import customtkinter as ctk

import widgets_strings

logger = logging.getLogger(__name__)


def _extract_commands(text: str) -> list[str]:
    """Extract copyable shell commands from a report/details string."""
    if not text:
        return []
    cmds: list[str] = []
    # patterns for commands we want to make copyable
    prefixes = ("brew ", "sudo ", "pip ", "pip3 ", "python", "python3", "py ", "apt ", "dnf ", "sudo apt", "sudo dnf", "xcode-select")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip pure comment lines
        if stripped.startswith("#"):
            continue
        # Remove leading bullet/list markers
        cleaned = re.sub(r"^[-*•]\s*", "", stripped)
        cleaned = cleaned.lstrip()
        if not cleaned or cleaned.startswith("#"):
            continue
        # Heuristic: line that looks like a shell command
        lower = cleaned.lower()
        if any(lower.startswith(p) for p in prefixes) or cleaned.startswith("brew install") or " -m venv" in cleaned or " -m pip install" in cleaned:
            # Strip inline comment after # not in quotes (keep quoted #)
            # Simple: split on " # " with space hash space
            if " # " in cleaned:
                cleaned = cleaned.split(" # ", 1)[0].rstrip()
            # Also handle "  # comment" style already filtered, but keep
            cmds.append(cleaned)
        elif line.startswith("  ") and len(cleaned) > 4 and ("install" in lower or "venv" in lower):
            if " # " in cleaned:
                cleaned = cleaned.split(" # ", 1)[0].rstrip()
            cmds.append(cleaned)
    # dedupe preserve order
    seen = set()
    uniq = []
    for c in cmds:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq


class CopyableCommandRow(ctk.CTkFrame):
    """Row displaying a shell command with click-to-copy (select+ctrlC + button)."""

    def __init__(self, master, command: str, **kwargs):
        super().__init__(master, fg_color=("gray90", "gray20"), corner_radius=6, **kwargs)
        self.command = command
        self.grid_columnconfigure(0, weight=1)

        # Mono entry (readonly) so select+Ctrl-C works natively
        self.entry = ctk.CTkEntry(
            master=self,
            width=480,
            height=28,
            font=ctk.CTkFont(family="Courier", size=11),
            fg_color="transparent",
            border_width=0,
            state="normal",
        )
        self.entry.insert(0, command)
        self.entry.configure(state="readonly")
        self.entry.grid(row=0, column=0, padx=(8, 4), pady=4, sticky="ew")
        # clicking entry copies
        self.entry.bind("<Button-1>", self._on_click_copy)
        self.entry.bind("<Double-Button-1>", self._on_click_copy)
        # tooltip hint
        self.entry.bind("<Enter>", lambda e: self.entry.configure(cursor="hand2"))
        self.entry.bind("<Leave>", lambda e: self.entry.configure(cursor=""))
        # also make label-like click area
        self.bind("<Button-1>", self._on_click_copy)

        self.copy_btn = ctk.CTkButton(
            master=self,
            text="Copy",
            width=70,
            height=28,
            command=self._copy,
            fg_color=("#3a7ebf", "#1f538d"),
            hover_color=("#325882", "#14375e"),
        )
        self.copy_btn.grid(row=0, column=1, padx=(4, 8), pady=4)

        self._feedback_after = None

    def _copy(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.command)
            self.update()
            orig = self.copy_btn.cget("text")
            self.copy_btn.configure(text="Copied!")
            if self._feedback_after:
                self.after_cancel(self._feedback_after)
            self._feedback_after = self.after(1500, lambda: self.copy_btn.configure(text=orig))
            logger.info(f"Copied command to clipboard: {self.command}")
        except Exception as e:
            logger.error(f"Clipboard copy failed for command: {e}")

    def _on_click_copy(self, event=None):
        self._copy()
        # Select all for easy Ctrl-C, but don't break so drag-select still works
        try:
            self.entry.selection_clear()
            self.entry.selection_range(0, "end")
            self.entry.icursor("end")
        except Exception:
            pass
        # Don't return "break" — allow native drag-select for partial copy
        return None


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
            text=widgets_strings.launch_failed_hint + " Click any command to copy it.",
            wraplength=660,
            justify="left",
            text_color="gray",
        )
        hint.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        # adjust row weight after hint
        self.grid_rowconfigure(2, weight=1)

        self.textbox = ctk.CTkTextbox(master=self, width=660, height=280, wrap="word")
        self.textbox.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.textbox.insert("0.0", self.report_text)
        # Make readonly but keep selectable: normal state with key block except copy/select
        self.textbox.configure(state="normal")
        self.textbox.bind("<Key>", lambda e: "break" if not (e.state & 0x4 and e.keysym.lower() in ("c", "a", "x")) else None)
        self.textbox.bind("<Control-c>", lambda e: self._copy_selection())
        self.textbox.bind("<Control-a>", lambda e: self._select_all())
        # Also allow clicking to focus for selection
        self.textbox.bind("<Button-1>", lambda e: self.after(10, lambda: self.textbox.focus_set()))

        # Per-command copyable rows extracted from report (click to copy, select+CtrlC)
        commands = _extract_commands(self.report_text)
        if commands:
            cmd_label = ctk.CTkLabel(
                master=self, text="Fix commands — click to copy:", anchor="w", text_color=("gray30", "gray70")
            )
            cmd_label.grid(row=3, column=0, padx=20, pady=(5, 2), sticky="w")
            self.cmd_scroll = ctk.CTkScrollableFrame(master=self, height=90, fg_color="transparent")
            self.cmd_scroll.grid(row=4, column=0, padx=20, pady=(0, 5), sticky="nsew")
            for cmd in commands[:8]:  # limit to avoid overflow
                row = CopyableCommandRow(self.cmd_scroll, command=cmd)
                row.pack(fill="x", pady=2)
            btn_row = 5
        else:
            btn_row = 3

        btn_frame = ctk.CTkFrame(master=self, fg_color="transparent")
        btn_frame.grid(row=btn_row + 1, column=0, padx=20, pady=(10, 20), sticky="ew")
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
        self.status_label.grid(row=btn_row + 2, column=0, padx=20, pady=(0, 10), sticky="w")

    def _copy_selection(self):
        try:
            sel = self.textbox.selection_get()
            if sel:
                self.clipboard_clear()
                self.clipboard_append(sel)
                self.update()
                self.status_label.configure(text="Selection copied", text_color="green")
                self.after(1500, lambda: self.status_label.configure(text=""))
        except Exception:
            # fallback: copy all
            self._copy_to_clipboard()

    def _select_all(self):
        try:
            self.textbox.tag_add("sel", "0.0", "end")
        except Exception:
            pass
        return "break"

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
    returncode: int | None,
    command: list | None,
    cwd: str | None,
    stderr_text: str | None,
    executable_path: str | None = None,
    extra_info: str | None = None,
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
    returncode: int | None,
    command: list | None,
    cwd: str | None,
    stderr_text: str | None,
    executable_path: str | None = None,
    extra_info: str | None = None,
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


class StartupErrorDialog(ctk.CTkToplevel):
    """Copyable dialog for startup environment errors with per-command click-to-copy."""

    def __init__(self, parent, title: str, message: str, details: str = "", **kwargs):
        super().__init__(parent, **kwargs)
        self.title_text = title
        self.message = message
        self.details = details
        self.title(title)
        self.geometry("720x520")
        self.lift()
        self.attributes("-topmost", True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.resizable(False, False)
        # grab after widgets created
        self.after(10, self._create_widgets)

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkLabel(
            master=self,
            text=self.title_text,
            font=ctk.CTkFont(size=16, weight="bold"),
            wraplength=680,
            justify="left",
        )
        header.grid(row=0, column=0, padx=20, pady=(20, 8), sticky="w")

        msg_label = ctk.CTkLabel(
            master=self,
            text=self.message,
            wraplength=680,
            justify="left",
        )
        msg_label.grid(row=1, column=0, padx=20, pady=(0, 8), sticky="w")

        self.textbox = ctk.CTkTextbox(master=self, width=680, height=200, wrap="word")
        self.textbox.grid(row=2, column=0, padx=20, pady=8, sticky="nsew")
        full_details = self.details or ""
        self.textbox.insert("0.0", full_details)
        self.textbox.configure(state="normal")
        # Readonly: allow select/copy but block typing
        self.textbox.bind("<Key>", lambda e: "break" if not (e.state & 0x4 and e.keysym.lower() in ("c", "a", "x")) else None)
        self.textbox.bind("<Control-c>", lambda e: self._copy_selection())
        self.textbox.bind("<Control-a>", lambda e: self._select_all())
        self.textbox.bind("<Button-1>", lambda e: self.after(10, lambda: self.textbox.focus_set()))

        combined = f"{self.details}\n{self.message}"
        commands = _extract_commands(combined)
        if commands:
            cmd_label = ctk.CTkLabel(
                master=self, text="Fix commands — click to copy:", anchor="w", text_color=("gray30", "gray70")
            )
            cmd_label.grid(row=3, column=0, padx=20, pady=(5, 2), sticky="w")
            self.cmd_scroll = ctk.CTkScrollableFrame(master=self, height=110, fg_color="transparent")
            self.cmd_scroll.grid(row=4, column=0, padx=20, pady=(0, 5), sticky="nsew")
            for cmd in commands[:10]:
                row = CopyableCommandRow(self.cmd_scroll, command=cmd)
                row.pack(fill="x", pady=2)
            btn_row = 5
        else:
            btn_row = 3

        btn_frame = ctk.CTkFrame(master=self, fg_color="transparent")
        btn_frame.grid(row=btn_row + 1, column=0, padx=20, pady=(10, 10), sticky="ew")
        btn_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.copy_btn = ctk.CTkButton(master=btn_frame, text="Copy Details", command=self._copy_details, width=140)
        self.copy_btn.grid(row=0, column=0, padx=5, sticky="ew")

        self.github_btn = ctk.CTkButton(master=btn_frame, text="Open GitHub Issues", command=self._open_github, width=140)
        self.github_btn.grid(row=0, column=1, padx=5, sticky="ew")

        self.close_btn = ctk.CTkButton(master=btn_frame, text="Close / Exit", command=self._on_close, width=140, fg_color="gray")
        self.close_btn.grid(row=0, column=2, padx=5, sticky="ew")

        self.status_label = ctk.CTkLabel(master=self, text="", text_color="green")
        self.status_label.grid(row=btn_row + 2, column=0, padx=20, pady=(0, 10), sticky="w")
        self.grab_set()

    def _copy_selection(self):
        try:
            sel = self.textbox.selection_get()
            if sel:
                self.clipboard_clear()
                self.clipboard_append(sel)
                self.update()
                self.status_label.configure(text="Selection copied", text_color="green")
                self.after(1500, lambda: self.status_label.configure(text=""))
        except Exception:
            self._copy_details()

    def _select_all(self):
        try:
            self.textbox.tag_add("sel", "0.0", "end")
        except Exception:
            pass
        return "break"

    def _copy_details(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(f"{self.message}\n\n{self.details}")
            self.update()
            self.status_label.configure(text="Copied to clipboard", text_color="green")
            self.after(2000, lambda: self.status_label.configure(text=""))
        except Exception as e:
            self.status_label.configure(text=f"Copy failed: {e}", text_color="red")

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


def show_startup_error_report(title: str, message: str, details: str = "", parent=None) -> None:
    """Show startup error with copyable commands. Creates hidden root if needed and blocks until closed."""
    def _show_blocking(p):
        try:
            dialog = StartupErrorDialog(p, title=title, message=message, details=details)
            logger.info(f"Showing startup error dialog: {title}")
            # Block until dialog closed — needed before sys.exit(1)
            try:
                p.wait_window(dialog)
            except Exception:
                # Fallback: wait on dialog itself
                try:
                    dialog.wait_window()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Failed to show startup error dialog: {e}", exc_info=True)
            logger.error(f"{title}: {message}\n{details}")

    # If parent provided, use it directly (blocking)
    if parent is not None:
        try:
            _show_blocking(parent)
        except Exception as e:
            logger.error(f"Startup dialog with parent failed: {e}", exc_info=True)
        return

    # No parent: create hidden CTk root and block
    tmp_root = None
    try:
        tmp_root = ctk.CTk()
        tmp_root.withdraw()
        # Create dialog and block
        dialog = StartupErrorDialog(tmp_root, title=title, message=message, details=details)
        logger.info(f"Showing startup error dialog: {title}")
        try:
            tmp_root.wait_window(dialog)
        except Exception:
            try:
                dialog.wait_window()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Failed to create startup dialog root: {e}", exc_info=True)
        logger.error(f"{title}: {message}\n{details}")
    finally:
        if tmp_root is not None:
            try:
                tmp_root.destroy()
            except Exception:
                pass
