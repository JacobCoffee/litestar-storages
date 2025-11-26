# litestar-storages

Async file storage abstraction library for Litestar.

## Features

- **Async-native**: Built from the ground up for async/await
- **Type-safe**: Full typing support with Protocol-based design
- **Modular**: Optional backend dependencies via extras
- **Litestar Integration**: First-class plugin support with dependency injection

## Installation

```bash
# Core library (includes MemoryStorage only)
pip install litestar-storages

# With filesystem support
pip install litestar-storages[filesystem]

# With S3 support
pip install litestar-storages[s3]

# All backends
pip install litestar-storages[all]
```

## Quick Start

### Memory Storage (for testing)

```python
from litestar_storages import MemoryStorage

storage = MemoryStorage()

# Store a file
stored = await storage.put("test.txt", b"hello world", content_type="text/plain")

# Retrieve it
data = await storage.get_bytes("test.txt")
print(data.decode())  # "hello world"

# Get a URL
url = await storage.url("test.txt")  # "memory://test.txt"
```

### Filesystem Storage

```python
from pathlib import Path
from litestar_storages import FileSystemStorage, FileSystemConfig

storage = FileSystemStorage(
    config=FileSystemConfig(
        path=Path("/var/uploads"),
        base_url="https://cdn.example.com/uploads",
    )
)

await storage.put("images/photo.jpg", image_data)
url = await storage.url("images/photo.jpg")
# Returns: https://cdn.example.com/uploads/images/photo.jpg
```

### S3 Storage

```python
from litestar_storages import S3Storage, S3Config

# AWS S3
storage = S3Storage(
    config=S3Config(
        bucket="my-bucket",
        region="us-east-1",
    )
)

# Cloudflare R2
storage = S3Storage(
    config=S3Config(
        bucket="my-bucket",
        endpoint_url="https://account.r2.cloudflarestorage.com",
        access_key_id="...",
        secret_access_key="...",
    )
)

# Upload file
stored = await storage.put("uploads/file.pdf", file_data, content_type="application/pdf")

# Generate presigned URL (expires in 1 hour by default)
url = await storage.url("uploads/file.pdf")
```

## Storage Protocol

All backends implement the `Storage` protocol:

```python
async def put(key: str, data: bytes | AsyncIterator[bytes], *, content_type: str | None, metadata: dict[str, str] | None) -> StoredFile
async def get(key: str) -> AsyncIterator[bytes]
async def get_bytes(key: str) -> bytes
async def delete(key: str) -> None
async def exists(key: str) -> bool
async def list(prefix: str = "", *, limit: int | None = None) -> AsyncIterator[StoredFile]
async def url(key: str, *, expires_in: timedelta | None = None) -> str
async def copy(source: str, destination: str) -> StoredFile
async def move(source: str, destination: str) -> StoredFile
async def info(key: str) -> StoredFile
```

## Backends

### Implemented

- **MemoryStorage**: In-memory storage for testing (no external dependencies)
- **FileSystemStorage**: Local filesystem with aiofiles (requires `aiofiles`)
- **S3Storage**: AWS S3 and S3-compatible services (requires `aioboto3`)

### Planned

- **GCSStorage**: Google Cloud Storage
- **AzureStorage**: Azure Blob Storage

## Security Features

### Path Traversal Prevention (FileSystemStorage)

The filesystem backend sanitizes all keys to prevent directory traversal attacks:

```python
storage.put("../../etc/passwd", data)  # Safe: becomes "etc/passwd"
```

### Presigned URLs (S3Storage)

Generate time-limited URLs for secure file access:

```python
from datetime import timedelta

url = await storage.url("private/file.pdf", expires_in=timedelta(minutes=15))
```

## Development

```bash
# Clone repository
git clone https://github.com/JacobCoffee/litestar-storages.git
cd litestar-storages

# Install with development dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Run linting
uv run ruff check src tests
uv run mypy src
```

## License

MIT License - see LICENSE file for details.

## Credits

Built for the [Litestar](https://litestar.dev) framework.
