#!/bin/bash
# Local E2E testing script with embeddings enabled
# Tests both small (workflow) and larger (README) repos

set -e

# --- Configuration ---
E2E_DIR="${E2E_DIR:-/tmp/sia-code-e2e}"
OPENAI_API_KEY="${OPENAI_API_KEY:?Error: OPENAI_API_KEY not set. Export it before running.}"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Sia-Code E2E Local Testing ===${NC}"
echo "Test directory: $E2E_DIR"
echo ""

# --- Clone repositories ---
mkdir -p "$E2E_DIR"

echo -e "${YELLOW}Cloning test repositories...${NC}"

# Small repos (from workflow)
if [ ! -d "$E2E_DIR/click" ]; then
  echo "  Cloning pallets/click (Python)..."
  git clone --depth 1 --filter=blob:none https://github.com/pallets/click "$E2E_DIR/click"
else
  echo "  ✓ click already cloned"
fi

if [ ! -d "$E2E_DIR/p-queue" ]; then
  echo "  Cloning sindresorhus/p-queue (TypeScript)..."
  git clone --depth 1 --filter=blob:none https://github.com/sindresorhus/p-queue "$E2E_DIR/p-queue"
else
  echo "  ✓ p-queue already cloned"
fi

# Larger repos (from README) - optional
if [ "${CLONE_LARGE_REPOS:-false}" = "true" ]; then
  if [ ! -d "$E2E_DIR/requests" ]; then
    echo "  Cloning psf/requests (Python - large)..."
    git clone --depth 1 https://github.com/psf/requests "$E2E_DIR/requests"
  else
    echo "  ✓ requests already cloned"
  fi
fi

echo ""
echo -e "${GREEN}✓ Repositories ready${NC}"
echo ""

# --- Run tests ---
cd /home/dxta/dev/portable-code-index/pci

# Activate venv if exists
if [ -f ".venv/bin/activate" ]; then
  source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

echo -e "${YELLOW}=== Running Python E2E Tests (click) ===${NC}"
export E2E_REPO_PATH="$E2E_DIR/click"
export E2E_LANGUAGE=python
export E2E_KEYWORD="def"
export E2E_SYMBOL="Command"
pytest tests/e2e/test_python_e2e.py -v --timeout=600 || {
  echo -e "${RED}Python E2E tests failed${NC}"
  exit 1
}

echo ""
echo -e "${YELLOW}=== Running TypeScript E2E Tests (p-queue) ===${NC}"
export E2E_REPO_PATH="$E2E_DIR/p-queue"
export E2E_LANGUAGE=typescript
export E2E_KEYWORD="function"
export E2E_SYMBOL="PQueue"
pytest tests/e2e/test_typescript_e2e.py -v --timeout=600 || {
  echo -e "${RED}TypeScript E2E tests failed${NC}"
  exit 1
}

# Run larger repo tests if requested
if [ "${CLONE_LARGE_REPOS:-false}" = "true" ]; then
  echo ""
  echo -e "${YELLOW}=== Running Python E2E Tests (requests - large) ===${NC}"
  export E2E_REPO_PATH="$E2E_DIR/requests"
  export E2E_LANGUAGE=python
  export E2E_KEYWORD="def"
  export E2E_SYMBOL="Session"
  pytest tests/e2e/test_python_e2e.py -v --timeout=900 || {
    echo -e "${RED}Requests E2E tests failed${NC}"
    exit 1
  }
fi

echo ""
echo -e "${GREEN}=== All E2E Tests Passed! ===${NC}"
echo ""
echo "Next steps:"
echo "  1. Run semantic quality tests: pytest tests/e2e/test_semantic_quality.py -v"
echo "  2. Run performance benchmarks: pytest tests/e2e/test_performance_benchmarks.py -v"
echo "  3. Run full suite with coverage: pytest tests/ --cov=sia_code --cov-report=html"
