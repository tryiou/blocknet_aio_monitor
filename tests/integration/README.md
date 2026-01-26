# Integration Tests

This directory contains integration tests for the Blocknet AIO Monitor application. Integration tests verify the
interaction between multiple components of the application, ensuring they work together correctly.

## Test Structure

```
tests/integration/
├── conftest.py              # Pytest configuration and fixtures
├── README.md                # This file
├── test_binary_workflow.py  # Binary download and installation tests
├── test_config_workflow.py  # Configuration management tests
├── test_gui_integration.py  # GUI component integration tests
├── test_process_management.py  # Process management tests
├── test_rpc_network.py      # RPC and network communication tests
├── fixtures/                # Test fixtures directory
├── mocks/                   # Mock services directory
└── helpers/                 # Helper utilities directory
```

## Test Categories

### 1. Binary Workflow Tests (`test_binary_workflow.py`)

Tests the complete workflow of downloading, extracting, and installing binaries:

- Blocknet Core download and installation
- Block-DX download and installation
- XLite download and installation
- Archive extraction (ZIP, TAR.GZ)
- File system operations
- Version validation
- Error handling

### 2. Configuration Workflow Tests (`test_config_workflow.py`)

Tests configuration management across components:

- Configuration initialization
- Reading and writing config files
- Blocknet configuration
- Block-DX configuration
- Config manager integration
- Path resolution
- Extra options handling
- Configuration backup and validation

### 3. Process Management Tests (`test_process_management.py`)

Tests process lifecycle management:

- Process start workflow
- Process monitoring
- Process stop workflow
- Process force kill
- Process timeout handling
- Process environment variables
- Process output capture
- PID file management
- State file management
- Signal handling
- Complete process lifecycle

### 4. GUI Integration Tests (`test_gui_integration.py`)

Tests GUI component integration:

- GUI initialization
- Frame manager integration
- Tooltip integration
- Binary manager integration
- Blocknet manager integration
- Block-DX manager integration
- XLite manager integration
- Button state management
- Event handling
- Async operations
- Error handling
- State machine
- Data flow

### 5. RPC Network Tests (`test_rpc_network.py`)

Tests RPC and network communication:

- RPC client initialization
- RPC request workflow
- RPC getbalance workflow
- RPC getinfo workflow
- RPC getblockcount workflow
- RPC error handling
- RPC authentication
- RPC session management
- RPC request format
- Network request workflow
- Network error handling
- File download workflow
- Multiple RPC calls
- RPC with parameters
- RPC response parsing

## Running Integration Tests

### Run All Integration Tests

```bash
# Run all integration tests
venv/bin/python -m pytest tests/integration/ -v

# Run with compact output
venv/bin/python -m pytest tests/integration/ -q

# Run with coverage
venv/bin/python -m pytest tests/integration/ --cov=. --cov-report=term-missing
```

### Run Specific Test Categories

```bash
# Run binary workflow tests
venv/bin/python -m pytest tests/integration/test_binary_workflow.py -v

# Run configuration workflow tests
venv/bin/python -m pytest tests/integration/test_config_workflow.py -v

# Run process management tests
venv/bin/python -m pytest tests/integration/test_process_management.py -v

# Run GUI integration tests
venv/bin/python -m pytest tests/integration/test_gui_integration.py -v

# Run RPC network tests
venv/bin/python -m pytest tests/integration/test_rpc_network.py -v
```

### Run Tests with Markers

```bash
# Run only integration tests (marked with @pytest.mark.integration)
venv/bin/python -m pytest tests/integration/ -m integration -v

# Run tests that require network access
venv/bin/python -m pytest tests/integration/ -m network -v

# Run GUI tests
venv/bin/python -m pytest tests/integration/ -m gui -v

# Run filesystem tests
venv/bin/python -m pytest tests/integration/ -m filesystem -v
```

### Run Tests with Specific Options

```bash
# Run with verbose output
venv/bin/python -m pytest tests/integration/ -v

# Run with detailed traceback
venv/bin/python -m pytest tests/integration/ --tb=long

# Run with coverage report
venv/bin/python -m pytest tests/integration/ --cov=. --cov-report=html

# Run with test durations
venv/bin/python -m pytest tests/integration/ --durations=10

# Run with xdist (parallel execution)
venv/bin/python -m pytest tests/integration/ -n auto
```

## Test Markers

Integration tests use the following pytest markers:

- `@pytest.mark.integration` - Marks tests as integration tests
- `@pytest.mark.network` - Marks tests that require network access
- `@pytest.mark.gui` - Marks tests that interact with GUI components
- `@pytest.mark.filesystem` - Marks tests that perform file operations

## Test Fixtures

The integration tests provide several fixtures in `conftest.py`:

### Environment Fixtures

- `temp_workspace` - Creates a temporary workspace for tests
- `mock_aio_folder` - Creates a mock AIO folder structure
- `mock_config_file` - Creates a mock configuration file

### Mock Service Fixtures

- `mock_github_api` - Mocks GitHub API responses
- `mock_rpc_server` - Mocks RPC server
- `mock_process_manager` - Mocks process management

### File System Fixtures

- `mock_binary_files` - Creates mock binary files
- `mock_config_files` - Creates mock configuration files

### GUI Fixtures

- `mock_gui_environment` - Mocks GUI environment

### Workflow Fixtures

- `complete_workflow_setup` - Complete workflow setup with all components

### Network Fixtures

- `mock_network_responses` - Mocks various network responses
- `mock_download_manager` - Mocks download manager

## Helper Utilities

The `helpers/test_helpers.py` file provides utility classes:

### IntegrationTestHelper

- `create_temp_workspace()` - Creates temporary workspace
- `cleanup_workspace()` - Cleans up workspace
- `create_mock_binary()` - Creates mock binary files
- `create_mock_config()` - Creates mock config files
- `mock_file_system_structure()` - Creates mock file system
- `create_test_data()` - Creates test data
- `patch_global_variables()` - Patches global variables
- `cleanup_patches()` - Cleans up patches
- `simulate_download_workflow()` - Simulates download workflow
- `verify_file_exists()` - Verifies file exists
- `verify_directory_exists()` - Verifies directory exists
- `verify_executable()` - Verifies file is executable

### WorkflowSimulator

- `simulate_blocknet_install_workflow()` - Simulates Blocknet installation
- `simulate_blockdx_install_workflow()` - Simulates Block-DX installation
- `simulate_xlite_install_workflow()` - Simulates XLite installation
- `simulate_process_lifecycle()` - Simulates process lifecycle

## Best Practices

### 1. Test Isolation

Each test should be independent and isolated. Use fixtures to set up and tear down test state.

### 2. Mock External Dependencies

Mock external services (GitHub, RPC servers) to ensure tests are reliable and fast.

### 3. Use Descriptive Test Names

Test names should clearly describe what is being tested and the expected behavior.

### 4. Test Error Scenarios

Include tests for error handling and edge cases.

### 5. Verify State Changes

After each operation, verify that the expected state changes occurred.

### 6. Clean Up Resources

Always clean up temporary files and resources in teardown methods.

### 7. Use Appropriate Markers

Use pytest markers to categorize tests and run specific test suites.

## Adding New Integration Tests

When adding new integration tests:

1. **Identify the workflow** - Determine what workflow you're testing
2. **Create test file** - Add a new test file in `tests/integration/`
3. **Add fixtures** - Add necessary fixtures in `conftest.py`
4. **Write tests** - Write clear, focused tests
5. **Add markers** - Use appropriate pytest markers
6. **Run tests** - Verify tests pass
7. **Update documentation** - Update this README if needed

## Example Test Pattern

```python
import pytest
from unittest.mock import patch, MagicMock

@pytest.mark.integration
class TestExampleWorkflow:
    """Example integration test class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Setup code here
    
    def teardown_method(self):
        """Clean up after tests."""
        # Cleanup code here
    
    def test_example_workflow(self):
        """Test example workflow."""
        # Test code here
        assert True
```

## Troubleshooting

### Tests Fail Due to Network Issues

- Some tests require network access (marked with `@pytest.mark.network`)
- Run network tests separately: `pytest tests/integration/ -m network`
- Mock network calls for offline testing

### Tests Fail Due to File Permissions

- Ensure test workspace has proper permissions
- Check file system operations in tests
- Use `chmod` to set appropriate permissions

### Tests Fail Due to Missing Dependencies

- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check for missing test dependencies

### Tests Run Slowly

- Use `pytest -n auto` for parallel execution
- Mock external services to speed up tests
- Use `--durations=10` to identify slow tests

## Contributing

When contributing integration tests:

1. Follow the existing test structure and patterns
2. Use appropriate fixtures and helpers
3. Write clear, descriptive test names
4. Include error scenarios
5. Update documentation
6. Run all tests before submitting

## License

This project is licensed under the MIT License - see the LICENSE file for details.
