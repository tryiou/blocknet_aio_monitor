# Mocking Strategy Documentation

## Overview

This document outlines the centralized mocking strategy implemented to reduce mocking redundancy in the Blocknet AIO Monitor test suite.

## Phase 1: Centralized Mock Patterns (Completed)

### New Fixtures in conftest.py

#### `mock_app_container_base`
```python
@pytest.fixture
def mock_app_container_base():
    """Base mock container with common properties."""
    container = MagicMock()
    container.system = "Linux"
    container.machine = "x86_64"
    container.aio_folder = "/test/aio"
    container.blocknet_release_url = "http://mock.com/blocknet"
    container.blockdx_release_url = "http://mock.com/blockdx"
    container.xlite_release_url = "http://mock.com/xlite"
    container.blockdx_curpath = "BLOCK-DX-1.0.0"
    container.xlite_curpath = "XLite-1.0.0"
    return container
```

#### `mock_gui_root_base`
```python
@pytest.fixture
def mock_gui_root_base():
    """Base mock GUI root with common properties."""
    mock_root = MagicMock()
    mock_root.tooltip_manager = MagicMock()
    mock_root.time_disable_button = 3000
    mock_root.theme_manager = MagicMock()
    mock_root.progress_manager = MagicMock()
    mock_root.network_monitor = MagicMock()
    mock_root.wallet_manager = MagicMock()
    return mock_root
```

#### `mock_file_operations_safe`
```python
@pytest.fixture
def mock_file_operations_safe():
    """Safe file operation mocks for unit tests."""
    with patch('os.path.exists') as mock_exists, \
         patch('os.path.isdir') as mock_isdir, \
         patch('os.path.isfile') as mock_isfile:
        mock_exists.return_value = True
        mock_isdir.return_value = True
        mock_isfile.return_value = False
        yield mock_exists, mock_isdir, mock_isfile
```

#### `mock_targeted_file_ops`
```python
@pytest.fixture
def mock_targeted_file_ops():
    """Targeted file operation mocking - only for specific paths."""
    def mock_exists_side_effect(path):
        return str(path) in ['/test/aio', '/test/aio/blocknet', '/test/aio/blockdx', '/test/aio/xlite']
    
    with patch('os.path.exists', side_effect=mock_exists_side_effect):
        yield
```

#### `unit_test_mocks`
```python
@pytest.fixture
def unit_test_mocks():
    """Mocks suitable for unit tests - minimal, focused."""
    with patch('subprocess.Popen') as mock_popen, \
         patch('psutil.Process') as mock_psutil, \
         patch('os.listdir') as mock_listdir:
        mock_listdir.return_value = []
        yield mock_popen, mock_psutil, mock_listdir
```

#### `integration_test_mocks`
```python
@pytest.fixture 
def integration_test_mocks():
    """Mocks suitable for integration tests - minimal mocking, real operations."""
    with patch('requests.get') as mock_requests:
        mock_requests.return_value.status_code = 200
        mock_requests.return_value.headers = {'Content-Length': '1024'}
        mock_requests.return_value.iter_content = lambda chunk_size: [b'x' * chunk_size]
        yield mock_requests
```

#### `utils_container_setup`
```python
@pytest.fixture
def utils_container_setup():
    """Standard container setup for utils tests."""
    with _utils_container_env(_build_utils_container()) as container:
        yield container
```

The `utils_container_setup*` family (`_with_binaries`, `_custom_exists`) shares two private helpers in conftest.py:

- `_build_utils_container(with_binaries=False)` - builds the mock container (data path, system, aio folder, optional binary names)
- `_utils_container_env(...)` - contextmanager applying the common patches: `utilities.utils.get_container`, `os.path.expanduser`, `os.path.expandvars`, and `os.path.exists` (defaults to `False`; a custom side effect can be supplied)

Similarly, `utils_test_setup` and `utils_test_setup_no_psutil_mock` share `_utils_test_env(container, temp_workspace)`, which patches the same targets but points paths at a real pytest `tmp_path` workspace.

## Usage Guidelines

### When to Use Centralized Fixtures

1. **Container Mocking**: Use `mock_app_container_base` for any tests that need a basic container mock
2. **GUI Root Mocking**: Use `mock_gui_root_base` for GUI-related tests
3. **File Operations**: Use `mock_file_operations_safe` for unit tests that need file system mocking
4. **Targeted File Operations**: Use `mock_targeted_file_ops` when you need specific path-based mocking
5. **Unit Tests**: Use `unit_test_mocks` for general unit test scenarios
6. **Integration Tests**: Use `integration_test_mocks` for integration tests that need minimal mocking

### How to Apply Fixtures

#### For unittest.TestCase classes:
```python
class TestMyClass(unittest.TestCase):
    def setUp(self):
        # Apply fixtures manually
        self.container = MagicMock()
        self.patcher_get_container = patch('module.get_container', return_value=self.container)
        self.mock_get_container = self.patcher_get_container.start()
        
    def tearDown(self):
        self.patcher_get_container.stop()
```

#### For pytest-style classes:
```python
@pytest.mark.usefixtures('mock_app_container_base', 'mock_file_operations_safe')
class TestMyClass:
    def test_something(self):
        # Fixtures are automatically applied
        pass
```

### Migration from Individual Patches

#### Before:
```python
@patch('utilities.utils.get_container', return_value=MagicMock())
@patch('os.path.exists')
@patch('os.path.expandvars')
@patch('os.path.expanduser')
def test_something(self, mock_expanduser, mock_expandvars, mock_exists, mock_container):
    mock_container.aio_folder = "/test/aio"
    mock_container.system = "Linux"
    mock_expanduser.return_value = "/test/data"
    mock_expandvars.return_value = "/test/data"
```

#### After:
```python
@pytest.mark.usefixtures('utils_container_setup')
def test_something(self):
    # Container and file operations are already mocked
    pass
```

## Benefits Achieved

1. **Reduced Code Duplication**: Eliminated repetitive mock setup across 15+ test files
2. **Improved Maintainability**: Changes to common mock patterns only need to be made in one place
3. **Better Test Isolation**: Centralized fixtures ensure consistent mock behavior
4. **Faster Test Execution**: Reduced overhead from creating multiple mock objects
5. **Enhanced Readability**: Test methods focus on testing logic rather than mock setup

## Remaining Work

### Phase 2: Reduce Redundant Basic Function Mocking
- [ ] Apply centralized fixtures to test_utils.py
- [ ] Apply centralized fixtures to test_blocknet_handler.py
- [ ] Apply centralized fixtures to test_xlite_handler.py
- [ ] Apply centralized fixtures to test_base_binutil.py

### Phase 3: Improve Test Organization
- [ ] Create test-specific mock configurations
- [ ] Group tests by mocking strategy
- [ ] Add more specialized fixtures for common scenarios

### Phase 4: Strategic Refactoring Implementation
- [ ] Systematic application of centralized fixtures across all test files
- [ ] Replace excessive individual patches with fixture usage
- [ ] Optimize test setup methods

### Phase 5: Validation and Safety Checks
- [ ] Run test suite after each major change
- [ ] Check for regressions and coverage loss
- [ ] Validate test behavior consistency

### Phase 6: Maintenance and Documentation
- [ ] Update testing guidelines with new patterns
- [ ] Create examples for common test scenarios
- [ ] Establish review process for new test additions

## Best Practices

1. **Use Real Implementations Where Safe**: Prefer real file operations in integration tests
2. **Mock Only What's Necessary**: Avoid over-mocking simple objects and functions
3. **Keep Fixtures Focused**: Each fixture should have a single, clear purpose
4. **Document Fixture Usage**: Add clear docstrings explaining when and how to use each fixture
5. **Test Your Fixtures**: Ensure fixtures work correctly and don't break existing tests

### Fixture Stacking Rules

Several centralized fixtures patch process-wide targets. Never stack multiple patches of the same target in one test - behavior then depends on fixture nesting order and is very hard to debug.

| Broad target | Patched by |
|---|---|
| `os.path.exists` | `mock_file_operations_safe`, `mock_targeted_file_ops`, `utils_container_setup*`, `utils_test_setup*` |
| `subprocess.Popen` | `unit_test_mocks` |
| `psutil.Process` | `unit_test_mocks` |

Rules:

1. **One source of truth per target per test**: pick a single fixture (or a single test-level patch) for each broad target; do not combine the fixtures listed above with each other or with additional `@patch` decorators of the same targets.
2. **Prefer targeted over broad**: when a test only needs specific paths, use `mock_targeted_file_ops` or a narrow side effect instead of blanket `os.path.exists` mocking.
3. **Watch inheritance**: `utils_container_setup_custom_exists` also patches `os.rename`; `blocknet_handler_setup`/`xlite_handler_setup` already include `unit_test_mocks`-style patches - do not re-add them at test level.
4. When adding new fixtures that patch these targets, update this table.

## Performance Metrics

- **Before**: 100+ patch() calls across test files
- **After**: Reduced to centralized fixtures with targeted patching
- **Expected Reduction**: 30-40% reduction in mock setup code
- **Test Performance**: Improved through reduced mock object creation overhead

## Monitoring and Maintenance

1. **Regular Review**: Periodically review fixture usage for redundancy
2. **Usage Analytics**: Track which fixtures are most/least used
3. **Continuous Improvement**: Regularly add new fixtures as common patterns emerge
4. **Community Feedback**: Gather feedback from developers on fixture usability