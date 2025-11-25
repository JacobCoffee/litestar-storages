# litestar-storages

Welcome to litestar-storages, an async-first file storage abstraction library for [Litestar](https://litestar.dev/).

## What is litestar-storages?

litestar-storages provides a unified, async-native interface for storing and retrieving files across multiple storage backends. Whether you need to store user uploads on the local filesystem, serve media from AWS S3, or use Cloudflare R2 for edge distribution, litestar-storages gives you a consistent API that works the same way everywhere.

```python
from litestar_storages import S3Storage, S3Config

storage = S3Storage(S3Config(bucket="my-uploads"))

# Store a file
await storage.put("photos/vacation.jpg", image_data)

# Get a presigned URL
url = await storage.url("photos/vacation.jpg", expires_in=timedelta(hours=1))
```

## Key Features

### Async-Native Design

Built from the ground up for Python's async/await paradigm. Unlike django-storages (sync) or fastapi-storages (sync despite the name), every operation in litestar-storages is truly asynchronous.

### Multiple Storage Backends

- **FileSystemStorage**: Local filesystem storage with optional URL generation
- **S3Storage**: Amazon S3 and S3-compatible services (Cloudflare R2, DigitalOcean Spaces, MinIO, Backblaze B2)
- **GCSStorage**: Google Cloud Storage with signed URLs and ADC support
- **AzureStorage**: Azure Blob Storage with SAS URLs and managed identity
- **MemoryStorage**: In-memory storage for testing and development

### First-Class Litestar Integration

The `StoragePlugin` provides seamless integration with Litestar applications:

- **Dependency injection**: Storage instances injected directly into route handlers
- **Lifespan management**: Automatic connection cleanup on application shutdown
- **Multiple storages**: Named storages for different use cases (uploads, images, documents)

### Type-Safe Protocol Design

A well-defined `Storage` protocol ensures all backends behave consistently:

```python
@runtime_checkable
class Storage(Protocol):
    async def put(self, key: str, data: bytes, ...) -> StoredFile: ...
    async def get(self, key: str) -> AsyncIterator[bytes]: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
    async def list(self, prefix: str = "") -> AsyncIterator[StoredFile]: ...
    async def url(self, key: str, *, expires_in: timedelta | None = None) -> str: ...
```

### Streaming Support

Handle large files efficiently without loading them entirely into memory:

```python
# Stream download
async for chunk in storage.get("large-file.zip"):
    await response.write(chunk)

# Stream upload from async iterator
await storage.put("large-file.zip", async_chunk_generator())
```

## Comparison with Litestar Stores

Litestar includes built-in [stores](https://docs.litestar.dev/2/usage/stores.html) for key-value data. These serve a **different purpose** than litestar-storages:

| Aspect | litestar-storages | Litestar Stores |
|--------|-------------------|-----------------|
| **Purpose** | File storage (uploads, media assets) | Key-value data (caching, sessions) |
| **Data type** | Binary files with metadata | Serialized values with TTL |
| **Typical use** | User uploads, CDN assets, documents | Sessions, rate limiting, caching |
| **Backends** | FileSystem, S3, GCS, Azure, Memory | Memory, File, Redis, Valkey |
| **TTL support** | No (files are persistent) | Yes (automatic expiration) |
| **Metadata** | Yes (content-type, size, custom) | No |
| **Presigned URLs** | Yes (for cloud backends) | No |

**Use litestar-storages when you need to:**
- Accept file uploads from users
- Store and serve media assets (images, videos, documents)
- Generate secure download URLs
- Manage files across cloud providers

**Use Litestar Stores when you need to:**
- Cache computed values
- Store session data
- Implement rate limiting
- Store ephemeral data with automatic expiration

## Documentation Contents

```{toctree}
:maxdepth: 2
:caption: Getting Started

getting-started
examples
```

```{toctree}
:maxdepth: 2
:caption: Storage Backends

backends/filesystem
backends/s3
backends/gcs
backends/azure
backends/memory
```

```{toctree}
:maxdepth: 2
:caption: Advanced Topics

advanced/retry
advanced/multipart-uploads
advanced/progress-callbacks
advanced/custom-backends
```

```{toctree}
:maxdepth: 1
:caption: Reference

API Reference <api/index>
comparison
changelog
```

## Quick Links

- [Installation and Setup](getting-started.md)
- [Example Applications](examples.md)
- [FileSystem Backend](backends/filesystem.md)
- [S3 Backend](backends/s3.md) (AWS, R2, Spaces, MinIO)
- [GCS Backend](backends/gcs.md) (Google Cloud Storage)
- [Azure Backend](backends/azure.md) (Azure Blob Storage)
- [Retry Utilities](advanced/retry.md) (Exponential backoff and retry logic)
- [Multipart Uploads](advanced/multipart-uploads.md) (Large file handling)
- [Progress Callbacks](advanced/progress-callbacks.md) (Transfer progress tracking)
- [Creating Custom Backends](advanced/custom-backends.md)
- [Library Comparison](comparison.rst) (vs django-storages, fastapi-storages)
- [GitHub Repository](https://github.com/JacobCoffee/litestar-storages)
