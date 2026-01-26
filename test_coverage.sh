
#!/bin/bash
# Run tests with coverage

echo "Running unit tests with coverage..."
venv/bin/coverage run -m pytest tests/unit/ -q

echo ""
echo "Running integration tests with coverage (excluding network tests)..."
venv/bin/coverage run -a -m pytest tests/integration/ -q -m "not network"

echo ""
echo "Generating coverage report..."
venv/bin/coverage report -m --include="blocknet_aio_monitor.py,gui/*.py,gui/**/*.py,utilities/*.py,utilities/**/*.py,widgets_strings.py"

echo ""
echo "To run all tests including network tests:"
echo "  venv/bin/pytest tests/ -v"
echo ""
echo "To run only unit tests:"
echo "  venv/bin/pytest tests/unit/ -v"
echo ""
echo "To run only integration tests:"
echo "  venv/bin/pytest tests/integration/ -v"
echo ""
echo "To run network tests (requires internet):"
echo "  venv/bin/pytest tests/integration/ -m network -v"