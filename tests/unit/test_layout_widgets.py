"""SegmentedPills adapter tests: theme-native colors, per-state repaint, no Tk."""

from unittest.mock import MagicMock, patch

import pytest

THEME = {
    "CTkEntry": {
        "fg_color": ["#F9F9FA", "#123149"],
        "text_color": ["gray10", "#DCE4EE"],
        "placeholder_text_color": ["gray52", "gray55"],
    },
    "CTkSegmentedButton": {"text_color_disabled": ["gray60", "gray74"]},
}


@pytest.fixture
def pills():
    with (
        patch("gui.layout.widgets.ctk") as mock_ctk,
        patch("gui.layout.widgets.ctkCheckBoxMod"),
    ):
        mock_ctk.ThemeManager.theme = THEME
        segmented = MagicMock()
        mock_ctk.CTkSegmentedButton.return_value = segmented
        from gui.layout.widgets import SegmentedPills

        adapter = SegmentedPills(
            parent=MagicMock(),
            values=["Core", "XLite"],
            variable=MagicMock(),
            command=MagicMock(),
        )
        yield adapter, segmented


def test_construction_kwargs_are_theme_native(pills):
    adapter, segmented = pills
    import gui.layout.widgets as widgets_mod

    _ = adapter
    call_kwargs = widgets_mod.ctk.CTkSegmentedButton.call_args[1]
    assert call_kwargs["values"] == ["Core", "XLite"]
    assert call_kwargs["fg_color"] == THEME["CTkEntry"]["fg_color"]
    assert call_kwargs["unselected_color"] == THEME["CTkEntry"]["fg_color"]
    assert call_kwargs["unselected_hover_color"] == THEME["CTkEntry"]["fg_color"]
    assert "selected_color" not in call_kwargs


def test_repaint_marks_selected_vs_unselected(pills):
    adapter, segmented = pills
    core_btn, xlite_btn = MagicMock(), MagicMock()
    segmented._buttons_dict = {"Core": core_btn, "XLite": xlite_btn}
    segmented.get.return_value = "XLite"

    adapter.repaint()

    xlite_btn.configure.assert_called_with(
        text_color=[THEME["CTkEntry"]["text_color"][0], THEME["CTkEntry"]["text_color"][1]]
    )
    core_btn.configure.assert_called_with(
        text_color=[
            THEME["CTkEntry"]["placeholder_text_color"][0],
            THEME["CTkSegmentedButton"]["text_color_disabled"][0],
        ]
    )


def test_repaint_skips_non_dict_buttons(pills):
    adapter, segmented = pills
    segmented._buttons_dict = MagicMock()

    adapter.repaint()  # must not raise


def test_set_repaints(pills):
    adapter, segmented = pills
    segmented._buttons_dict = {}

    adapter.set("Core")

    segmented.set.assert_called_once_with("Core")


if __name__ == "__main__":
    pytest.main([__file__])
