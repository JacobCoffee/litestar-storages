# litestar-storages Test Suite

Comprehensive test suite for litestar-storages library with 3,657 lines of test code targeting >90% coverage.

## Test Structure

```
tests/
├── __init__.py                  # Package marker
├── conftest.py                  # Shared fixtures and configuration
├── test_protocol.py             # Protocol compliance tests
├── backends/
│   ├── __init__.py
│   ├── test_memory.py          # MemoryStorage tests
│   ├── test_filesystem.py      # FileSystemStorage tests
│   └── test_s3.py              # S3Storage tests
└── contrib/
    ├── __init__.py
    └── test_plugin.py           # StoragePlugin integration tests
```

## Test Categories

### 1. Protocol Compliance Tests (`test_protocol.py`)

Tests that run against ALL storage backends using the `any_storage` parametrized fixture.

**Classes:**
- `TestBasicOperations` - put, get, exists, delete operations
- `TestListingOperations` - file listing and prefix filtering
- `TestMetadataOperations` - metadata retrieval and file info
- `TestCopyMoveOperations` - copy and move operations
- `TestURLGeneration` - URL generation for file access
- `TestEdgeCases` - edge cases and error conditions
- `TestBinaryData` - binary data handling and large files

**Total Tests:** ~40 tests × 3 backends = 120 test executions

### 2. MemoryStorage Tests (`backends/test_memory.py`)

Backend-specific tests for in-memory storage.

**Classes:**
- `TestMemoryStorageBasics` - instance creation, isolation, persistence
- `TestMemorySizeLimits` - max_size enforcement and capacity management
- `TestMemoryStorageMetadata` - metadata handling and preservation
- `TestMemoryStorageEdgeCases` - overwrites, concurrency, ETag generation
- `TestMemoryStorageURL` - URL generation for memory backend
- `TestMemoryStorageListing` - listing order and consistency

**Total Tests:** ~30 tests

### 3. FileSystemStorage Tests (`backends/test_filesystem.py`)

Backend-specific tests for filesystem storage.

**Classes:**
- `TestFileSystemStorageBasics` - disk operations, directory creation
- `TestDirectoryCreation` - nested directories, concurrent creation
- `TestPathSanitization` - security: path traversal prevention, sanitization
- `TestFilePermissions` - file permissions and custom modes
- `TestURLGeneration` - URL generation with base_url
- `TestFileSystemCopyMove` - efficient filesystem operations
- `TestFileSystemListing` - directory structure and ordering
- `TestFileSystemMetadata` - content type detection, extended attributes
- `TestFileSystemEdgeCases` - Unicode filenames, symlinks, edge cases

**Total Tests:** ~40 tests

### 4. S3Storage Tests (`backends/test_s3.py`)

Backend-specific tests for S3-compatible storage using moto mocking.

**Classes:**
- `TestS3StorageBasics` - S3 client initialization, credentials
- `TestS3PresignedURLs` - presigned URL generation and expiration
- `TestS3PrefixHandling` - prefix namespacing and isolation
- `TestS3CustomEndpoint` - S3-compatible services (R2, MinIO, Spaces)
- `TestS3Metadata` - S3 user metadata and ETag handling
- `TestS3CopyMove` - server-side copy operations
- `TestS3Listing` - pagination and prefix filtering
- `TestS3Streaming` - streaming uploads and downloads
- `TestS3ErrorHandling` - error scenarios
- `TestS3Configuration` - configuration options
- `TestRealWorldScenarios` - multipart uploads, concurrency, CDN patterns

**Total Tests:** ~50 tests

### 5. StoragePlugin Tests (`contrib/test_plugin.py`)

Integration tests for Litestar plugin.

**Classes:**
- `TestStoragePluginBasics` - plugin registration and configuration
- `TestStorageDependencyInjection` - DI of storage instances
- `TestFileUploadController` - realistic upload/download workflows
- `TestControllerIntegration` - Controller class integration
- `TestMultipleStorageScenarios` - multi-storage patterns
- `TestPluginLifecycle` - lifecycle management

**Total Tests:** ~25 tests

## Running Tests

### Run All Tests
```bash
pytest tests/
```

### Run Protocol Compliance Tests Only
```bash
pytest tests/test_protocol.py
```

### Run Tests for Specific Backend
```bash
pytest tests/backends/test_memory.py
pytest tests/backends/test_filesystem.py
pytest tests/backends/test_s3.py
```

### Run Integration Tests Only
```bash
pytest tests/contrib/
```

### Run with Coverage
```bash
pytest tests/ --cov=litestar_storages --cov-report=html --cov-report=term-missing
```

### Run Specific Test Class
```bash
pytest tests/test_protocol.py::TestBasicOperations
```

### Run Specific Test
```bash
pytest tests/test_protocol.py::TestBasicOperations::test_put_and_get_bytes
```

### Run Tests by Marker
```bash
pytest tests/ -m unit          # Unit tests only
pytest tests/ -m integration   # Integration tests only
pytest tests/ -m slow          # Slow tests only
```

## Fixtures

### Storage Fixtures

**`memory_storage`** - Fresh MemoryStorage instance for each test
- Isolated in-memory storage
- No size limits
- Fast for unit tests

**`memory_storage_with_limit`** - MemoryStorage with 1MB size limit
- Tests max_size enforcement
- Capacity management

**`filesystem_storage`** - FileSystemStorage in temporary directory
- Uses pytest's `tmp_path`
- Auto-cleanup after test
- Default permissions (0o644)

**`filesystem_storage_with_base_url`** - FileSystemStorage with base URL
- Tests URL generation
- CDN-style URL formatting

**`s3_storage`** - S3Storage with mocked AWS backend
- Uses moto's `mock_aws`
- No real AWS credentials needed
- Fast local testing

**`s3_storage_with_prefix`** - S3Storage with key prefix
- Tests namespace isolation
- Multi-tenant scenarios

**`any_storage`** - Parametrized fixture yielding each backend
- **Critical fixture for protocol compliance**
- Tests run 3x (memory, filesystem, S3)
- Ensures consistent behavior

### Data Fixtures

**`sample_text_data`** - Small text data (33 bytes)
**`sample_binary_data`** - All byte values 0-255
**`large_data`** - 1MB of data for streaming tests
**`sample_metadata`** - Sample metadata dictionary
**`async_data_chunks`** - Factory for async iterators

### Litestar Fixtures

**`litestar_app`** - Basic Litestar application
**`litestar_test_client`** - Async test client for API testing

## Test Coverage Goals

- **Overall Coverage:** >90%
- **Unit Tests:** >95% coverage of backend logic
- **Integration Tests:** >80% coverage of plugin/API integration
- **Protocol Compliance:** 100% of protocol methods tested across all backends

## Test Patterns

### 1. Protocol Compliance Pattern
```python
async def test_feature(any_storage: Storage):
    """Test runs against ALL backends."""
    # Test logic here - will execute 3 times
```

### 2. Backend-Specific Pattern
```python
async def test_memory_feature(memory_storage: MemoryStorage):
    """Test specific to MemoryStorage."""
    # Test memory-specific behavior
```

### 3. Integration Pattern
```python
@pytest.mark.integration
async def test_litestar_integration():
    """Integration test with Litestar."""
    # Full application test
```

### 4. Mocking Pattern (S3)
```python
async def test_s3_feature(s3_storage: S3Storage):
    """S3 test with moto mocking."""
    # moto intercepts all boto3/aioboto3 calls
    # No real AWS access
```

## Key Test Features

### Security Testing
- Path traversal prevention (`../ attacks`)
- Absolute path sanitization
- Windows path separator handling
- Symlink security

### Edge Cases
- Empty files (0 bytes)
- Large files (1MB+)
- Unicode filenames
- Special characters in keys
- Concurrent operations
- Overwrite behavior

### Error Handling
- FileNotFoundError for missing files
- StorageError for capacity limits
- Proper exception messages
- Graceful degradation

### Performance Testing
- Streaming large files
- Concurrent uploads
- Memory efficiency
- Server-side operations (S3 copy)

## Continuous Integration

Tests are designed to run in CI/CD pipelines:
- No external dependencies (moto for S3)
- Fast execution (<30s for full suite)
- Isolated test data (tmp_path, in-memory)
- Parallel execution supported
- Deterministic results

## Writing New Tests

### For New Backends

1. Add backend fixture to `conftest.py`
2. Add backend to `any_storage` parametrize list
3. Create `tests/backends/test_<backend>.py`
4. Run protocol compliance tests - should pass automatically
5. Add backend-specific tests for unique features

### For New Features

1. Add protocol compliance test in `test_protocol.py` if feature is in protocol
2. Add backend-specific tests if needed
3. Add integration test in `contrib/test_plugin.py` if exposed via plugin
4. Ensure >90% coverage of new code

## Test Markers

- `@pytest.mark.unit` - Fast, isolated unit tests
- `@pytest.mark.integration` - Integration tests with Litestar
- `@pytest.mark.slow` - Tests taking >1 second
- `@pytest.mark.requires_network` - Tests requiring network access

## Dependencies

Test dependencies (in `pyproject.toml`):
- `pytest>=8.0.0` - Test framework
- `pytest-asyncio>=0.23.0` - Async test support
- `pytest-cov>=4.0.0` - Coverage reporting
- `moto[s3]>=5.0.0` - AWS S3 mocking
- `litestar>=2.0.0` - Framework integration testing

## Best Practices

1. **Isolation** - Each test is independent, no shared state
2. **Descriptive Names** - Test names describe what is being tested
3. **Documentation** - Docstrings explain what is verified
4. **Fast Execution** - Use in-memory and mocked backends
5. **Comprehensive Coverage** - Test happy path, edge cases, and errors
6. **Realistic Scenarios** - Integration tests mirror real usage
7. **Type Safety** - Full type hints for fixtures and test functions

## Future Test Additions

When implementing additional backends:
- `tests/backends/test_gcs.py` - Google Cloud Storage tests
- `tests/backends/test_azure.py` - Azure Blob Storage tests

When adding features:
- Multipart upload tests
- Progress callback tests
- Retry logic tests
- Connection pooling tests

---

**Total Test Count:** ~185 tests
**Total Lines of Code:** 3,657 lines
**Estimated Coverage:** >90%
**Execution Time:** <30 seconds

This test suite provides comprehensive validation of all storage backends and ensures consistent behavior across different storage providers.
