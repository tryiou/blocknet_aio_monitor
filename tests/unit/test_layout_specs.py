"""Pure layout-spec tests: no Tk, no mocks. A spec change is an intentional diff."""

import pytest

from gui.layout.specs import BINARY_SPEC, BLOCKDX_SPEC, CORE_SPEC, PANEL_ORDER, PANEL_SPECS, XLITE_SPEC


def test_panel_order_and_registry_complete():
    assert PANEL_ORDER == ("binary", "core", "blockdx", "xlite")
    assert set(PANEL_SPECS) == set(PANEL_ORDER)


def test_binary_table_has_four_complete_rows():
    assert len(BINARY_SPEC.table.rows) == 4
    for row in BINARY_SPEC.table.rows:
        assert len(row) == 5  # label, menu, found, install, start
    assert BINARY_SPEC.title.right == "button_switch_theme"
    assert BINARY_SPEC.title_span == 6  # spacer column included


def test_core_bootstrap_aligns_above_custom_path_column():
    assert CORE_SPEC.title.right == "download_bootstrap_button"
    assert CORE_SPEC.title.right_column == 3
    assert CORE_SPEC.entry_row.button == "custom_path_button"
    assert len(CORE_SPEC.grid.boxes) == 4


def test_blockdx_title_has_no_right_action():
    assert BLOCKDX_SPEC.title.right is None
    assert len(BLOCKDX_SPEC.grid.boxes) == 2


def test_xlite_title_hosts_pills_left_of_password():
    title = XLITE_SPEC.title
    assert list(title.middle) == [
        ("xbridge_block_source_label", "label"),
        ("xbridge_block_segmented", "segmented"),
    ]
    assert title.right == "store_password_button"
    assert title.compact is True
    assert len(XLITE_SPEC.grid.boxes) == 4


if __name__ == "__main__":
    pytest.main([__file__])
