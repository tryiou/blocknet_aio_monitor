"""Shared frame-manager base: owns master/title frames and shell grid.

Subclasses build widgets via gui.layout.widgets factories, declare their
spec in gui.layout.specs, and delegate grid_widgets() to the renderer.
"""

from gui.layout import renderer, specs, tokens, widgets


class BaseFrameManager:
    """Creates master/title frames; grids them into the root shell."""

    panel: str = ""

    def __init__(self, parent):
        self.parent = parent
        self.root_gui = parent.root_gui
        self.master_frame = widgets.make_frame(self.root_gui)
        self.title_frame = widgets.make_frame(self.master_frame)

    @property
    def spec(self) -> specs.PanelSpec:
        return specs.PANEL_SPECS[self.panel]

    def grid_shell(self, row: int) -> None:
        """Grid master + title frames into the root window (shell-owned rows)."""
        self.master_frame.grid(
            row=row,
            column=0,
            padx=tokens.PAD_FRAME_X,
            pady=tokens.PAD_FRAME_Y,
            sticky=tokens.STICKY_MAIN,
        )
        self.title_frame.grid(
            row=0,
            column=0,
            columnspan=self.spec.title_span,
            padx=tokens.PAD,
            pady=tokens.PAD,
            sticky=tokens.STICKY_TITLE,
        )

    def grid_widgets(self) -> None:
        """Apply the panel spec. No x/y args — rows are manager-local."""
        spec = self.spec
        renderer.grid_title(self.title_frame, spec.title, self)
        if spec.entry_row is not None:
            renderer.grid_entry_row(self.title_frame, spec.entry_row, self)
        if spec.grid is not None:
            renderer.grid_status_grid(self.master_frame, spec.grid, self)
        if spec.table is not None:
            renderer.grid_binary_table(self.master_frame, spec.table, self)
