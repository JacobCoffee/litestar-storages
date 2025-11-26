# Multi-Backend Configuration

Configure different storage backends for development, testing, and production environments. This recipe demonstrates how to build an environment-aware storage factory that seamlessly switches between filesystem (development), memory (testing), and cloud storage (production).

## Prerequisites

- Python 3.9+
- litestar-storages installed (`pip install litestar-storages`)
- For S3: `pip install litestar-storages[s3]`
- For Litestar: `pip install litestar-storages[litestar]`

## The Problem

Modern applications need different storage configurations:

- **Development**: Local filesystem for simplicity and quick iteration
- **Testing**: In-memory storage for speed and isolation
- **Staging**: Cloud storage with test credentials
- **Production**: Cloud storage with production credentials and CDN

Hardcoding configuration leads to fragile code and security risks. Environment-based configuration provides flexibility while maintaining consistency.

## Solution

### Storage Factory

Create a factory that returns the appropriate storage backend based on configuration:

```python
"""Environment-aware storage factory."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from litestar_storages import (
    Storage,
    MemoryStorage,
    MemoryConfig,
    FileSystemStorage,
    FileSystemConfig,
    S3Storage,
    S3Config,
)

# Optional cloud backends
try:
    from litestar_storages import GCSStorage, GCSConfig
    HAS_GCS = True
except ImportError:
    HAS_GCS = False

try:
    from litestar_storages import AzureStorage, AzureConfig
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False


class StorageBackend(str, Enum):
    """Supported storage backends."""

    MEMORY = "memory"
    FILESYSTEM = "filesystem"
    S3 = "s3"
    GCS = "gcs"
    AZURE = "azure"


class Environment(str, Enum):
    """Application environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class StorageSettings:
    """Storage configuration settings.

    Attributes:
        backend: Storage backend type
        local_path: Path for filesystem storage
        local_base_url: Base URL for filesystem storage
        s3_bucket: S3 bucket name
        s3_region: AWS region
        s3_endpoint_url: Custom S3 endpoint (for R2, MinIO, etc.)
        s3_prefix: Key prefix for S3 storage
        gcs_bucket: GCS bucket name
        gcs_prefix: Key prefix for GCS storage
        azure_container: Azure Blob container name
        azure_connection_string: Azure connection string
    """

    backend: StorageBackend = StorageBackend.FILESYSTEM

    # Filesystem settings
    local_path: Path = field(default_factory=lambda: Path("./uploads"))
    local_base_url: str | None = None

    # S3 settings
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    s3_prefix: str = ""
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    # GCS settings
    gcs_bucket: str = ""
    gcs_prefix: str = ""
    gcs_credentials_path: str | None = None

    # Azure settings
    azure_container: str = ""
    azure_connection_string: str | None = None

    @classmethod
    def from_env(cls, prefix: str = "STORAGE") -> "StorageSettings":
        """Load settings from environment variables.

        Environment variables:
            {PREFIX}_BACKEND: Backend type (memory, filesystem, s3, gcs, azure)
            {PREFIX}_LOCAL_PATH: Local filesystem path
            {PREFIX}_LOCAL_BASE_URL: Base URL for local files
            {PREFIX}_S3_BUCKET: S3 bucket name
            {PREFIX}_S3_REGION: AWS region
            {PREFIX}_S3_ENDPOINT_URL: Custom S3 endpoint
            {PREFIX}_S3_PREFIX: S3 key prefix
            {PREFIX}_S3_ACCESS_KEY_ID: AWS access key
            {PREFIX}_S3_SECRET_ACCESS_KEY: AWS secret key
            {PREFIX}_GCS_BUCKET: GCS bucket name
            {PREFIX}_GCS_PREFIX: GCS key prefix
            {PREFIX}_GCS_CREDENTIALS_PATH: Path to GCS credentials JSON
            {PREFIX}_AZURE_CONTAINER: Azure container name
            {PREFIX}_AZURE_CONNECTION_STRING: Azure connection string

        Args:
            prefix: Environment variable prefix

        Returns:
            StorageSettings populated from environment
        """
        def env(key: str, default: str = "") -> str:
            return os.getenv(f"{prefix}_{key}", default)

        backend_str = env("BACKEND", "filesystem").lower()
        try:
            backend = StorageBackend(backend_str)
        except ValueError:
            backend = StorageBackend.FILESYSTEM

        return cls(
            backend=backend,
            local_path=Path(env("LOCAL_PATH", "./uploads")),
            local_base_url=env("LOCAL_BASE_URL") or None,
            s3_bucket=env("S3_BUCKET"),
            s3_region=env("S3_REGION", "us-east-1"),
            s3_endpoint_url=env("S3_ENDPOINT_URL") or None,
            s3_prefix=env("S3_PREFIX"),
            s3_access_key_id=env("S3_ACCESS_KEY_ID") or None,
            s3_secret_access_key=env("S3_SECRET_ACCESS_KEY") or None,
            gcs_bucket=env("GCS_BUCKET"),
            gcs_prefix=env("GCS_PREFIX"),
            gcs_credentials_path=env("GCS_CREDENTIALS_PATH") or None,
            azure_container=env("AZURE_CONTAINER"),
            azure_connection_string=env("AZURE_CONNECTION_STRING") or None,
        )


def create_storage(settings: StorageSettings | None = None) -> Storage:
    """Create storage backend from settings.

    Args:
        settings: Storage settings (defaults to loading from environment)

    Returns:
        Configured storage backend

    Raises:
        ValueError: If required configuration is missing
        ImportError: If required backend package is not installed
    """
    if settings is None:
        settings = StorageSettings.from_env()

    if settings.backend == StorageBackend.MEMORY:
        return MemoryStorage(config=MemoryConfig())

    if settings.backend == StorageBackend.FILESYSTEM:
        return FileSystemStorage(
            config=FileSystemConfig(
                path=settings.local_path,
                base_url=settings.local_base_url,
                create_dirs=True,
            )
        )

    if settings.backend == StorageBackend.S3:
        if not settings.s3_bucket:
            raise ValueError("S3 bucket name is required (STORAGE_S3_BUCKET)")

        return S3Storage(
            config=S3Config(
                bucket=settings.s3_bucket,
                region=settings.s3_region,
                endpoint_url=settings.s3_endpoint_url,
                prefix=settings.s3_prefix,
                access_key_id=settings.s3_access_key_id,
                secret_access_key=settings.s3_secret_access_key,
            )
        )

    if settings.backend == StorageBackend.GCS:
        if not HAS_GCS:
            raise ImportError("GCS support requires: pip install litestar-storages[gcs]")
        if not settings.gcs_bucket:
            raise ValueError("GCS bucket name is required (STORAGE_GCS_BUCKET)")

        return GCSStorage(
            config=GCSConfig(
                bucket=settings.gcs_bucket,
                prefix=settings.gcs_prefix,
            )
        )

    if settings.backend == StorageBackend.AZURE:
        if not HAS_AZURE:
            raise ImportError("Azure support requires: pip install litestar-storages[azure]")
        if not settings.azure_container:
            raise ValueError("Azure container is required (STORAGE_AZURE_CONTAINER)")

        return AzureStorage(
            config=AzureConfig(
                container=settings.azure_container,
                connection_string=settings.azure_connection_string,
            )
        )

    raise ValueError(f"Unknown backend: {settings.backend}")


def get_default_settings_for_env(env: Environment) -> StorageSettings:
    """Get sensible default settings for an environment.

    Args:
        env: Target environment

    Returns:
        Default StorageSettings for the environment
    """
    if env == Environment.TESTING:
        return StorageSettings(backend=StorageBackend.MEMORY)

    if env == Environment.DEVELOPMENT:
        return StorageSettings(
            backend=StorageBackend.FILESYSTEM,
            local_path=Path("./dev-uploads"),
            local_base_url="/files",
        )

    # Staging and Production default to S3 (customize as needed)
    return StorageSettings(
        backend=StorageBackend.S3,
        # Actual values should come from environment variables
    )
```

### Framework-Agnostic Usage

Use the factory in a standalone application:

```python
"""Framework-agnostic multi-backend storage usage."""

import asyncio
import os
from pathlib import Path

# Import factory from above
# from storage_factory import create_storage, StorageSettings, StorageBackend


async def main() -> None:
    """Demonstrate environment-aware storage."""

    # Option 1: Auto-detect from environment
    storage = create_storage()

    # Option 2: Explicit configuration for development
    dev_storage = create_storage(
        StorageSettings(
            backend=StorageBackend.FILESYSTEM,
            local_path=Path("./dev-uploads"),
            local_base_url="http://localhost:8000/files",
        )
    )

    # Option 3: Explicit configuration for testing
    test_storage = create_storage(
        StorageSettings(backend=StorageBackend.MEMORY)
    )

    # Option 4: Explicit S3 configuration
    # In real usage, credentials come from environment
    s3_storage = create_storage(
        StorageSettings(
            backend=StorageBackend.S3,
            s3_bucket="my-app-uploads",
            s3_region="us-west-2",
            s3_prefix="uploads/",
        )
    )

    # Use the storage (all backends have the same interface)
    await storage.put(
        key="test/hello.txt",
        data=b"Hello, World!",
        content_type="text/plain",
    )

    # Read it back
    content = await storage.get_bytes("test/hello.txt")
    print(f"Content: {content.decode()}")

    # Get URL (format varies by backend)
    url = await storage.url("test/hello.txt")
    print(f"URL: {url}")

    # Clean up
    await storage.delete("test/hello.txt")
    await storage.close()


if __name__ == "__main__":
    # Set environment for testing
    os.environ["STORAGE_BACKEND"] = "filesystem"
    os.environ["STORAGE_LOCAL_PATH"] = "./demo-uploads"

    asyncio.run(main())
```

### With Litestar

Integrate environment-aware storage into a Litestar application:

```python
"""Litestar application with multi-backend storage."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

from litestar import Litestar, get, post, delete
from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.exceptions import NotFoundException

from litestar_storages import Storage, StoredFile, StorageFileNotFoundError
from litestar_storages.contrib.plugin import StoragePlugin

# Import factory from above
# from storage_factory import create_storage, StorageSettings, StorageBackend, Environment


@dataclass
class AppConfig:
    """Application configuration."""

    environment: str
    storage_settings: StorageSettings
    debug: bool = False

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load config from environment."""
        env = os.getenv("APP_ENV", "development")

        return cls(
            environment=env,
            storage_settings=StorageSettings.from_env(),
            debug=env == "development",
        )


# Response DTOs
@dataclass
class FileResponse:
    """File information response."""

    key: str
    size: int
    content_type: str | None
    url: str


@dataclass
class HealthResponse:
    """Health check response."""

    status: str
    environment: str
    storage_backend: str


# Route handlers
@get("/health")
async def health_check(
    config: Annotated[AppConfig, Provide(AppConfig.from_env)],
) -> HealthResponse:
    """Check application health."""
    return HealthResponse(
        status="healthy",
        environment=config.environment,
        storage_backend=config.storage_settings.backend.value,
    )


@post("/files/{path:path}")
async def upload_file(
    path: str,
    data: UploadFile,
    storage: Storage,
) -> FileResponse:
    """Upload a file to storage."""
    content = await data.read()

    stored = await storage.put(
        key=path,
        data=content,
        content_type=data.content_type,
    )

    url = await storage.url(path)

    return FileResponse(
        key=stored.key,
        size=stored.size,
        content_type=stored.content_type,
        url=url,
    )


@get("/files/{path:path}")
async def get_file_info(
    path: str,
    storage: Storage,
) -> FileResponse:
    """Get file information."""
    try:
        info = await storage.info(path)
        url = await storage.url(path)

        return FileResponse(
            key=info.key,
            size=info.size,
            content_type=info.content_type,
            url=url,
        )
    except StorageFileNotFoundError as e:
        raise NotFoundException(detail=f"File not found: {path}") from e


@delete("/files/{path:path}")
async def delete_file(
    path: str,
    storage: Storage,
) -> dict[str, str]:
    """Delete a file."""
    try:
        await storage.delete(path)
        return {"status": "deleted", "key": path}
    except StorageFileNotFoundError as e:
        raise NotFoundException(detail=f"File not found: {path}") from e


# Application factory
def create_app() -> Litestar:
    """Create Litestar application with environment-aware storage."""
    config = AppConfig.from_env()
    storage = create_storage(config.storage_settings)

    return Litestar(
        route_handlers=[health_check, upload_file, get_file_info, delete_file],
        plugins=[StoragePlugin(default=storage)],
        debug=config.debug,
    )


# For development: uvicorn main:app --reload
app = create_app()
```

### Testing with Isolated Storage

Use memory storage for fast, isolated tests:

```python
"""Test suite with isolated storage."""

import pytest
from pathlib import Path

from litestar.testing import TestClient

# Import from above
# from storage_factory import create_storage, StorageSettings, StorageBackend
# from app import create_app


@pytest.fixture
def test_storage():
    """Create isolated memory storage for tests."""
    return create_storage(StorageSettings(backend=StorageBackend.MEMORY))


@pytest.fixture
def test_app(test_storage):
    """Create test application with memory storage."""
    from litestar import Litestar
    from litestar_storages.contrib.plugin import StoragePlugin

    # Import route handlers
    from app import health_check, upload_file, get_file_info, delete_file

    return Litestar(
        route_handlers=[health_check, upload_file, get_file_info, delete_file],
        plugins=[StoragePlugin(default=test_storage)],
    )


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


class TestFileUpload:
    """Tests for file upload functionality."""

    def test_upload_and_retrieve(self, client):
        """Test uploading and retrieving a file."""
        # Upload
        response = client.post(
            "/files/test/hello.txt",
            files={"data": ("hello.txt", b"Hello, World!", "text/plain")},
        )
        assert response.status_code == 201

        data = response.json()
        assert data["key"] == "test/hello.txt"
        assert data["size"] == 13
        assert data["content_type"] == "text/plain"

    def test_file_not_found(self, client):
        """Test 404 for missing files."""
        response = client.get("/files/nonexistent.txt")
        assert response.status_code == 404

    def test_delete_file(self, client):
        """Test file deletion."""
        # Upload first
        client.post(
            "/files/to-delete.txt",
            files={"data": ("to-delete.txt", b"Delete me", "text/plain")},
        )

        # Delete
        response = client.delete("/files/to-delete.txt")
        assert response.status_code == 200

        # Verify deleted
        response = client.get("/files/to-delete.txt")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_storage_isolation(test_storage):
    """Test that memory storage is isolated between tests."""
    # Each test gets a fresh storage instance
    files = [f async for f in test_storage.list()]
    assert len(files) == 0, "Storage should be empty at test start"

    # Add a file
    await test_storage.put("isolation-test.txt", b"test", content_type="text/plain")

    # Verify it exists
    assert await test_storage.exists("isolation-test.txt")
```

### Environment-Specific Configuration Files

Organize configuration with environment files:

```bash
# .env.development
APP_ENV=development
STORAGE_BACKEND=filesystem
STORAGE_LOCAL_PATH=./dev-uploads
STORAGE_LOCAL_BASE_URL=http://localhost:8000/files

# .env.testing
APP_ENV=testing
STORAGE_BACKEND=memory

# .env.staging
APP_ENV=staging
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=myapp-staging-uploads
STORAGE_S3_REGION=us-west-2
STORAGE_S3_PREFIX=uploads/

# .env.production
APP_ENV=production
STORAGE_BACKEND=s3
STORAGE_S3_BUCKET=myapp-prod-uploads
STORAGE_S3_REGION=us-west-2
STORAGE_S3_PREFIX=uploads/
# Note: AWS credentials from IAM role or AWS_* env vars
```

Load with python-dotenv:

```python
"""Load environment-specific configuration."""

import os
from pathlib import Path
from dotenv import load_dotenv


def load_config() -> None:
    """Load configuration for current environment."""
    env = os.getenv("APP_ENV", "development")

    # Load environment-specific file
    env_file = Path(f".env.{env}")
    if env_file.exists():
        load_dotenv(env_file)

    # Load local overrides (gitignored)
    local_file = Path(".env.local")
    if local_file.exists():
        load_dotenv(local_file, override=True)


# Call at application startup
load_config()
```

### Multiple Named Storages

Configure different storage backends for different purposes:

```python
"""Multiple storage backends for different file types."""

from litestar import Litestar, post
from litestar.datastructures import UploadFile

from litestar_storages import (
    Storage,
    S3Storage,
    S3Config,
    FileSystemStorage,
    FileSystemConfig,
)
from litestar_storages.contrib.plugin import StoragePlugin


def create_storages() -> dict[str, Storage]:
    """Create multiple storage backends."""
    return {
        # Fast local storage for temporary files
        "temp": FileSystemStorage(
            config=FileSystemConfig(
                path=Path("/tmp/app-uploads"),
                create_dirs=True,
            )
        ),

        # S3 for user uploads
        "uploads": S3Storage(
            config=S3Config(
                bucket="myapp-user-uploads",
                prefix="user-files/",
            )
        ),

        # Separate bucket for public assets
        "public": S3Storage(
            config=S3Config(
                bucket="myapp-public-assets",
                prefix="assets/",
            )
        ),
    }


@post("/upload/avatar")
async def upload_avatar(
    data: UploadFile,
    uploads_storage: Storage,  # Injected as "{name}_storage"
) -> dict:
    """Upload user avatar to uploads storage."""
    content = await data.read()
    result = await uploads_storage.put(f"avatars/{data.filename}", content)
    return {"key": result.key}


@post("/upload/temp")
async def upload_temp(
    data: UploadFile,
    temp_storage: Storage,
) -> dict:
    """Upload temporary file to local storage."""
    content = await data.read()
    result = await temp_storage.put(f"processing/{data.filename}", content)
    return {"key": result.key}


# Application with multiple storages
storages = create_storages()

app = Litestar(
    route_handlers=[upload_avatar, upload_temp],
    plugins=[StoragePlugin(**storages)],
)
```

## Key Points

- **Single interface, multiple backends**: Write code once, run anywhere
- **Environment variables**: Keep configuration out of code
- **Testing isolation**: Use MemoryStorage for fast, isolated tests
- **Gradual migration**: Start with filesystem, move to cloud when ready
- **Named storages**: Use different backends for different purposes

## Configuration Best Practices

1. **Never hardcode credentials**: Use environment variables or IAM roles
2. **Use prefixes**: Separate environments in the same bucket with prefixes
3. **Default to safe**: Default to filesystem/memory in development
4. **Validate early**: Check configuration at startup, not first use
5. **Document requirements**: List required environment variables

## Related

- [File Upload with Validation](file-upload-validation.md) - Validate files regardless of backend
- [Streaming Large Files](streaming-large-files.md) - Handle large files in any backend
- [Image Processing Pipeline](image-processing-pipeline.md) - Process images before cloud storage
