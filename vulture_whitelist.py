# vulture_whitelist.py — suppress known false positives for Vulture
# Vulture reports dead code with --min-confidence. This file whitelists
# symbols that are dynamically used (GUI callbacks, customtkinter bindings,
# pytest fixtures, string-referenced handlers) but look unused statically.
#
# Usage:
#   venv/bin/vulture . vulture_whitelist.py --min-confidence 80 --exclude venv,build,dist,.git
#
# Add entries like `whitelisted_function` or `WhitelistedClass` as needed.
# See: https://github.com/jendrikseipp/vulture#whitelists

# GUI managers — invoked via getattr / tkinter callbacks
whitelist_gui_callbacks = [
    "setup",
    "on_button_click",
    "update_status",
]

# Pytest fixtures in tests/conftest.py — imported implicitly by pytest
whitelist_pytest_fixtures = [
    "mock_file_operations_safe",
    "unit_test_mocks",
    "utils_test_mocks",
]

# Vendored custom_tk_mods — upstream API, may appear unused
whitelist_custom_tk = [
    "ctkCheckBox",
    "ctkInputDialogMod",
]

# Utilities — false positives from dynamic imports / platform guards
whitelist_utils = [
    "winreg",  # utilities/bin_handlers/xlite_handler.py:20 windows-only
    "dmg_path",
    "mount_point",
]

# Keep file non-empty for vulture; dummy avoids Ruff F821
whitelist_dummy_keepalive = True
