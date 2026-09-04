# AGENTS.md - Blocknet AIO Monitor

## Overview
Python 3.12+ GUI application using customtkinter for monitoring Blocknet Core, Block-DX, and XLite wallets.
Cross-platform: Linux, Windows, macOS.

## Quick Commands

### Testing
```bash
# All tests (excluding network)
venv/bin/pytest tests/ -q

# By type
venv/bin/pytest tests/unit/ -q                    # Unit tests only
venv/bin/pytest tests/integration/ -q             # Integration tests only
venv/bin/pytest tests/ -m network -q              # Network-dependent tests
venv/bin/pytest tests/ -m gui -q                  # GUI tests

# Coverage
./test_coverage.sh

# Single test
venv/bin/pytest tests/unit/test_utils.py::TestUtils::test_function_name -v

# Other options
venv/bin/pytest tests/ --durations=10             # Show test durations
venv/bin/pytest tests/ -n auto                    # Parallel execution
```

### Running
```bash
venv/bin/python blocknet_aio_monitor.py
```

### Setup
```bash
python3 -m venv venv
source venv/bin/activate      # Linux/macOS
venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

## Code Standards

**Type Hints Required:**
```python
def run_command(cmd_list: List[str], cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    """Execute command and capture output."""
```

**Naming:**
- Classes: `PascalCase` (BinaryManager, TestConfigWorkflow)
- Functions/variables: `snake_case` (load_cfg_json, binary_manager)
- Constants: `UPPER_SNAKE_CASE` (TIME_DISABLE_BUTTON)

**Imports Order:**
```python
# 1. Standard library
import asyncio, logging
from pathlib import Path
from typing import List, Optional

# 2. Third-party
import customtkinter as ctk
from PIL import Image

# 3. Local
from utilities import utils
```

**Logging (no print statements):**
```python
logger = logging.getLogger(__name__)
logger.info("message")  # Use appropriate level: debug/info/warning/error
```

**Error Handling:**
```python
try:
    # code
except SpecificException as e:
    logger.error(f"Error: {e}", exc_info=True)
```

## Testing Guidelines

- **Isolation:** Tests use temp directories (`tests/conftest.py`), never touch `~/.AIO_Blocknet`
- **Markers:** `@pytest.mark.integration`, `@pytest.mark.network`, `@pytest.mark.gui`, `@pytest.mark.slow`
- **Test naming:** `test_<what>_<expected_behavior>` (e.g., `test_tooltip_text_updates_when_different`)
- **Fixtures:** Use pytest fixtures for setup/teardown

## Project Structure
```
blocknet_aio_monitor.py          # Entry point
gui/                             # GUI components (managers)
utilities/                       # Utils, config, logging
tests/unit/                      # Unit tests
tests/integration/               # Integration tests
tests/conftest.py                # Shared fixtures
```

## Key Patterns

**Async operations:**
```python
async def setup(self) -> None:
    await asyncio.gather(task1(), task2())
```

**Dependencies:**
- Use `~=` for compatible versions: `psutil~=5.9.8`
- Use `==` for pinned versions: `pygit2==1.18.0`

**Linting configured** — `pyproject.toml:1` (`[tool.ruff]`, `[tool.pytest.ini_options]`), `vulture_whitelist.py:1`, `vulture_whitelist_prod.py:1`, `requirements-dev.txt:5` (`ruff~=0.12.0`, `vulture~=2.14`, `pre-commit~=4.2`), CI `.github/workflows/lint.yml:1` (Ruff strict, Vulture global strict, Vulture prod-only warning).
```bash
venv/bin/ruff check .                          # lint (E,F,W,I,N,UP,S,B,C4,SIM, line-length 120)
venv/bin/ruff format --check . --diff          # format check (Black-compatible, 120)
venv/bin/ruff check --fix .                    # auto-fix where safe
venv/bin/vulture . vulture_whitelist.py --min-confidence 80 --exclude venv,build,dist,.git
venv/bin/vulture utilities/ gui/ blocknet_aio_monitor.py vulture_whitelist_prod.py --min-confidence 80 --exclude venv,build,dist,.git  # prod-only deviation
pre-commit install && pre-commit run --all-files  # opt-in, .pre-commit-config.yaml:1 ruff+vulture prod
```
