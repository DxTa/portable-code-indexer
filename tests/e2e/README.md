# sia-code E2E Multi-Language Test Suite

End-to-end tests that verify sia-code functionality from a user's perspective across 10 programming language repositories.

## Overview

This test suite validates sia-code's complete feature set by:
- Cloning real-world repositories for each supported language
- Running all sia-code commands (init, index, search, research, status, compact)
- Verifying outputs match expected behavior
- Testing on actual production codebases (not synthetic test data)

## Test Matrix

| Language | Repository | Stars | Test File |
|----------|-----------|-------|-----------|
| Python | [psf/requests](https://github.com/psf/requests) | 54k | `test_python_e2e.py` |
| JavaScript | [expressjs/express](https://github.com/expressjs/express) | 69k | `test_javascript_e2e.py` |
| TypeScript | [denoland/deno](https://github.com/denoland/deno) | 100k+ | `test_typescript_e2e.py` |
| Go | [gin-gonic/gin](https://github.com/gin-gonic/gin) | 88k | `test_go_e2e.py` |
| Rust | [tokio-rs/tokio](https://github.com/tokio-rs/tokio) | 31k | `test_rust_e2e.py` |
| Java | [mockito/mockito](https://github.com/mockito/mockito) | 15k | `test_java_e2e.py` |
| C++ | [nlohmann/json](https://github.com/nlohmann/json) | 49k | `test_cpp_e2e.py` |
| C# | [dotnet/aspnetcore](https://github.com/dotnet/aspnetcore) | 38k | `test_csharp_e2e.py` |
| Ruby | [sinatra/sinatra](https://github.com/sinatra/sinatra) | 12k | `test_ruby_e2e.py` |
| PHP | [slimphp/Slim](https://github.com/slimphp/Slim) | 12k | `test_php_e2e.py` |

## Test Coverage

Each language test file contains **22 comprehensive tests** covering:

### 1. Initialization (3 tests)
- Creates `.sia-code` directory
- Generates valid `config.json`
- Creates `index.mv2` file

### 2. Indexing (5 tests)
- Full indexing completes successfully
- Reports file and chunk counts
- Skips excluded patterns (`.git`, `node_modules`)
- `--clean` rebuilds from scratch
- `--update` only processes changed files

### 3. Search - Lexical (4 tests)
- Finds language-specific keywords
- Finds known symbols in repository
- Returns correct file paths
- Respects `-k/--limit` parameter

### 4. Search - Output Formats (3 tests)
- `--format json` produces valid JSON
- `--format table` renders formatted output
- `--format csv` produces valid CSV

### 5. Research (3 tests)
- Multi-hop research finds related code
- Respects `--hops` parameter
- `--graph` shows code relationships

### 6. Status & Maintenance (4 tests)
- Status shows index information
- Status displays chunk metrics
- Compact handles healthy index
- `--force` always runs compaction

**Total: 220 E2E tests across 10 language jobs**

## Running Tests

### Locally (Single Language)

Test Python repository:
```bash
# Set environment variables
export E2E_REPO_URL=https://github.com/psf/requests
export E2E_LANGUAGE=python
export E2E_KEYWORD="def"
export E2E_SYMBOL="Session"

# Run tests
pytest tests/e2e/test_python_e2e.py -v
```

Or use local repo:
```bash
# Clone repository first
git clone --depth 1 https://github.com/psf/requests target-repo

# Point to local clone
export E2E_REPO_PATH=target-repo
pytest tests/e2e/test_python_e2e.py -v
```

### Locally (All Languages)

**Warning:** This will clone 10 repositories (~500MB total) and take 30+ minutes.

```bash
# Run all E2E tests sequentially
pytest tests/e2e/ -v --timeout=600
```

### GitHub Actions

Tests run automatically on:
- Push to `main` or `develop`
- Pull requests to `main`
- Manual workflow dispatch

View results:
1. Go to Actions tab
2. Select "E2E Multi-Language Tests" workflow
3. View matrix of 10 parallel jobs

Each job runs independently in ~5 minutes (total wall time: ~5 min with parallelization).

## Sparse Checkout Strategy

Large repositories use sparse checkout to reduce clone size and CI time:

```yaml
# Example: TypeScript (deno)
sparse_paths: "cli/js cli/tsc"
```

This clones only specific directories, reducing download from 500MB to <50MB.

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `E2E_REPO_URL` | Repository URL to clone | `https://github.com/psf/requests` |
| `E2E_REPO_PATH` | Local repository path (overrides URL) | `./target-repo` |
| `E2E_SPARSE_PATHS` | Sparse checkout directories | `"cli/js cli/tsc"` |
| `E2E_LANGUAGE` | Language being tested | `python` |
| `E2E_KEYWORD` | Expected language keyword | `def` |
| `E2E_SYMBOL` | Known symbol in repo | `Session` |

## Architecture

### Fixtures (`conftest.py`)

Session-scoped fixtures ensure efficient testing:
- `target_repo`: Clones repo once per session
- `initialized_repo`: Runs `sia-code init` once
- `indexed_repo`: Runs `sia-code index` once

All 22 tests share the same indexed repository, making execution fast.

### Base Test Class (`base_e2e_test.py`)

Provides common utilities:
- `run_cli()`: Execute sia-code commands
- `search_json()`: Run search and parse JSON output
- `get_result_symbols()`: Extract symbols from results
- `assert_contains_language_extension()`: Verify file types

Language-specific subclasses set:
- `LANGUAGE`: Language identifier
- `EXPECTED_KEYWORD`: Language keyword (e.g., `def`, `func`, `class`)
- `EXPECTED_SYMBOL`: Known symbol in repository

### Test Files

Each `test_{language}_e2e.py`:
- Inherits from language-specific base class
- Implements 22 standard tests
- Customizes search terms for the target repository

## Adding New Language Tests

1. Create new base class in `base_e2e_test.py`:
```python
class NewLangE2ETest(BaseE2ETest):
    LANGUAGE = "newlang"
    EXPECTED_KEYWORD = "keyword"
```

2. Create test file `test_newlang_e2e.py`:
```python
from .base_e2e_test import NewLangE2ETest

class TestNewLangE2E(NewLangE2ETest):
    EXPECTED_SYMBOL = "MainClass"
    # Implement 22 test methods
```

3. Add to GitHub Actions matrix:
```yaml
- language: newlang
  repo_url: https://github.com/org/repo
  sparse_paths: ""
  keyword: "keyword"
  symbol: "MainClass"
  test_file: test_newlang_e2e.py
```

## Troubleshooting

### Test Timeout
Increase pytest timeout:
```bash
pytest tests/e2e/test_java_e2e.py --timeout=900
```

### Indexing Fails
Check sia-code installation:
```bash
sia-code --version
sia-code init --help
```

### No Results Found
Repository may not contain expected symbols. Check:
```bash
cd target-repo
grep -r "ExpectedSymbol" . | head
```

### GitHub Actions Failure
Download artifacts:
1. Go to failed workflow run
2. Scroll to "Artifacts"  
3. Download `debug-index-{language}`

## Performance Metrics

Expected execution times (per language):

| Stage | Time |
|-------|------|
| Clone repo | 10-60s |
| sia-code init | 1-2s |
| sia-code index | 30-180s |
| Search tests | 5-10s |
| Research tests | 10-30s |
| Status tests | 1-2s |
| **Total** | **~3-5 min** |

## Known Limitations

1. **Large repositories** (>100MB) use sparse checkout
2. **Network-dependent**: Tests require internet to clone repos
3. **Time-consuming**: Full suite takes 30+ min locally (5 min in CI with parallelization)
4. **Disk space**: ~500MB for all repositories

## CI/CD Integration

Tests run in parallel matrix with 10 jobs:
- Each job tests one language independently
- Jobs can run simultaneously (5 min total wall time)
- Artifacts uploaded for debugging
- Summary report generated after all jobs complete

## Related Documentation

- [sia-code README](../../README.md)
- [GitHub Actions Workflow](../../.github/workflows/e2e-multi-language.yml)
- [Test Plan](~/.config/opencode/plans/dxta_ses_44c668505ffeXp7o8Pd652HFWf_task_plan.md)
