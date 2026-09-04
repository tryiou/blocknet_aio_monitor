"""The ONLY module allowed to call .grid()/columnconfigure() for panel layout.

Each function applies one spec type with uniform pads/stickies from tokens.
"""

from typing import Any

from gui.layout import specs, tokens


def _pad(compact: bool):
    p = tokens.PAD_COMPACT if compact else tokens.PAD
    return {"padx": p, "pady": p}


def grid_title(title_frame, spec: specs.TitleSpec, ns: Any) -> None:
    """Caption col 0 (w); middle controls cols 1..n (col 1 carries weight);
    right action in the last column hugging the edge (e)."""
    pad = _pad(spec.compact)
    caption = getattr(ns, spec.caption)
    caption.grid(row=0, column=0, sticky=tokens.STICKY_W, **pad)
    last = 0
    for i, (attr, kind) in enumerate(spec.middle, start=1):
        getattr(ns, attr).grid(row=0, column=i, sticky=tokens.TITLE_MIDDLE_STICKY[kind], **pad)
        last = i
    title_frame.columnconfigure(1, weight=1)
    if spec.right is not None:
        right_col = spec.right_column if spec.right_column is not None else last + 1
        getattr(ns, spec.right).grid(row=0, column=right_col, sticky=tokens.STICKY_E, **pad)


def grid_status_grid(master_frame, spec: specs.StatusGridSpec, ns: Any) -> None:
    """2-column checkbox grid, row-major from start_row. Columns share weight
    equally so both checkbox columns are identical by construction."""
    for i, attr in enumerate(spec.boxes):
        row = spec.start_row + i // 2
        col = i % 2
        getattr(ns, attr).grid(row=row, column=col, padx=tokens.PAD, pady=tokens.PAD, sticky=tokens.STICKY_CHECK)
    master_frame.columnconfigure(0, weight=1)
    master_frame.columnconfigure(1, weight=1)


def grid_entry_row(title_frame, spec: specs.EntryRowSpec, ns: Any) -> None:
    """Core data-path row: label col 0, stretching entry col 1, button col 3."""
    getattr(ns, spec.label).grid(row=spec.row, column=0, padx=tokens.PAD, pady=tokens.PAD, sticky=tokens.STICKY_W)
    getattr(ns, spec.entry).grid(row=spec.row, column=1, padx=tokens.PAD, pady=tokens.PAD, sticky=tokens.STICKY_WE)
    getattr(ns, spec.button).grid(row=spec.row, column=3, padx=tokens.PAD, pady=tokens.PAD, sticky=tokens.STICKY_CHECK)


def grid_binary_table(master_frame, spec: specs.BinaryTableSpec, ns: Any) -> None:
    """Binary rows: label-e / menu-ew / found / SPACER col 3 (weight 1) / install / start-e.

    The spacer column replaces the legacy magic padx=(70,8) gutter.
    """
    for r, (label, menu, found, install, start) in enumerate(spec.rows, start=spec.start_row):
        getattr(ns, label).grid(row=r, column=0, padx=tokens.PAD, pady=tokens.PAD, sticky=tokens.STICKY_E)
        getattr(ns, menu).grid(row=r, column=1, sticky=tokens.STICKY_CHECK)
        getattr(ns, found).grid(row=r, column=2, padx=tokens.PAD, pady=tokens.PAD, sticky=tokens.STICKY_CHECK)
        getattr(ns, install).grid(row=r, column=4, padx=tokens.PAD, pady=tokens.PAD, sticky=tokens.STICKY_CHECK)
        getattr(ns, start).grid(row=r, column=5, padx=tokens.PAD, pady=tokens.PAD, sticky=tokens.STICKY_E)
    master_frame.columnconfigure(3, weight=1)
