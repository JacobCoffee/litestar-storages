# Example Applications

This guide walks through two example applications that demonstrate how to use litestar-storages in real-world scenarios. The examples progress from a minimal "hello world" application to a full-featured API with multiple storage backends, controllers, and proper error handling.

## Overview

| Example | Location | Purpose |
|---------|----------|---------|
| Minimal | `examples/minimal/` | Basic upload, download, and list operations |
| Full-Featured | `examples/full_featured/` | Multiple storages, controllers, DTOs, exception handling |

Both examples use `MemoryStorage` by default for easy testing without external dependencies. See [Swapping Storage Backends](#swapping-storage-backends) for instructions on using S3 or filesystem storage.

---

## Minimal Example

**Location**: `examples/minimal/app.py`

This example demonstrates the core functionality of litestar-storages in under 60 lines of code.

### What It Demonstrates

- Single storage backend setup with `StoragePlugin`
- File upload via multipart form data
- Streaming file download
- Listing all stored files
- Dependency injection of the `Storage` instance

### Running the Example

From the project root:

```bash
uv run litestar --app examples.minimal.app:app run
```

Or from the `examples/minimal/` directory:

```bash
cd examples/minimal
uv run litestar run
```

The server starts at `http://localhost:8000` by default.

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/upload` | Upload a file (multipart form data) |
| `GET` | `/files/{key:path}` | Download a file by key |
| `GET` | `/files` | List all stored files |

### Code Walkthrough

#### Application Setup

```python
from litestar import Litestar, get, post
from litestar_storages import Storage, StoredFile
from litestar_storages.backends.memory import MemoryStorage
from litestar_storages.contrib.plugin import StoragePlugin

app = Litestar(
    route_handlers=[upload, download, list_files],
    plugins=[StoragePlugin(default=MemoryStorage())],
)
```

The `StoragePlugin` registers a `MemoryStorage` instance as the default storage. This enables dependency injection of `Storage` into route handlers.

#### Upload Handler

```python
@post("/upload")
async def upload(
    data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    storage: Storage,  # Injected by StoragePlugin
) -> StoredFile:
    """Upload a file."""
    content = await data.read()
    return await storage.put(
        key=data.filename or "unnamed",
        data=content,
        content_type=data.content_type,
    )
```

Key points:
- `UploadFile` handles multipart form data parsing
- `Storage` is automatically injected via the plugin
- `storage.put()` returns a `StoredFile` with metadata about the stored file

#### Download Handler

```python
@get("/files/{key:path}")
async def download(key: str, storage: Storage) -> Stream:
    """Download a file."""
    info = await storage.info(key)
    return Stream(
        iterator=storage.get(key),
        media_type=info.content_type,
    )
```

Key points:
- The `{key:path}` parameter allows keys with slashes (e.g., `uploads/images/photo.jpg`)
- `storage.get()` returns an async iterator for streaming
- `Stream` response efficiently handles large files without loading them into memory

#### List Handler

```python
@get("/files")
async def list_files(storage: Storage) -> list[StoredFile]:
    """List all files."""
    return [f async for f in storage.list()]
```

The `storage.list()` method returns an async generator, which we collect into a list for the JSON response.

---

## Full-Featured Example

**Location**: `examples/full_featured/app.py`

This example demonstrates production-ready patterns for building file storage APIs.

### What It Demonstrates

- Multiple named storage backends (images, documents)
- Controller-based route organization
- DTO responses for clean API output
- Custom exception handlers for storage errors
- Content-type validation
- Presigned URL generation
- Proper HTTP status codes and response headers

### Running the Example

From the project root:

```bash
uv run litestar --app examples.full_featured.app:app run
```

Or from the `examples/full_featured/` directory:

```bash
cd examples/full_featured
uv run litestar run
```

### API Endpoints

#### Images Controller (`/api/images`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/images/` | Upload an image (validates `image/*` content type) |
| `GET` | `/api/images/` | List all images |
| `GET` | `/api/images/{key:path}` | Get image metadata |
| `GET` | `/api/images/{key:path}/download` | Download an image |
| `DELETE` | `/api/images/{key:path}` | Delete an image |

#### Documents Controller (`/api/documents`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/` | Upload a document |
| `GET` | `/api/documents/` | List all documents |
| `GET` | `/api/documents/{key:path}` | Get document metadata |
| `GET` | `/api/documents/{key:path}/download` | Download a document |
| `GET` | `/api/documents/{key:path}/url` | Get presigned URL (15 min expiry) |
| `DELETE` | `/api/documents/{key:path}` | Delete a document |

#### Utility

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check endpoint |

### Code Walkthrough

#### Multiple Named Storages

```python
# Create storage backends
images_storage = MemoryStorage()
documents_storage = MemoryStorage()

app = Litestar(
    route_handlers=[...],
    plugins=[
        StoragePlugin(
            images=images_storage,      # -> images_storage: Storage
            documents=documents_storage, # -> documents_storage: Storage
        )
    ],
)
```

Named storages are injected using the naming convention `{name}_storage`. For example:
- `images` becomes `images_storage: Storage`
- `documents` becomes `documents_storage: Storage`

#### Controller Organization

```python
class ImageController(Controller):
    """Controller for image file operations."""

    path = "/api/images"
    tags = ["Images"]

    @post("/", return_dto=StoredFileDTO)
    async def upload_image(
        self,
        data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
        images_storage: Storage,  # Named storage injection
    ) -> StoredFile:
        # ...
```

Controllers group related endpoints and can specify:
- Base path (`/api/images`)
- OpenAPI tags for documentation
- DTOs for response serialization

#### Exception Handlers

```python
from litestar_storages.exceptions import StorageFileNotFoundError, StorageFileExistsError

def storage_not_found_handler(request: Request, exc: StorageFileNotFoundError) -> Response:
    """Convert StorageFileNotFoundError to 404 response."""
    return Response(
        content={"detail": f"File not found: {exc.key}"},
        status_code=HTTP_404_NOT_FOUND,
    )

def storage_exists_handler(request: Request, exc: StorageFileExistsError) -> Response:
    """Convert StorageFileExistsError to 409 response."""
    return Response(
        content={"detail": f"File already exists: {exc.key}"},
        status_code=HTTP_409_CONFLICT,
    )

app = Litestar(
    # ...
    exception_handlers={
        StorageFileNotFoundError: storage_not_found_handler,
        StorageFileExistsError: storage_exists_handler,
    },
)
```

Custom exception handlers convert storage-specific exceptions into appropriate HTTP responses:
- `StorageFileNotFoundError` becomes HTTP 404
- `StorageFileExistsError` becomes HTTP 409

#### Content Type Validation

```python
@post("/", return_dto=StoredFileDTO)
async def upload_image(
    self,
    data: Annotated[UploadFile, Body(media_type=RequestEncodingType.MULTI_PART)],
    images_storage: Storage,
) -> StoredFile:
    content = await data.read()
    content_type = data.content_type or "application/octet-stream"

    # Basic content-type validation
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type: {content_type}. Expected image/*",
        )

    return await images_storage.put(
        key=f"uploads/{data.filename}",
        data=content,
        content_type=content_type,
    )
```

The image controller validates that uploaded files have an `image/*` content type before storing them.

#### Presigned URL Generation

```python
@get("/{key:path}/url")
async def get_document_url(self, key: str, documents_storage: Storage) -> dict[str, str]:
    """Get a presigned URL for document download."""
    url = await documents_storage.url(key, expires_in=timedelta(minutes=15))
    return {"url": url, "expires_in": "15 minutes"}
```

Presigned URLs allow temporary access to files without authentication. This is particularly useful with S3 and other cloud backends.

Note: `MemoryStorage` returns `memory://` URLs which are not externally accessible. Use `S3Storage` or `FileSystemStorage` with a `base_url` for real presigned URLs.

#### Download Response Headers

```python
@get("/{key:path}/download")
async def download_image(self, key: str, images_storage: Storage) -> Stream:
    info = await images_storage.info(key)
    return Stream(
        iterator=images_storage.get(key),
        media_type=info.content_type,
        headers={
            "Content-Length": str(info.size),
            "Content-Disposition": f'inline; filename="{key.split("/")[-1]}"',
        },
    )
```

Response headers provide:
- `Content-Length` for download progress indication
- `Content-Disposition` to suggest a filename (use `inline` for images, `attachment` for documents)

#### DTO Usage

```python
from litestar_storages.contrib.dto import StoredFileDTO, StoredFileReadDTO

@post("/", return_dto=StoredFileDTO)
async def upload_image(...) -> StoredFile:
    # Returns: key, size, content_type, etag, last_modified (excludes metadata)

@get("/{key:path}", return_dto=StoredFileReadDTO)
async def get_image_info(...) -> StoredFile:
    # Returns: all fields including metadata
```

DTOs control what fields are serialized in responses:
- `StoredFileDTO`: Excludes `metadata` field for cleaner responses
- `StoredFileReadDTO`: Includes all fields

---

## Swapping Storage Backends

The examples use `MemoryStorage` by default. Here's how to switch to production-ready backends:

### Using S3Storage

Replace `MemoryStorage` with `S3Storage`:

```python
from litestar_storages.backends.s3 import S3Storage, S3Config

# AWS S3
images_storage = S3Storage(
    config=S3Config(
        bucket="my-images-bucket",
        region="us-east-1",
        # Uses AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY from environment
    )
)

# Cloudflare R2
documents_storage = S3Storage(
    config=S3Config(
        bucket="my-documents-bucket",
        endpoint_url="https://ACCOUNT_ID.r2.cloudflarestorage.com",
        access_key_id="R2_ACCESS_KEY",
        secret_access_key="R2_SECRET_KEY",
    )
)

# DigitalOcean Spaces
storage = S3Storage(
    config=S3Config(
        bucket="my-space",
        endpoint_url="https://nyc3.digitaloceanspaces.com",
        region="nyc3",
    )
)

# MinIO (self-hosted)
storage = S3Storage(
    config=S3Config(
        bucket="my-bucket",
        endpoint_url="http://localhost:9000",
        access_key_id="minioadmin",
        secret_access_key="minioadmin",
        use_ssl=False,
    )
)
```

### Using FileSystemStorage

```python
from pathlib import Path
from litestar_storages.backends.filesystem import FileSystemStorage, FileSystemConfig

images_storage = FileSystemStorage(
    config=FileSystemConfig(
        path=Path("./uploads/images"),
        create_dirs=True,
        base_url="/static/images",  # For URL generation
    )
)

documents_storage = FileSystemStorage(
    config=FileSystemConfig(
        path=Path("./uploads/documents"),
        create_dirs=True,
        base_url="/static/documents",
    )
)
```

### Environment-Based Configuration

A common pattern is selecting the backend based on environment:

```python
import os
from pathlib import Path
from litestar_storages import Storage
from litestar_storages.backends.memory import MemoryStorage
from litestar_storages.backends.filesystem import FileSystemStorage, FileSystemConfig
from litestar_storages.backends.s3 import S3Storage, S3Config


def create_storage(name: str) -> Storage:
    """Create storage based on environment."""
    env = os.environ.get("ENVIRONMENT", "development")

    if env == "production":
        return S3Storage(
            config=S3Config(
                bucket=os.environ[f"{name.upper()}_BUCKET"],
                region=os.environ.get("AWS_REGION", "us-east-1"),
            )
        )
    elif env == "testing":
        return MemoryStorage()
    else:  # development
        return FileSystemStorage(
            config=FileSystemConfig(
                path=Path(f"./dev-uploads/{name}"),
                create_dirs=True,
            )
        )


images_storage = create_storage("images")
documents_storage = create_storage("documents")
```

---

## Testing the Examples

### Using curl

#### Upload a File

```bash
# Upload an image
curl -X POST http://localhost:8000/api/images/ \
  -F "data=@photo.jpg"

# Upload a document
curl -X POST http://localhost:8000/api/documents/ \
  -F "data=@document.pdf"

# Minimal example - upload
curl -X POST http://localhost:8000/upload \
  -F "data=@file.txt"
```

#### List Files

```bash
# List images
curl http://localhost:8000/api/images/

# List documents
curl http://localhost:8000/api/documents/

# Minimal example - list
curl http://localhost:8000/files
```

#### Download a File

```bash
# Download image
curl http://localhost:8000/api/images/uploads/photo.jpg/download -o photo.jpg

# Download document
curl http://localhost:8000/api/documents/docs/document.pdf/download -o document.pdf

# Minimal example - download
curl http://localhost:8000/files/file.txt -o file.txt
```

#### Get File Metadata

```bash
# Get image info
curl http://localhost:8000/api/images/uploads/photo.jpg

# Get document info
curl http://localhost:8000/api/documents/docs/document.pdf
```

#### Get Presigned URL

```bash
# Documents only
curl http://localhost:8000/api/documents/docs/document.pdf/url
```

#### Delete a File

```bash
# Delete image
curl -X DELETE http://localhost:8000/api/images/uploads/photo.jpg

# Delete document
curl -X DELETE http://localhost:8000/api/documents/docs/document.pdf
```

### Using HTTPie

[HTTPie](https://httpie.io/) provides a more user-friendly CLI:

```bash
# Upload a file
http -f POST localhost:8000/api/images/ data@photo.jpg

# List files
http localhost:8000/api/images/

# Get file info
http localhost:8000/api/images/uploads/photo.jpg

# Download (follow redirects, save to file)
http localhost:8000/api/images/uploads/photo.jpg/download > photo.jpg

# Delete
http DELETE localhost:8000/api/images/uploads/photo.jpg
```

### Using Python

```python
import httpx
import asyncio
from pathlib import Path


async def test_example():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # Upload a file
        with open("photo.jpg", "rb") as f:
            response = await client.post(
                "/api/images/",
                files={"data": ("photo.jpg", f, "image/jpeg")},
            )
            print("Upload:", response.json())

        # List files
        response = await client.get("/api/images/")
        print("List:", response.json())

        # Get file info
        response = await client.get("/api/images/uploads/photo.jpg")
        print("Info:", response.json())

        # Download file
        response = await client.get("/api/images/uploads/photo.jpg/download")
        Path("downloaded.jpg").write_bytes(response.content)
        print("Downloaded:", len(response.content), "bytes")

        # Delete file
        response = await client.delete("/api/images/uploads/photo.jpg")
        print("Deleted:", response.status_code)


asyncio.run(test_example())
```

---

## Next Steps

- Learn about [FileSystem storage configuration](backends/filesystem.md)
- Set up [S3 storage](backends/s3.md) for production
- Explore [custom backend development](advanced/custom-backends.md)
- See the [API Reference](api/index) for complete method documentation
