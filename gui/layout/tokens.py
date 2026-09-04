"""Single source of truth for all GUI geometry tokens.

Every size/pad/sticky in gui/ must come from here (via renderer/factories).
No raw width=/padx=/pady=/sticky= literals in frame managers.
"""

# Padding
PAD: int = 5
PAD_COMPACT: int = 2
PAD_FRAME_X: int = 10
PAD_FRAME_Y: int = 5

# Fixed widget widths (all dynamic text lives inside fixed-width widgets,
# so 1s poll StringVar updates can never resize the shrink-wrap window).
# Calibrated ~20% narrower than the v1.3.6 baseline (ENTRY 387, MENU 200, etc.)
BUTTON_W: int = 105
BIN_BUTTON_W: int = 75
CHECK_W: int = 165
OPTIONMENU_W: int = 160
ENTRY_W: int = 310
ICON_W: int = 1
HEADER_W: int = 400
BLOCKDX_LABEL_W: int = 470
CORNER_R: int = 25

# XLite title pin: its content (caption + pills + button) is narrower than the
# sibling titles, so the title frame is pinned to keep identical checkbox
# columns in every panel (v1.3.6 golden 598, scaled to the narrower window).
TITLE_W: int = 480

# Grid stickies
STICKY_TITLE: str = "ew"
STICKY_MAIN: str = "nsew"
STICKY_CHECK: str = "ew"
STICKY_HEAD: str = "nw"
STICKY_E: str = "e"
STICKY_W: str = "w"
STICKY_WE: str = "we"

# Title-row middle-slot stickies per control kind
TITLE_MIDDLE_STICKY: dict[str, str] = {"label": STICKY_E, "segmented": STICKY_W}

# Tooltip defaults (single styling source for TooltipManager registrations)
TOOLTIP_BG: tuple[str, str] = ("#ebebeb", "#051937")
TOOLTIP_DEFAULTS: dict[str, object] = {
    "bg_color": TOOLTIP_BG,
    "border_width": 2,
    "justify": "left",
    "delay": 1,
    "follow": True,
}
