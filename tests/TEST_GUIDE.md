# Test Execution Guide

Complete guide for running, debugging, and maintaining the litestar-storages test suite.

## Quick Start

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage report
pytest --cov

# Run specific test file
pytest tests/test_protocol.py

# Run specific test class
pytest tests/test_protocol.py::TestBasicOperations

# Run specific test
pytest tests/test_protocol.py::TestBasicOperations::test_put_and_get_bytes
```

## Test Organization

### By Test Type

**Unit Tests** - Fast, isolated tests of individual components
```bash
pytest -m unit
```

**Integration Tests** - Tests with Litestar framework
```bash
pytest -m integration
```

**Slow Tests** - Tests taking >1 second
```bash
pytest -m slow
```

### By Backend

**Memory Backend**
```bash
pytest tests/backends/test_memory.py
```

**Filesystem Backend**
```bash
pytest tests/backends/test_filesystem.py
```

**S3 Backend**
```bash
pytest tests/backends/test_s3.py
```

### Protocol Compliance

**All Protocol Tests** (runs 3x per test - once per backend)
```bash
pytest tests/test_protocol.py
```

**Protocol Tests for Specific Backend**
```bash
# Memory only
pytest tests/test_protocol.py -k memory

# Filesystem only
pytest tests/test_protocol.py -k filesystem

# S3 only
pytest tests/test_protocol.py -k s3
```

## Coverage Reports

### Generate Coverage

**Terminal Report**
```bash
pytest --cov=litestar_storages --cov-report=term-missing
```

**HTML Report** (opens in browser)
```bash
pytest --cov=litestar_storages --cov-report=html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

**XML Report** (for CI/CD)
```bash
pytest --cov=litestar_storages --cov-report=xml
```

### Coverage Goals

- **Overall:** >90%
- **Core Protocol:** >95%
- **Backends:** >90%
- **Plugin:** >85%

### Check Coverage Threshold
```bash
# Fails if coverage < 90%
pytest --cov-fail-under=90
```

## Advanced Testing

### Parallel Execution

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel (4 workers)
pytest -n 4

# Auto-detect CPU count
pytest -n auto
```

### Verbose Output

```bash
# Very verbose
pytest -vv

# Show stdout/stderr even for passing tests
pytest -s

# Show local variables in traceback
pytest --showlocals
```

### Debugging

**Drop into debugger on failure**
```bash
pytest --pdb
```

**Drop into debugger at start of test**
```bash
pytest --trace
```

**Run only failed tests from last run**
```bash
pytest --lf  # last failed
pytest --ff  # failed first, then rest
```

**Step through test execution**
```python
# In test file
import pytest; pytest.set_trace()
```

### Filtering Tests

**By test name pattern**
```bash
# Run all upload tests
pytest -k upload

# Run all tests with "s3" in name
pytest -k s3

# Exclude slow tests
pytest -k "not slow"

# Complex expression
pytest -k "upload and not slow"
```

**By marker**
```bash
# Run only unit tests
pytest -m unit

# Run integration tests, exclude slow
pytest -m "integration and not slow"
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"

      - name: Run tests
        run: |
          pytest --cov --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

## Writing Tests

### Test Template

```python
"""Module docstring describing what's being tested."""

from __future__ import annotations

import pytest
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from litestar_storages import Storage


@pytest.mark.unit
class TestFeature:
    """Test suite for specific feature."""

    async def test_basic_case(self, any_storage: Storage) -> None:
        """
        Test basic functionality.

        Verifies:
        - What is being tested
        - Expected behavior
        - Edge cases covered
        """
        # Arrange
        data = b"test data"

        # Act
        result = await any_storage.put("test.txt", data)

        # Assert
        assert result.key == "test.txt"
        assert result.size == len(data)
```

### Best Practices

1. **Use Type Hints**
   ```python
   async def test_feature(self, storage: Storage) -> None:
   ```

2. **Descriptive Docstrings**
   ```python
   async def test_upload_with_metadata(self) -> None:
       """
       Test uploading file with custom metadata.

       Verifies:
       - Metadata is stored
       - Metadata is retrievable
       - Metadata persists across operations
       """
   ```

3. **Arrange-Act-Assert Pattern**
   ```python
   # Arrange
   data = b"test"
   key = "file.txt"

   # Act
   result = await storage.put(key, data)

   # Assert
   assert result.key == key
   ```

4. **Test Isolation**
   - Each test is independent
   - No shared state between tests
   - Use fresh fixtures

5. **Test One Thing**
   - Each test verifies one behavior
   - Keep tests focused and simple
   - Split complex scenarios into multiple tests

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Ensure package is installed in editable mode
pip install -e .
```

**Fixture Not Found**
```bash
# Check conftest.py is in tests/ directory
ls tests/conftest.py

# Verify fixture name matches
pytest --fixtures | grep storage
```

**Async Tests Not Running**
```bash
# Ensure pytest-asyncio is installed
pip install pytest-asyncio

# Check pytest.ini has asyncio_mode = auto
cat pytest.ini | grep asyncio_mode
```

**S3 Mock Not Working**
```bash
# Ensure moto is installed with S3 support
pip install "moto[s3]"

# Check fixture uses mock_aws decorator
# In conftest.py: @mock_aws
```

### Debug Output

**Show print statements**
```bash
pytest -s
```

**Show captured logs**
```bash
pytest --log-cli-level=DEBUG
```

**Show fixture setup/teardown**
```bash
pytest --setup-show
```

**Show why tests were selected/deselected**
```bash
pytest -v --collect-only
```

## Performance Optimization

### Identify Slow Tests

```bash
# Show slowest 10 tests
pytest --durations=10

# Show all test durations
pytest --durations=0
```

### Profile Tests

```bash
# Install pytest-profiling
pip install pytest-profiling

# Profile test execution
pytest --profile
```

### Optimize Fixtures

```python
# Use appropriate scope
@pytest.fixture(scope="session")  # Once per test session
@pytest.fixture(scope="module")   # Once per module
@pytest.fixture(scope="class")    # Once per class
@pytest.fixture(scope="function")  # Once per test (default)
```

## Test Data Management

### Using Fixtures

```python
# Use existing data fixtures
async def test_feature(self, sample_text_data: bytes):
    await storage.put("file.txt", sample_text_data)
```

### Creating Custom Fixtures

```python
# In conftest.py or test file
@pytest.fixture
def custom_data():
    """Custom test data fixture."""
    return {"key": "value"}
```

### Parametrized Tests

```python
@pytest.mark.parametrize("filename,expected", [
    ("test.txt", "text/plain"),
    ("image.jpg", "image/jpeg"),
    ("doc.pdf", "application/pdf"),
])
async def test_content_type(filename, expected):
    # Test runs 3 times with different parameters
    pass
```

## Reporting

### JUnit XML (for CI)
```bash
pytest --junitxml=junit.xml
```

### HTML Report
```bash
pip install pytest-html
pytest --html=report.html --self-contained-html
```

### JSON Report
```bash
pip install pytest-json-report
pytest --json-report --json-report-file=report.json
```

## Maintenance

### Update Test Dependencies

```bash
# Update all dev dependencies
pip install --upgrade -e ".[dev]"

# Check for outdated packages
pip list --outdated
```

### Check Test Quality

**Mutation Testing** (test the tests)
```bash
pip install mutmut
mutmut run
mutmut results
```

**Test Coverage Gaps**
```bash
# Find uncovered lines
pytest --cov --cov-report=term-missing
```

### Clean Up

```bash
# Remove coverage artifacts
rm -rf .coverage htmlcov coverage.xml

# Remove pytest cache
rm -rf .pytest_cache

# Remove Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
```

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [moto Documentation](https://docs.getmoto.org/)
- [Litestar Testing Guide](https://docs.litestar.dev/latest/usage/testing.html)

---

For questions or issues with tests, please open an issue on GitHub.
