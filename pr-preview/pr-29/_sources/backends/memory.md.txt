# Memory Storage

The `MemoryStorage` backend stores files entirely in memory. It's designed for testing and development scenarios where you need a functional storage backend without external dependencies.

## When to Use Memory Storage

**Ideal for:**

- Unit and integration tests
- Development environments
- Quick prototyping
- CI/CD pipelines without external services

**Not suitable for:**

- Production deployments
- Persistent storage requirements
- Multi-process applications
- Large file storage

## Configuration

### MemoryConfig Options

```python
from litestar_storages import MemoryStorage, MemoryConfig

config = MemoryConfig(
    max_size=None,  # Optional: maximum total bytes to store
)

storage = MemoryStorage(config)

# Or use defaults (no size limit)
storage = MemoryStorage()
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_size` | `int \| None` | `None` | Maximum total bytes across all files (None = unlimited) |

## Basic Usage

```python
from litestar_storages import MemoryStorage

storage = MemoryStorage()

# Store a file
result = await storage.put(
    "test.txt",
    b"Hello, World!",
    content_type="text/plain",
)
print(f"Stored: {result.key}, size: {result.size}")

# Check existence
exists = await storage.exists("test.txt")
assert exists is True

# Retrieve the file
content = await storage.get_bytes("test.txt")
assert content == b"Hello, World!"

# List files
async for file in storage.list():
    print(f"{file.key}: {file.size} bytes")

# Delete
await storage.delete("test.txt")
assert await storage.exists("test.txt") is False
```

## Testing Patterns

### Pytest Fixtures

```python
import pytest
from litestar_storages import MemoryStorage


@pytest.fixture
def storage():
    """Provide a fresh memory storage for each test."""
    return MemoryStorage()


async def test_file_upload(storage):
    """Test file upload functionality."""
    result = await storage.put("document.pdf", b"PDF content")

    assert result.key == "document.pdf"
    assert result.size == 11
    assert await storage.exists("document.pdf")


async def test_file_not_found(storage):
    """Test handling of missing files."""
    from litestar_storages import FileNotFoundError

    with pytest.raises(FileNotFoundError):
        await storage.get_bytes("nonexistent.txt")
```

### Testing Litestar Routes

```python
import pytest
from litestar.testing import AsyncTestClient
from litestar import Litestar, post
from litestar.datastructures import UploadFile
from litestar_storages import Storage, StoredFile, MemoryStorage, StoragePlugin


@post("/upload")
async def upload(data: UploadFile, storage: Storage) -> StoredFile:
    content = await data.read()
    return await storage.put(data.filename, content)


@pytest.fixture
def app():
    """Create test application with memory storage."""
    return Litestar(
        route_handlers=[upload],
        plugins=[StoragePlugin(MemoryStorage())],
    )


async def test_upload_endpoint(app):
    """Test the upload endpoint."""
    async with AsyncTestClient(app) as client:
        response = await client.post(
            "/upload",
            files={"data": ("test.txt", b"Hello!", "text/plain")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["key"] == "test.txt"
        assert data["size"] == 6
```

### Mocking Cloud Backends

Replace cloud backends with memory storage in tests:

```python
import pytest
from unittest.mock import patch
from litestar_storages import MemoryStorage


@pytest.fixture
def mock_s3_storage():
    """Replace S3 storage with memory storage for testing."""
    storage = MemoryStorage()
    # Pre-populate with test data if needed
    return storage


async def test_with_mock_storage(mock_s3_storage):
    """Test code that normally uses S3."""
    # Your test can now use mock_s3_storage
    await mock_s3_storage.put("test.txt", b"test data")

    # Test your business logic
    content = await mock_s3_storage.get_bytes("test.txt")
    assert content == b"test data"
```

### Factory Pattern for Test Flexibility

```python
import os
from litestar_storages import Storage, MemoryStorage, S3Storage, S3Config


def create_storage() -> Storage:
    """Create storage based on environment."""
    if os.environ.get("USE_REAL_S3"):
        return S3Storage(S3Config(bucket=os.environ["TEST_BUCKET"]))
    return MemoryStorage()


# In tests
storage = create_storage()  # Uses MemoryStorage unless USE_REAL_S3 is set
```

## Size Limits

Prevent memory exhaustion in development:

```python
from litestar_storages import MemoryStorage, MemoryConfig, StorageError

# Limit to 10MB total storage
storage = MemoryStorage(
    config=MemoryConfig(max_size=10 * 1024 * 1024)
)

# This will work
await storage.put("small.txt", b"x" * 1000)

# This will raise an error if total exceeds 10MB
try:
    await storage.put("large.bin", b"x" * 20_000_000)
except StorageError as e:
    print(f"Storage limit exceeded: {e}")
```

## URL Generation

Memory storage generates pseudo-URLs for compatibility:

```python
storage = MemoryStorage()
await storage.put("test.txt", b"content")

url = await storage.url("test.txt")
# Returns: "memory://test.txt"

# With expiration (ignored, but API-compatible)
url = await storage.url("test.txt", expires_in=timedelta(hours=1))
# Still returns: "memory://test.txt"
```

These URLs are not functional for HTTP access but maintain API compatibility with other backends.

## Limitations

### No Persistence

Data is lost when the process exits:

```python
storage = MemoryStorage()
await storage.put("important.txt", b"data")

# If the process restarts, the file is gone
# There is no way to recover it
```

### Single Process Only

Memory storage is not shared between processes:

```python
# Process 1
storage = MemoryStorage()
await storage.put("shared.txt", b"data")

# Process 2 - different MemoryStorage instance
storage2 = MemoryStorage()
await storage2.exists("shared.txt")  # False - separate memory space
```

For multi-process testing, use a shared backend like MinIO or a temporary filesystem.

### Memory Consumption

All file data is held in memory:

```python
storage = MemoryStorage()

# This consumes 100MB of RAM
await storage.put("large.bin", b"x" * 100_000_000)

# Use max_size to prevent runaway memory usage
storage = MemoryStorage(MemoryConfig(max_size=50 * 1024 * 1024))
```

### No Real URLs

The `url()` method returns non-functional `memory://` URLs:

```python
url = await storage.url("file.txt")
# Returns "memory://file.txt" - cannot be used for HTTP access
```

## Comparison with Other Backends

| Feature | MemoryStorage | FileSystemStorage | S3Storage |
|---------|---------------|-------------------|-----------|
| Persistence | No | Yes | Yes |
| Setup required | None | Directory path | Bucket + credentials |
| Multi-process | No | Yes | Yes |
| Speed | Fastest | Fast | Network-dependent |
| Real URLs | No | With base_url | Yes (presigned) |
| Use case | Testing | Single-server | Production |

## Next Steps

- Learn about [FileSystem storage](filesystem.md) for persistent local storage
- Set up [S3 storage](s3.md) for production deployments
- Create [custom backends](../advanced/custom-backends.md) for specialized needs
