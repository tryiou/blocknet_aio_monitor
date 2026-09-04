"""Widget factories: the only place widgets are constructed with style.

Frame managers call these; no per-instance colors/sizes/pads elsewhere.
"""

import logging
from collections.abc import Callable, Sequence

import customtkinter as ctk

import custom_tk_mods.ctkCheckBox as ctkCheckBoxMod
from gui.layout import tokens

logger = logging.getLogger(__name__)


def make_frame(parent, width: int | None = None):
    kwargs = {"master": parent}
    if width is not None:
        kwargs["width"] = width
    return ctk.CTkFrame(**kwargs)


def make_caption(parent, text: str, width: int | None = None):
    kwargs = {"master": parent, "text": text, "anchor": tokens.STICKY_HEAD}
    if width is not None:
        kwargs["width"] = width
    return ctk.CTkLabel(**kwargs)


def make_label(parent, text: str):
    return ctk.CTkLabel(master=parent, text=text)


def make_button(parent, width: int = tokens.BUTTON_W, **kwargs):
    return ctk.CTkButton(master=parent, width=width, **kwargs)


def make_checkbox(parent, variable, textvariable=None, text="", width: int = tokens.CHECK_W):
    kwargs = {
        "variable": variable,
        "corner_radius": tokens.CORNER_R,
        "state": "disabled",
        "width": width,
    }
    if textvariable is not None:
        kwargs["textvariable"] = textvariable
    else:
        kwargs["text"] = text
    return ctkCheckBoxMod.CTkCheckBox(parent, **kwargs)


def make_optionmenu(parent, values: Sequence[str], width: int = tokens.OPTIONMENU_W, **kwargs):
    return ctk.CTkOptionMenu(master=parent, values=list(values), width=width, **kwargs)


def make_entry(parent, textvariable, width: int = tokens.ENTRY_W, readonly: bool = True):
    entry = ctk.CTkEntry(master=parent, textvariable=textvariable, state="normal", width=width)
    if readonly:
        entry.configure(state="readonly")
    return entry


def make_icon_button(parent, image, command: Callable[[], None]):
    """Transparent 1px button (theme toggle)."""
    return ctk.CTkButton(
        master=parent,
        image=image,
        command=command,
        text="",
        fg_color="transparent",
        hover=False,
        width=tokens.ICON_W,
    )


class SegmentedPills:
    """XBridge BLOCK source selector with per-state pill text.

    CTkSegmentedButton exposes a single text_color, so the selected pill is
    repainted from the live theme (Light/Dark toggle applies with no extra code).
    No tooltip: the widget has no bind() support (raises NotImplementedError).
    """

    def __init__(self, parent, values: list[str], variable, command: Callable[[str], None]):
        theme = ctk.ThemeManager.theme
        entry_text = theme["CTkEntry"]["text_color"]
        entry_placeholder = theme["CTkEntry"]["placeholder_text_color"]
        seg_disabled = theme["CTkSegmentedButton"]["text_color_disabled"]
        entry_blue = theme["CTkEntry"]["fg_color"]
        self.selected = [entry_text[0], entry_text[1]]
        self.unselected = [entry_placeholder[0], seg_disabled[0]]
        self.widget = ctk.CTkSegmentedButton(
            parent,
            values=values,
            variable=variable,
            command=command,
            fg_color=entry_blue,
            unselected_color=entry_blue,
            unselected_hover_color=entry_blue,
            text_color=self.unselected,
        )
        self.repaint()

    def repaint(self) -> None:
        try:
            current = self.widget.get()
            buttons = self.widget._buttons_dict
            if not isinstance(buttons, dict):
                return
            for value, button in buttons.items():
                button.configure(text_color=self.selected if value == current else self.unselected)
        except Exception as e:
            logger.debug(f"segmented pill repaint failed: {e}")

    def set(self, value: str) -> None:
        self.widget.set(value)
        self.repaint()

    def get(self) -> str:
        return self.widget.get()

    def configure(self, **kwargs) -> None:
        self.widget.configure(**kwargs)

    def grid(self, **kwargs) -> None:
        self.widget.grid(**kwargs)
