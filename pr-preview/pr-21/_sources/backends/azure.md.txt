# Azure Blob Storage

The `AzureStorage` backend stores files in Microsoft Azure Blob Storage. It supports SAS URL generation, server-side operations, and streaming for efficient handling of large files.

## Installation

Install with the Azure extra:

```bash
pip install litestar-storages[azure]
```

This installs `azure-storage-blob` for async blob operations. For managed identity authentication, you will also need `azure-identity`:

```bash
pip install litestar-storages[azure] azure-identity
```

## Configuration

### AzureConfig Options

```python
from datetime import timedelta
from litestar_storages import AzureStorage, AzureConfig

config = AzureConfig(
    container="my-container",                    # Required: container name
    account_url=None,                            # Optional: storage account URL
    account_key=None,                            # Optional: storage account key
    connection_string=None,                      # Optional: full connection string
    prefix="",                                   # Optional: key prefix for all operations
    presigned_expiry=timedelta(hours=1),         # Optional: default SAS URL expiration
)

storage = AzureStorage(config)
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `container` | `str` | Required | Azure Blob container name |
| `account_url` | `str \| None` | `None` | Storage account URL (e.g., `https://<account>.blob.core.windows.net`) |
| `account_key` | `str \| None` | `None` | Storage account access key |
| `connection_string` | `str \| None` | `None` | Full connection string (alternative to account_url + account_key) |
| `prefix` | `str` | `""` | Key prefix applied to all operations |
| `presigned_expiry` | `timedelta` | 1 hour | Default expiration for SAS URLs |

## Authentication Methods

Azure Storage supports several authentication methods. Choose the one that best fits your deployment scenario.

### Connection String

The simplest method for development and testing. Find your connection string in the Azure Portal under Storage Account > Access keys.

```python
from litestar_storages import AzureStorage, AzureConfig

storage = AzureStorage(
    config=AzureConfig(
        container="my-container",
        connection_string="DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=...;EndpointSuffix=core.windows.net",
    )
)
```

### Account URL + Account Key

Explicit credential configuration:

```python
storage = AzureStorage(
    config=AzureConfig(
        container="my-container",
        account_url="https://myaccount.blob.core.windows.net",
        account_key="your-storage-account-key",
    )
)
```

### DefaultAzureCredential (Managed Identity)

When running on Azure infrastructure (App Service, Functions, AKS, VMs), use managed identity for secure, credential-free authentication:

```python
# No account_key needed - uses DefaultAzureCredential
storage = AzureStorage(
    config=AzureConfig(
        container="my-container",
        account_url="https://myaccount.blob.core.windows.net",
        # account_key omitted - will use DefaultAzureCredential
    )
)
```

This requires the `azure-identity` package:

```bash
pip install azure-identity
```

DefaultAzureCredential automatically tries multiple authentication methods in order:

1. Environment variables (`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`)
2. Managed Identity (system-assigned or user-assigned)
3. Azure CLI credentials
4. Azure PowerShell credentials
5. Visual Studio Code credentials

### Running on Azure (Auto-Detection)

When deployed to Azure services with managed identity enabled, authentication is automatic:

```python
import os

storage = AzureStorage(
    config=AzureConfig(
        container=os.environ["AZURE_STORAGE_CONTAINER"],
        account_url=os.environ["AZURE_STORAGE_ACCOUNT_URL"],
        # Credentials automatically discovered from managed identity
    )
)
```

**Required Azure RBAC role:** Assign "Storage Blob Data Contributor" to your managed identity:

```bash
# Using Azure CLI
az role assignment create \
    --assignee <managed-identity-principal-id> \
    --role "Storage Blob Data Contributor" \
    --scope /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Storage/storageAccounts/<storage-account>
```

### Azurite Emulator Support

For local development without an Azure subscription, use the Azurite emulator:

```python
# Azurite default credentials
storage = AzureStorage(
    config=AzureConfig(
        container="test-container",
        connection_string=(
            "DefaultEndpointsProtocol=http;"
            "AccountName=devstoreaccount1;"
            "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
            "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1"
        ),
    )
)
```

## Usage Examples

### Basic Upload and Download

```python
from litestar import post, get
from litestar.datastructures import UploadFile
from litestar_storages import Storage


@post("/upload")
async def upload_file(
    data: UploadFile,
    storage: Storage,
) -> dict:
    """Upload a file to Azure Blob Storage."""
    content = await data.read()

    result = await storage.put(
        key=f"uploads/{data.filename}",
        data=content,
        content_type=data.content_type,
        metadata={
            "original-name": data.filename,
            "uploaded-by": "user-123",
        },
    )

    return {
        "key": result.key,
        "size": result.size,
        "content_type": result.content_type,
    }


@get("/files/{key:path}")
async def download_file(
    key: str,
    storage: Storage,
) -> bytes:
    """Download a file from Azure Blob Storage."""
    return await storage.get_bytes(key)
```

### SAS URL Generation

SAS (Shared Access Signature) URLs provide time-limited access to private blobs without exposing credentials.

```python
from datetime import timedelta

# Use default expiration (from config)
url = await storage.url("documents/report.pdf")

# Custom expiration
url = await storage.url(
    "documents/report.pdf",
    expires_in=timedelta(minutes=15),
)

# Long-lived URL (use sparingly)
url = await storage.url(
    "public/image.jpg",
    expires_in=timedelta(days=7),
)
```

**SAS URL Patterns:**

```python
from litestar import get
from litestar.response import Redirect
from litestar_storages import Storage


@get("/files/{key:path}/download-url")
async def get_download_url(
    key: str,
    storage: Storage,
) -> dict[str, str]:
    """Generate a temporary download URL."""
    url = await storage.url(key, expires_in=timedelta(minutes=30))
    return {"download_url": url, "expires_in": "30 minutes"}


@get("/files/{key:path}/download")
async def download_file(
    key: str,
    storage: Storage,
) -> Redirect:
    """Redirect to SAS URL for download."""
    url = await storage.url(key, expires_in=timedelta(minutes=5))
    return Redirect(url)
```

**Note:** SAS URL generation requires an account key. It does not work with managed identity alone.

### Using with Prefix

Organize files within a container using prefixes:

```python
# All operations prefixed with "app-name/uploads/"
storage = AzureStorage(
    config=AzureConfig(
        container="shared-container",
        connection_string="...",
        prefix="app-name/uploads/",
    )
)

# Stores at: app-name/uploads/images/photo.jpg
await storage.put("images/photo.jpg", data)

# Lists only files under the prefix
async for file in storage.list("images/"):
    print(file.key)  # Returns "images/photo.jpg", not full path
```

Use cases for prefixes:

- Multiple applications sharing a container
- Environment separation (production/, staging/)
- Tenant isolation in multi-tenant applications

### Streaming Large Files

Stream files directly from Azure without loading entirely into memory:

```python
from litestar import get
from litestar.response import Stream


@get("/files/{key:path}")
async def stream_file(
    key: str,
    storage: Storage,
) -> Stream:
    """Stream a file directly from Azure."""
    info = await storage.info(key)

    return Stream(
        storage.get(key),
        media_type=info.content_type or "application/octet-stream",
        headers={
            "Content-Length": str(info.size),
            "Content-Disposition": f'attachment; filename="{key.split("/")[-1]}"',
        },
    )
```

### Copy and Move Operations

```python
async def archive_file(key: str, storage: Storage) -> StoredFile:
    """Copy a file to the archive folder."""
    return await storage.copy(f"active/{key}", f"archive/{key}")


async def publish_draft(key: str, storage: Storage) -> StoredFile:
    """Move a file from drafts to published."""
    return await storage.move(f"drafts/{key}", f"published/{key}")
```

## Azurite Emulator Setup

Azurite is the official Azure Storage emulator for local development.

### Docker Setup

```bash
# Run Azurite with persistent storage
docker run -d \
    --name azurite \
    -p 10000:10000 \
    -p 10001:10001 \
    -p 10002:10002 \
    -v azurite-data:/data \
    mcr.microsoft.com/azure-storage/azurite

# Create a container (using Azure CLI)
az storage container create \
    --name test-container \
    --connection-string "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1"
```

### Docker Compose

```yaml
version: "3.8"

services:
  azurite:
    image: mcr.microsoft.com/azure-storage/azurite
    ports:
      - "10000:10000"  # Blob service
      - "10001:10001"  # Queue service
      - "10002:10002"  # Table service
    volumes:
      - azurite-data:/data
    command: "azurite --blobHost 0.0.0.0 --queueHost 0.0.0.0 --tableHost 0.0.0.0"

volumes:
  azurite-data:
```

### Azurite Configuration

```python
import os

# Development configuration
AZURITE_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=http;"
    "AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1"
)

# Use environment to switch between local and production
def get_storage() -> AzureStorage:
    if os.environ.get("ENVIRONMENT") == "production":
        return AzureStorage(
            config=AzureConfig(
                container=os.environ["AZURE_STORAGE_CONTAINER"],
                account_url=os.environ["AZURE_STORAGE_ACCOUNT_URL"],
            )
        )
    else:
        return AzureStorage(
            config=AzureConfig(
                container="test-container",
                connection_string=AZURITE_CONNECTION_STRING,
            )
        )
```

## Best Practices

### Credential Management

**Credential Hierarchy:**

AzureStorage uses credentials in this order:

1. Explicit `connection_string` in config
2. Explicit `account_url` + `account_key` in config
3. `account_url` with DefaultAzureCredential (managed identity, environment, CLI)

**Recommended approach by environment:**

| Environment | Credential Method |
|-------------|-------------------|
| Local development | Azurite or connection string |
| CI/CD | Environment variables (secrets) |
| Azure App Service | Managed Identity |
| Azure Functions | Managed Identity |
| Azure Kubernetes (AKS) | Workload Identity |

### Environment Variable Configuration

```bash
# For connection string auth
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=..."

# For account URL + key auth
export AZURE_STORAGE_ACCOUNT_URL="https://myaccount.blob.core.windows.net"
export AZURE_STORAGE_ACCOUNT_KEY="your-account-key"
export AZURE_STORAGE_CONTAINER="my-container"

# For managed identity (DefaultAzureCredential)
export AZURE_STORAGE_ACCOUNT_URL="https://myaccount.blob.core.windows.net"
export AZURE_STORAGE_CONTAINER="my-container"
# No key needed - uses managed identity
```

### Never Commit Credentials

```python
# BAD - credentials in code
storage = AzureStorage(AzureConfig(
    container="my-container",
    account_key="super-secret-key",  # Never do this!
))

# GOOD - credentials from environment
import os

storage = AzureStorage(AzureConfig(
    container=os.environ["AZURE_STORAGE_CONTAINER"],
    connection_string=os.environ.get("AZURE_STORAGE_CONNECTION_STRING"),
))
```

### Container Naming Rules

Azure container names must:

- Be 3-63 characters long
- Start with a letter or number
- Contain only lowercase letters, numbers, and hyphens
- Not have consecutive hyphens

```python
# Valid names
"my-container"
"uploads2024"
"app-data-prod"

# Invalid names
"My-Container"      # No uppercase
"my--container"     # No consecutive hyphens
"-my-container"     # Must start with letter/number
"ab"                # Too short
```

## Error Handling

```python
from litestar_storages import (
    StorageError,
    StorageFileNotFoundError,
    ConfigurationError,
    StorageConnectionError,
)


async def safe_download(key: str, storage: Storage) -> bytes | None:
    """Download a file with error handling."""
    try:
        return await storage.get_bytes(key)
    except StorageFileNotFoundError:
        return None
    except StorageConnectionError as e:
        logger.error(f"Connection error: {e}")
        raise
    except StorageError as e:
        logger.error(f"Storage error: {e}")
        raise


async def safe_delete(key: str, storage: Storage) -> bool:
    """Delete a file, returning False if it doesn't exist."""
    # Note: Azure delete raises an error for non-existent blobs
    if not await storage.exists(key):
        return False
    await storage.delete(key)
    return True
```

### Common Error Scenarios

| Error | Cause | Solution |
|-------|-------|----------|
| `ConfigurationError` | Missing container name or credentials | Check config parameters |
| `StorageConnectionError` | Network issues or invalid endpoint | Verify account URL and network |
| `StorageFileNotFoundError` | Blob does not exist | Check key and prefix |
| `StorageError` (with "AuthenticationFailed") | Invalid credentials | Verify account key or connection string |

## Azure-Specific Considerations

### Delete Behavior

Unlike S3 and GCS, Azure Blob Storage raises an error when deleting a non-existent blob. Use `exists()` first for idempotent deletes:

```python
async def idempotent_delete(key: str, storage: Storage) -> None:
    """Delete a file without raising if it doesn't exist."""
    if await storage.exists(key):
        await storage.delete(key)
```

### SAS URL Limitations

- SAS URLs require an account key (cannot be generated with managed identity alone)
- For managed identity scenarios, consider using Azure CDN with private endpoints
- SAS tokens should be short-lived for security

### Blob Types

AzureStorage uses block blobs, which are suitable for most file storage scenarios. For append-only logs or page blobs (VHDs), you would need direct Azure SDK usage.

## Large File Uploads

For files larger than 100MB, use `put_large()` or the manual multipart upload API. Azure implements multipart uploads using Block Blobs, where blocks are staged individually and then committed as a single blob.

### Using put_large()

The simplest way to upload large files with automatic chunking and progress tracking:

```python
from litestar_storages import AzureStorage, AzureConfig, ProgressInfo

storage = AzureStorage(
    AzureConfig(
        container="my-container",
        connection_string="DefaultEndpointsProtocol=https;...",
    )
)

# Upload a large file with automatic chunking
result = await storage.put_large(
    key="backups/database-dump.sql.gz",
    data=large_file_bytes,
    content_type="application/gzip",
    metadata={"source": "daily-backup"},
    part_size=4 * 1024 * 1024,  # 4MB blocks (Azure default)
)

print(f"Uploaded {result.size} bytes to {result.key}")
```

### Progress Tracking

Monitor upload progress with a callback function:

```python
from litestar_storages import ProgressInfo


def show_progress(info: ProgressInfo) -> None:
    """Display upload progress."""
    if info.percentage is not None:
        bar_length = 40
        filled = int(bar_length * info.percentage / 100)
        bar = "=" * filled + "-" * (bar_length - filled)
        print(f"\r[{bar}] {info.percentage:.1f}%", end="", flush=True)


async def upload_with_progress(storage: AzureStorage, key: str, data: bytes) -> None:
    """Upload a large file with progress display."""
    result = await storage.put_large(
        key=key,
        data=data,
        progress_callback=show_progress,
    )
    print(f"\nComplete! Uploaded {result.size} bytes")


# Usage
await upload_with_progress(storage, "videos/presentation.mp4", video_data)
```

### Manual Multipart Upload

For fine-grained control over the upload process:

```python
from litestar_storages import AzureStorage, AzureConfig

storage = AzureStorage(
    AzureConfig(
        container="my-container",
        connection_string="...",
    )
)

# Step 1: Start the upload
upload = await storage.start_multipart_upload(
    key="large-archive.tar.gz",
    content_type="application/gzip",
    metadata={"created-by": "backup-service"},
    part_size=8 * 1024 * 1024,  # 8MB blocks
)

# Step 2: Upload blocks
block_size = 8 * 1024 * 1024
data = load_large_file()

try:
    for part_num in range(1, (len(data) // block_size) + 2):
        start = (part_num - 1) * block_size
        block_data = data[start:start + block_size]
        if not block_data:
            break

        block_id = await storage.upload_part(upload, part_num, block_data)
        print(f"Uploaded block {part_num}: {block_id}")

    # Step 3: Commit the block list
    result = await storage.complete_multipart_upload(upload)
    print(f"Upload complete: {result.key}")

except Exception as e:
    # Azure auto-cleans uncommitted blocks after 7 days
    # Explicit abort is optional but releases tracking resources
    await storage.abort_multipart_upload(upload)
    raise
```

### Azure Block Blob Limits

| Limit | Value |
|-------|-------|
| Maximum blocks per blob | 50,000 |
| Maximum block size | 4000 MB |
| Maximum blob size | ~190 TB |
| Block ID length | Must be consistent across all blocks |
| Uncommitted block lifetime | 7 days (auto-cleanup) |

### Block Size Recommendations

| File Size | Recommended Block Size | Reasoning |
|-----------|----------------------|-----------|
| 100MB - 1GB | 4MB (default) | Good parallelism, reasonable overhead |
| 1GB - 10GB | 8-16MB | Fewer blocks to manage |
| 10GB+ | 32-64MB | Minimize API calls |

```python
# Adjust block size based on file size
def get_optimal_block_size(file_size: int) -> int:
    """Calculate optimal block size for Azure uploads."""
    if file_size < 1 * 1024 * 1024 * 1024:  # < 1GB
        return 4 * 1024 * 1024  # 4MB
    elif file_size < 10 * 1024 * 1024 * 1024:  # < 10GB
        return 16 * 1024 * 1024  # 16MB
    else:
        return 64 * 1024 * 1024  # 64MB


# Usage
block_size = get_optimal_block_size(len(data))
result = await storage.put_large(key, data, part_size=block_size)
```

## Next Steps

- Learn about [Memory storage](memory.md) for testing Azure code without Azure
- Explore [Filesystem storage](filesystem.md) for local development
- Create [custom backends](../advanced/custom-backends.md) for other cloud providers
