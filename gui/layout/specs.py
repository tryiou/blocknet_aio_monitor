"""Declarative, Tk-free layout specs. One spec per panel; renderer.py applies them.

Tests assert these pure dataclasses — never mock .grid() calls.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TitleSpec:
    """Title bar: caption col 0, middle controls, right action hugging the edge."""

    caption: str  # widget attr name
    middle: tuple[tuple[str, str], ...] = ()  # (attr name, control kind) pairs
    right: str | None = None  # widget attr name
    right_column: int | None = None  # override grid column (default: just after middle)
    compact: bool = False  # dense pads for crowded rows (XLite title)


@dataclass(frozen=True)
class StatusGridSpec:
    """2-column checkbox grid, filled row-major."""

    boxes: tuple[str, ...]  # widget attr names
    start_row: int = 1


@dataclass(frozen=True)
class EntryRowSpec:
    """Core data-path row inside the title frame."""

    label: str
    entry: str
    button: str
    row: int = 1


@dataclass(frozen=True)
class BinaryTableSpec:
    """Binary panel rows: label / optionmenu / found / [spacer] / install / start."""

    rows: tuple[tuple[str, str, str, str, str], ...]
    start_row: int = 1


@dataclass(frozen=True)
class PanelSpec:
    title: TitleSpec
    entry_row: EntryRowSpec | None = None
    grid: StatusGridSpec | None = None
    table: BinaryTableSpec | None = None
    title_span: int = 2  # master columns the title frame spans


BINARY_ROWS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "blocknet_label",
        "blocknet_version_optionmenu",
        "blocknet_found_checkbox",
        "install_delete_blocknet_button",
        "blocknet_start_close_button",
    ),
    (
        "blockdx_label",
        "blockdx_version_optionmenu",
        "blockdx_found_checkbox",
        "install_delete_blockdx_button",
        "blockdx_start_close_button",
    ),
    (
        "xlite_label",
        "xlite_version_optionmenu",
        "xlite_found_checkbox",
        "install_delete_xlite_button",
        "xlite_toggle_execution_button",
    ),
    (
        "bots_label",
        "bots_version_optionmenu",
        "bots_found_checkbox",
        "install_delete_bots_button",
        "bots_toggle_execution_button",
    ),
)

BINARY_SPEC = PanelSpec(
    title=TitleSpec(caption="header_label", right="button_switch_theme"),
    table=BinaryTableSpec(rows=BINARY_ROWS),
    title_span=6,
)

CORE_SPEC = PanelSpec(
    title=TitleSpec(caption="label", right="download_bootstrap_button", right_column=3),
    entry_row=EntryRowSpec(label="data_path_label", entry="data_path_entry", button="custom_path_button"),
    grid=StatusGridSpec(
        boxes=(
            "data_path_status_checkbox",
            "conf_status_checkbox",
            "process_status_checkbox",
            "rpc_connection_checkbox",
        ),
        start_row=2,
    ),
)

BLOCKDX_SPEC = PanelSpec(
    title=TitleSpec(caption="label"),
    grid=StatusGridSpec(boxes=("process_status_checkbox", "valid_config_checkbox")),
)

XLITE_SPEC = PanelSpec(
    title=TitleSpec(
        caption="xlite_label",
        middle=(
            ("xbridge_block_source_label", "label"),
            ("xbridge_block_segmented", "segmented"),
        ),
        right="store_password_button",
        compact=True,
    ),
    grid=StatusGridSpec(
        boxes=(
            "process_status_checkbox",
            "daemon_process_status_checkbox",
            "valid_config_checkbox",
            "daemon_valid_config_checkbox",
        ),
    ),
)

PANEL_ORDER: tuple[str, ...] = ("binary", "core", "blockdx", "xlite")

PANEL_SPECS: dict[str, PanelSpec] = {
    "binary": BINARY_SPEC,
    "core": CORE_SPEC,
    "blockdx": BLOCKDX_SPEC,
    "xlite": XLITE_SPEC,
}
