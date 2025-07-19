#!/usr/bin/env python3
"""
Test runner script for Blocknet AIO Monitor.

This script provides a convenient way to run all tests or specific test modules.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a command and return the result."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def discover_tests(test_dir="tests"):
    """Discover all test files in the tests directory."""
    test_files = []
    test_path = Path(test_dir)

    if not test_path.exists():
        print(f"Test directory '{test_dir}' not found")
        return test_files

    for test_file in test_path.glob("test_*.py"):
        test_files.append(str(test_file))

    return sorted(test_files)


def run_all_tests(verbose=False, coverage=False):
    """Run all tests using pytest."""
    cmd = ["python", "-m", "pytest", "tests/"]

    if verbose:
        cmd.append("-v")

    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term-missing"])

    cmd_str = " ".join(cmd)
    print(f"Running: {cmd_str}")

    returncode, stdout, stderr = run_command(cmd_str)

    print("STDOUT:")
    print(stdout)
    if stderr:
        print("STDERR:")
        print(stderr)

    return returncode


def run_specific_test(test_file, verbose=False):
    """Run a specific test file."""
    if not os.path.exists(test_file):
        print(f"Test file '{test_file}' not found")
        return 1

    cmd = ["python", "-m", "pytest", test_file]
    if verbose:
        cmd.append("-v")

    cmd_str = " ".join(cmd)
    print(f"Running: {cmd_str}")

    returncode, stdout, stderr = run_command(cmd_str)

    print("STDOUT:")
    print(stdout)
    if stderr:
        print("STDERR:")
        print(stderr)

    return returncode


def run_unittest(test_file, verbose=False):
    """Run a specific test file using unittest."""
    if not os.path.exists(test_file):
        print(f"Test file '{test_file}' not found")
        return 1

    cmd = ["python", "-m", "unittest", test_file]
    if verbose:
        cmd.append("-v")

    cmd_str = " ".join(cmd)
    print(f"Running: {cmd_str}")

    returncode, stdout, stderr = run_command(cmd_str)

    print("STDOUT:")
    print(stdout)
    if stderr:
        print("STDERR:")
        print(stderr)

    return returncode


def list_tests():
    """List all available test files."""
    test_files = discover_tests()

    if not test_files:
        print("No test files found")
        return

    print("Available test files:")
    for i, test_file in enumerate(test_files, 1):
        print(f"{i:2d}. {test_file}")


def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description="Test runner for Blocknet AIO Monitor")

    parser.add_argument(
        "test_file",
        nargs="?",
        help="Specific test file to run (e.g., tests/test_main_gui.py)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "-c", "--coverage",
        action="store_true",
        help="Generate coverage report"
    )

    parser.add_argument(
        "-u", "--unittest",
        action="store_true",
        help="Use unittest instead of pytest"
    )

    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List all available test files"
    )

    parser.add_argument(
        "-a", "--all",
        action="store_true",
        help="Run all tests (default)"
    )

    args = parser.parse_args()

    # Change to project root directory
    project_root = Path(__file__).parent
    os.chdir(project_root)

    if args.list:
        list_tests()
        return 0

    if args.test_file:
        if args.unittest:
            return run_unittest(args.test_file, args.verbose)
        else:
            return run_specific_test(args.test_file, args.verbose)

    # Default: run all tests
    return run_all_tests(args.verbose, args.coverage)


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
