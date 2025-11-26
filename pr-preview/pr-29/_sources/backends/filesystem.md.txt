# FileSystem Storage

The `FileSystemStorage` backend stores files on the local filesystem. It's ideal for development, single-server deployments, or when you need direct filesystem access to stored files.

## Configuration

The `FileSystemConfig` dataclass controls all filesystem storage behavior:

```python
from pathlib import Path
from litestar_storages import FileSystemStorage, FileSystemConfig

config = FileSystemConfig(
    path=Path("/var/uploads"),      # Required: base directory for storage
    base_url="https://cdn.example.com/uploads",  # Optional: URL prefix
    create_dirs=True,               # Optional: auto-create directories (default: True)
    permissions=0o644,              # Optional: file permissions (default: 0o644)
)

storage = FileSystemStorage(config)
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `path` | `Path` | Required | Base directory for all stored files |
| `base_url` | `str \| None` | `None` | URL prefix for generating file URLs |
| `create_dirs` | `bool` | `True` | Automatically create directories as needed |
| `permissions` | `int` | `0o644` | Unix file permissions for created files |

## Basic Usage

### Storing Files

```python
from pathlib import Path
from litestar_storages import FileSystemStorage, FileSystemConfig

storage = FileSystemStorage(
    config=FileSystemConfig(path=Path("./uploads"))
)

# Store bytes directly
result = await storage.put(
    "documents/report.pdf",
    pdf_bytes,
    content_type="application/pdf",
)
print(f"Stored: {result.key}, size: {result.size} bytes")

# Store with custom metadata
result = await storage.put(
    "images/photo.jpg",
    image_bytes,
    content_type="image/jpeg",
    metadata={"author": "John Doe", "camera": "Canon EOS R5"},
)
```

### Retrieving Files

```python
# Get entire file as bytes (for small files)
content = await storage.get_bytes("documents/report.pdf")

# Stream file contents (for large files)
async for chunk in storage.get("videos/large-video.mp4"):
    await process_chunk(chunk)

# Get file metadata without downloading
info = await storage.info("documents/report.pdf")
print(f"Size: {info.size}, Modified: {info.last_modified}")
```

### Listing Files

```python
# List all files
async for file in storage.list():
    print(f"{file.key}: {file.size} bytes")

# List files with a prefix (like a directory)
async for file in storage.list("images/"):
    print(f"Image: {file.key}")

# Limit results
async for file in storage.list("logs/", limit=100):
    print(file.key)
```

### Other Operations

```python
# Check if file exists
if await storage.exists("documents/report.pdf"):
    print("File exists!")

# Copy a file
new_file = await storage.copy("images/photo.jpg", "images/photo-backup.jpg")

# Move/rename a file
moved = await storage.move("temp/upload.jpg", "images/final.jpg")

# Delete a file
await storage.delete("temp/old-file.txt")
```

## Path Handling and Security

### Key Normalization

Keys are automatically normalized for security and consistency:

```python
# Backslashes are converted to forward slashes
await storage.put("path\\to\\file.txt", data)  # Stored as "path/to/file.txt"

# Leading slashes are removed
await storage.put("/absolute/path.txt", data)  # Stored as "absolute/path.txt"

# Path traversal attempts are blocked
await storage.put("../../../etc/passwd", data)  # Raises error or sanitized
```

### Directory Structure

Files are stored in subdirectories matching their keys:

```python
# Configuration
storage = FileSystemStorage(
    config=FileSystemConfig(path=Path("/var/uploads"))
)

# Storing files creates directory structure automatically
await storage.put("users/123/avatar.jpg", data)
# Creates: /var/uploads/users/123/avatar.jpg

await storage.put("documents/2024/01/report.pdf", data)
# Creates: /var/uploads/documents/2024/01/report.pdf
```

### File Permissions

Control permissions on created files:

```python
# Readable by owner only
config = FileSystemConfig(
    path=Path("/secure/uploads"),
    permissions=0o600,  # rw-------
)

# World-readable (for public assets)
config = FileSystemConfig(
    path=Path("/public/assets"),
    permissions=0o644,  # rw-r--r--
)
```

## URL Generation

The `url()` method generates URLs for accessing files. Behavior depends on whether `base_url` is configured.

### Without base_url

Returns the absolute filesystem path:

```python
storage = FileSystemStorage(
    config=FileSystemConfig(path=Path("/var/uploads"))
)

url = await storage.url("images/photo.jpg")
# Returns: "/var/uploads/images/photo.jpg"
```

### With base_url

Returns a URL combining the base URL and file key:

```python
storage = FileSystemStorage(
    config=FileSystemConfig(
        path=Path("/var/uploads"),
        base_url="https://cdn.example.com/uploads",
    )
)

url = await storage.url("images/photo.jpg")
# Returns: "https://cdn.example.com/uploads/images/photo.jpg"
```

### URL Configuration Patterns

**Serving via reverse proxy (nginx, Caddy):**

```python
# Files in /var/www/static/uploads
# Nginx serves /var/www/static at https://example.com/static
config = FileSystemConfig(
    path=Path("/var/www/static/uploads"),
    base_url="https://example.com/static/uploads",
)
```

**Serving via CDN:**

```python
# Files in /var/uploads
# CDN pulls from origin, serves at cdn.example.com
config = FileSystemConfig(
    path=Path("/var/uploads"),
    base_url="https://cdn.example.com",
)
```

**Development with Litestar static files:**

```python
from litestar import Litestar
from litestar.static_files import create_static_files_router

config = FileSystemConfig(
    path=Path("./uploads"),
    base_url="/static/uploads",
)

app = Litestar(
    route_handlers=[...],
    plugins=[StoragePlugin(FileSystemStorage(config))],
    route_handlers=[
        create_static_files_router(
            path="/static/uploads",
            directories=["./uploads"],
        ),
    ],
)
```

## Usage Examples

### File Upload Handler

```python
from litestar import post
from litestar.datastructures import UploadFile
from litestar_storages import Storage, StoredFile
import uuid


@post("/upload")
async def upload_file(
    data: UploadFile,
    storage: Storage,
) -> StoredFile:
    """Upload a file with a unique name."""
    # Generate unique filename to prevent overwrites
    ext = Path(data.filename).suffix
    unique_name = f"{uuid.uuid4()}{ext}"
    key = f"uploads/{unique_name}"

    content = await data.read()
    return await storage.put(
        key=key,
        data=content,
        content_type=data.content_type,
        metadata={"original_name": data.filename},
    )
```

### Organized File Storage

```python
from datetime import datetime


async def store_user_document(
    user_id: int,
    filename: str,
    content: bytes,
    storage: Storage,
) -> StoredFile:
    """Store a user document in an organized structure."""
    # Organize by user and date
    today = datetime.now().strftime("%Y/%m/%d")
    key = f"users/{user_id}/documents/{today}/{filename}"

    return await storage.put(
        key=key,
        data=content,
        content_type="application/octet-stream",
    )


# Usage
result = await store_user_document(
    user_id=123,
    filename="contract.pdf",
    content=pdf_bytes,
    storage=storage,
)
# Stored at: users/123/documents/2024/01/15/contract.pdf
```

### Cleanup Old Files

```python
from datetime import datetime, timedelta


async def cleanup_old_temp_files(
    storage: Storage,
    max_age: timedelta = timedelta(days=7),
) -> int:
    """Delete temporary files older than max_age."""
    deleted = 0
    cutoff = datetime.now() - max_age

    async for file in storage.list("temp/"):
        if file.last_modified and file.last_modified < cutoff:
            await storage.delete(file.key)
            deleted += 1

    return deleted
```

## Limitations

- **No presigned URLs**: Unlike cloud backends, filesystem storage cannot generate time-limited signed URLs. The `url()` method returns static paths.

- **Single server only**: Files are stored locally, so they are only accessible from the server where they are stored. For multi-server deployments, use a shared filesystem (NFS) or a cloud backend.

- **Manual backup required**: Unlike cloud storage, local files are not automatically replicated. Implement your own backup strategy.

- **Limited metadata**: Custom metadata is not persisted to the filesystem (only available in memory during the session). For persistent metadata, use a database or a cloud backend.

## Next Steps

- Learn about [S3 storage](s3.md) for cloud-based file storage with presigned URLs
- Use [Memory storage](memory.md) for testing without touching the filesystem
