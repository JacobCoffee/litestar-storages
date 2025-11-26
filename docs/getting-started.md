# Getting Started

This guide covers installation, basic concepts, and your first steps with litestar-storages.

## Installation

### Base Package

The base package includes FileSystem and Memory backends. **No framework dependencies required**:

```bash
pip install litestar-storages
```

This gives you a fully functional async storage library that works with any Python async application.

### With Cloud Backends

Install optional dependencies for cloud storage support:

```bash
# S3 and S3-compatible services (AWS S3, Cloudflare R2, DigitalOcean Spaces, MinIO)
pip install litestar-storages[s3]

# Google Cloud Storage
pip install litestar-storages[gcs]

# Azure Blob Storage
pip install litestar-storages[azure]

# All cloud backends (no framework)
pip install litestar-storages[s3,gcs,azure]
```

### With Litestar Integration

For Litestar applications with dependency injection and plugin support:

```bash
# Base + Litestar integration
pip install litestar-storages[litestar]

# With specific cloud backend + Litestar
pip install litestar-storages[s3,litestar]

# Everything (all backends + Litestar)
pip install litestar-storages[all]
```

### Development Installation

For development with all testing tools:

```bash
pip install litestar-storages[dev]
```

## Basic Concepts

### The Storage Protocol

All storage backends implement the `Storage` protocol, which defines a consistent interface for file operations:

```python
from litestar_storages import Storage

# Core operations available on all backends:
await storage.put(key, data)        # Store a file
await storage.get(key)              # Stream file contents
await storage.get_bytes(key)        # Get entire file as bytes
await storage.delete(key)           # Delete a file
await storage.exists(key)           # Check if file exists
await storage.info(key)             # Get file metadata
await storage.list(prefix)          # List files
await storage.url(key)              # Generate access URL
await storage.copy(source, dest)    # Copy a file
await storage.move(source, dest)    # Move/rename a file
```

### StoredFile

The `StoredFile` dataclass represents metadata about a stored file:

```python
from litestar_storages import StoredFile

@dataclass(frozen=True, slots=True)
class StoredFile:
    key: str                              # Storage path/key
    size: int                             # File size in bytes
    content_type: str | None = None       # MIME type
    etag: str | None = None               # Entity tag (hash)
    last_modified: datetime | None = None # Last modification time
    metadata: dict[str, str] = field(default_factory=dict)  # Custom metadata
```

This is returned by operations like `put()`, `info()`, and `list()`:

```python
result = await storage.put("document.pdf", pdf_bytes, content_type="application/pdf")
print(f"Stored {result.key}: {result.size} bytes")
print(f"Content-Type: {result.content_type}")
```

### Keys (File Paths)

Files are identified by **keys**, which are path-like strings:

```python
# Simple key
await storage.put("readme.txt", data)

# Hierarchical keys (like directories)
await storage.put("users/123/avatar.jpg", image_data)
await storage.put("users/123/documents/resume.pdf", pdf_data)

# List with prefix to find related files
async for file in storage.list("users/123/"):
    print(file.key)
```

Keys are normalized for security:
- Backslashes are converted to forward slashes
- Leading slashes are removed
- Path traversal attempts (`..`) are blocked

## Plain Python Usage

litestar-storages works with any async Python code. No framework required.

### Basic Example

```python
import asyncio
from pathlib import Path
from litestar_storages import FileSystemStorage, FileSystemConfig

async def main():
    # Create storage with configuration
    storage = FileSystemStorage(
        config=FileSystemConfig(
            path=Path("./uploads"),    # Where to store files
            create_dirs=True,          # Create directory if missing
        )
    )

    # Store some data
    result = await storage.put(
        "hello.txt",
        b"Hello, litestar-storages!",
        content_type="text/plain",
    )
    print(f"Stored: {result.key} ({result.size} bytes)")

    # Check it exists
    exists = await storage.exists("hello.txt")
    print(f"File exists: {exists}")

    # Read it back
    content = await storage.get_bytes("hello.txt")
    print(f"Content: {content.decode()}")

    # Get metadata
    info = await storage.info("hello.txt")
    print(f"Last modified: {info.last_modified}")

    # List all files
    print("\nAll files:")
    async for file in storage.list():
        print(f"  - {file.key}: {file.size} bytes")

    # Clean up
    await storage.delete("hello.txt")
    print("\nFile deleted")

asyncio.run(main())
```

### Using with FastAPI

```python
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, UploadFile, Depends
from litestar_storages import FileSystemStorage, FileSystemConfig, Storage

# Create storage instance
storage = FileSystemStorage(
    FileSystemConfig(path=Path("./uploads"), create_dirs=True)
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing needed for filesystem
    yield
    # Shutdown: close any connections (important for cloud backends)
    await storage.close()


app = FastAPI(lifespan=lifespan)


def get_storage() -> Storage:
    """Dependency that provides the storage instance."""
    return storage


@app.post("/upload")
async def upload_file(
    file: UploadFile,
    storage: Storage = Depends(get_storage),
):
    """Upload a file."""
    content = await file.read()
    result = await storage.put(
        file.filename,
        content,
        content_type=file.content_type,
    )
    return {"key": result.key, "size": result.size}


@app.get("/files/{filename}")
async def get_file_info(
    filename: str,
    storage: Storage = Depends(get_storage),
):
    """Get file metadata."""
    info = await storage.info(filename)
    return {
        "key": info.key,
        "size": info.size,
        "content_type": info.content_type,
    }
```

### Using with Starlette

```python
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from litestar_storages import FileSystemStorage, FileSystemConfig

storage = FileSystemStorage(
    FileSystemConfig(path=Path("./uploads"), create_dirs=True)
)


async def upload(request: Request) -> JSONResponse:
    """Handle file upload."""
    form = await request.form()
    upload_file = form["file"]
    content = await upload_file.read()

    result = await storage.put(
        upload_file.filename,
        content,
        content_type=upload_file.content_type,
    )
    return JSONResponse({"key": result.key, "size": result.size})


async def on_shutdown():
    await storage.close()


app = Starlette(
    routes=[Route("/upload", upload, methods=["POST"])],
    on_shutdown=[on_shutdown],
)
```

## Using with Litestar

The `StoragePlugin` integrates storage into your Litestar application with dependency injection.

### Basic Setup

```python
from pathlib import Path
from litestar import Litestar, post, get
from litestar.datastructures import UploadFile
from litestar_storages import (
    Storage,
    StoredFile,
    FileSystemStorage,
    FileSystemConfig,
    StoragePlugin,
)


@post("/upload")
async def upload_file(
    data: UploadFile,
    storage: Storage,  # Automatically injected
) -> StoredFile:
    """Handle file upload."""
    content = await data.read()
    return await storage.put(
        key=data.filename,
        data=content,
        content_type=data.content_type,
    )


@get("/files/{filename:str}")
async def get_file_info(
    filename: str,
    storage: Storage,
) -> StoredFile:
    """Get file metadata."""
    return await storage.info(filename)


# Configure and create the application
storage = FileSystemStorage(
    config=FileSystemConfig(
        path=Path("./uploads"),
        base_url="/static/uploads",
    )
)

app = Litestar(
    route_handlers=[upload_file, get_file_info],
    plugins=[StoragePlugin(storage)],
)
```

### Multiple Named Storages

Use different storages for different purposes:

```python
from litestar_storages import (
    StoragePlugin,
    FileSystemStorage,
    FileSystemConfig,
    S3Storage,
    S3Config,
)

app = Litestar(
    route_handlers=[...],
    plugins=[
        StoragePlugin(
            # Default storage (inject as `storage: Storage`)
            default=FileSystemStorage(
                FileSystemConfig(path=Path("./uploads"))
            ),
            # Named storage (inject as `images_storage: Storage`)
            images=S3Storage(
                S3Config(bucket="my-images-bucket")
            ),
            # Another named storage (inject as `documents_storage: Storage`)
            documents=S3Storage(
                S3Config(bucket="my-documents-bucket")
            ),
        )
    ],
)


@post("/images")
async def upload_image(
    data: UploadFile,
    images_storage: Storage,  # Uses the "images" storage
) -> StoredFile:
    content = await data.read()
    return await images_storage.put(data.filename, content)


@post("/documents")
async def upload_document(
    data: UploadFile,
    documents_storage: Storage,  # Uses the "documents" storage
) -> StoredFile:
    content = await data.read()
    return await documents_storage.put(data.filename, content)
```

## Configuration Patterns

### Environment Variables

All backends support environment variable fallbacks for sensitive configuration:

```python
import os
from litestar_storages import S3Storage, S3Config

# These will use AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
# environment variables if not explicitly provided
storage = S3Storage(
    config=S3Config(
        bucket=os.environ["UPLOADS_BUCKET"],
        region=os.environ.get("AWS_REGION", "us-east-1"),
        # access_key_id and secret_access_key fall back to env vars
    )
)
```

### Dataclass Configuration

Use dataclasses for clean, type-safe configuration:

```python
from dataclasses import dataclass
from pathlib import Path
from litestar_storages import FileSystemConfig, S3Config


@dataclass
class AppConfig:
    uploads_path: Path = Path("./uploads")
    uploads_url: str = "/static/uploads"

    @property
    def storage_config(self) -> FileSystemConfig:
        return FileSystemConfig(
            path=self.uploads_path,
            base_url=self.uploads_url,
        )


config = AppConfig()
storage = FileSystemStorage(config.storage_config)
```

### Factory Pattern

Create storage instances based on environment:

```python
import os
from pathlib import Path
from litestar_storages import (
    Storage,
    FileSystemStorage,
    FileSystemConfig,
    S3Storage,
    S3Config,
    MemoryStorage,
)


def create_storage() -> Storage:
    """Create storage based on environment."""
    env = os.environ.get("ENVIRONMENT", "development")

    if env == "production":
        return S3Storage(
            S3Config(
                bucket=os.environ["S3_BUCKET"],
                region=os.environ.get("AWS_REGION", "us-east-1"),
            )
        )
    elif env == "testing":
        return MemoryStorage()
    else:  # development
        return FileSystemStorage(
            FileSystemConfig(path=Path("./dev-uploads"))
        )


storage = create_storage()
```

## Next Steps

- Learn about [FileSystem storage](backends/filesystem.md) for local file handling
- Set up [S3 storage](backends/s3.md) for AWS and S3-compatible services
- Set up [GCS storage](backends/gcs.md) for Google Cloud Storage
- Set up [Azure storage](backends/azure.md) for Azure Blob Storage
- Use [Memory storage](backends/memory.md) for testing
- Explore [example applications](examples.md) for complete working examples
- Create [custom backends](advanced/custom-backends.md) for specialized needs
