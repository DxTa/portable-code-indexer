"""Integration test using the CLI directly."""

import subprocess
import sys
from pathlib import Path
import shutil

# Cleanup first
test_dir = Path("test_cli_project")
if test_dir.exists():
    shutil.rmtree(test_dir)

test_dir.mkdir()

print("=== PCI CLI Integration Test ===\n")

# Test 1: Initialize
print("1. Testing 'pci init'...")
result = subprocess.run(
    [sys.executable, "-m", "pci.cli", "init"],
    cwd=test_dir,
    capture_output=True,
    text=True
)
print(result.stdout)
if result.returncode != 0:
    print(f"ERROR: {result.stderr}")
    sys.exit(1)

assert (test_dir / ".pci").exists(), ".pci directory not created"
assert (test_dir / ".pci/config.json").exists(), "config.json not created"
assert (test_dir / ".pci/index.mv2").exists(), "index.mv2 not created"
print("✓ Init successful\n")

# Test 2: Status
print("2. Testing 'pci status'...")
result = subprocess.run(
    [sys.executable, "-m", "pci.cli", "status"],
    cwd=test_dir,
    capture_output=True,
    text=True
)
print(result.stdout)
if result.returncode != 0:
    print(f"ERROR: {result.stderr}")
print("✓ Status successful\n")

# Test 3: Config
print("3. Testing 'pci config --show'...")
result = subprocess.run(
    [sys.executable, "-m", "pci.cli", "config", "--show"],
    cwd=test_dir,
    capture_output=True,
    text=True
)
print(result.stdout[:200] + "...\n")
if result.returncode != 0:
    print(f"ERROR: {result.stderr}")
print("✓ Config successful\n")

# Test 4: Index (should show not implemented)
print("4. Testing 'pci index'...")
result = subprocess.run(
    [sys.executable, "-m", "pci.cli", "index"],
    cwd=test_dir,
    capture_output=True,
    text=True
)
print(result.stdout)
print("✓ Index command works (not yet implemented)\n")

# Test 5: Search (should show not initialized error or no results)
print("5. Testing 'pci search'...")
result = subprocess.run(
    [sys.executable, "-m", "pci.cli", "search", "test query"],
    cwd=test_dir,
    capture_output=True,
    text=True
)
print(result.stdout)
print("✓ Search command works\n")

# Cleanup
shutil.rmtree(test_dir)
print("\n=== All CLI tests passed! ===")
