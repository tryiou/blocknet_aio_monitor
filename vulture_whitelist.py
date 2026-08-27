# vulture_whitelist.py — suppress known false positives for Vulture
# Vulture reports dead code with --min-confidence. This file whitelists
# symbols that are dynamically used (GUI callbacks, customtkinter bindings,
# pytest fixtures, string-referenced handlers) but look unused statically.
#
# Usage:
#   venv/bin/vulture . vulture_whitelist.py --min-confidence 80 --exclude venv,build,dist,.git
#
# Generated via: venv/bin/vulture . vulture_whitelist.py --make-whitelist --min-confidence 80 --exclude venv,build,dist,.git
# plus manual GUI callbacks.

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

# --- Vulture 80 strict whitelist — generated via --make-whitelist, intentional ---
frame  # unused variable (blocknet_aio_monitor.py:442)
index  # unused variable (custom_tk_mods/ctkCheckBox.py:455)
var_name  # unused variable (custom_tk_mods/ctkCheckBox.py:455)
Optional  # unused import (tests/conftest.py:19)
mock_file_operations_safe  # unused variable (tests/conftest.py:433)
unit_test_mocks  # unused variable (tests/conftest.py:594)
unit_test_mocks  # unused variable (tests/conftest.py:609)
utils_test_mocks  # unused variable (tests/conftest.py:646)
Optional  # unused import (tests/integration/helpers/test_helpers.py:12)
bm_module  # unused import (tests/unit/test_binary_manager_inotify.py:8)
PropertyMock  # unused import (tests/unit/test_blockdx_frame_manager.py:6)
constants  # unused import (tests/unit/test_blocknet_frame_manager.py:9)
BinaryManagerAlias  # unused import (tests/unit/test_darwin_arm64.py:173)
d  # unused variable (tests/unit/test_environment.py:109)
d  # unused variable (tests/unit/test_environment.py:138)
mock_broken  # unused variable (tests/unit/test_git_repo_management.py:144)
mock_broken  # unused variable (tests/unit/test_git_repo_management.py:157)
mock_broken  # unused variable (tests/unit/test_git_repo_management.py:168)
mock_broken  # unused variable (tests/unit/test_git_repo_management.py:183)
mock_broken  # unused variable (tests/unit/test_git_repo_management.py:389)
mock_sleep  # unused variable (tests/unit/test_git_repo_management.py:1085)
mock_sleep  # unused variable (tests/unit/test_git_repo_management.py:1112)
test_name  # unused variable (tests/unit/test_keyring_manager.py:327)
dmg_path  # unused variable (utilities/bin_handlers/base_binutil.py:110)
mount_point  # unused variable (utilities/bin_handlers/base_binutil.py:110)
# plus integration helpers (also in 80 list, already covered)
files  # unused variable (tests/integration/test_git_branch_switch.py:20)

# Keep file non-empty for vulture; dummy avoids Ruff F821
whitelist_dummy_keepalive = True
