# vulture_whitelist_prod.py — prod-only whitelist (strict, no test fixtures)
# Used for second Vulture step: `vulture utilities/ gui/ blocknet_aio_monitor.py vulture_whitelist_prod.py --min-confidence 80`
# This file whitelists *production* false positives only.
# Test fixtures (mock_file_operations_safe, unit_test_mocks, etc.) are INTENTIONALLY NOT whitelisted
# here so that `prod-only` reports them as deviations (test-only code that should be prod or removed).

# GUI managers — invoked via getattr / tkinter callbacks
whitelist_gui_callbacks = [
    "setup",
    "on_button_click",
    "update_status",
]

# Vendored custom_tk_mods — upstream API
whitelist_custom_tk = [
    "ctkCheckBox",
    "ctkInputDialogMod",
]

# Utilities — false positives from dynamic imports / platform guards
whitelist_utils = [
    "winreg",
    "dmg_path",
    "mount_point",
]

# --- Vulture 80 prod-only whitelist — generated via --make-whitelist on prod PATH ---
frame  # unused variable (blocknet_aio_monitor.py:442)
index  # unused variable (custom_tk_mods/ctkCheckBox.py:455)
var_name  # unused variable (custom_tk_mods/ctkCheckBox.py:455)
dmg_path  # unused variable (utilities/bin_handlers/base_binutil.py:110)
mount_point  # unused variable (utilities/bin_handlers/base_binutil.py:110)

# Keep file non-empty for vulture; dummy avoids Ruff F821
whitelist_dummy_keepalive = True  # noqa: F401
