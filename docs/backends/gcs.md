# GCS Storage

The `GCSStorage` backend stores files in Google Cloud Storage. It provides async operations using `gcloud-aio-storage`, supports signed URLs for temporary access, and works seamlessly with Google Cloud's authentication mechanisms.

## When to Use GCS Storage

**Ideal for:**

- Applications deployed on Google Cloud Platform (GKE, Cloud Run, Compute Engine)
- Teams already using the Google Cloud ecosystem
- Workloads that benefit from GCS features (lifecycle policies, multi-regional storage)
- Integration with other Google Cloud services (BigQuery, Dataflow, etc.)

## Installation

Install with the GCS extra:

```bash
pip install litestar-storages[gcs]
```

This installs `gcloud-aio-storage` for async GCS operations.

## Configuration

### GCSConfig Options

```python
from datetime import timedelta
from litestar_storages import GCSStorage, GCSConfig

config = GCSConfig(
    bucket="my-bucket",                       # Required: GCS bucket name
    project="my-gcp-project",                 # Optional: GCP project ID
    service_file="/path/to/credentials.json", # Optional: service account key
    prefix="",                                # Optional: key prefix for all operations
    presigned_expiry=timedelta(hours=1),      # Optional: default URL expiration
    api_root=None,                            # Optional: custom endpoint (for emulators)
)

storage = GCSStorage(config)
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `bucket` | `str` | Required | GCS bucket name |
| `project` | `str \| None` | `None` | GCP project ID (required for some operations) |
| `service_file` | `str \| None` | `None` | Path to service account JSON key file |
| `prefix` | `str` | `""` | Key prefix applied to all operations |
| `presigned_expiry` | `timedelta` | 1 hour | Default expiration for signed URLs |
| `api_root` | `str \| None` | `None` | Custom API endpoint (for emulators like fake-gcs-server) |

## Authentication Methods

GCSStorage supports multiple authentication methods, automatically detecting credentials when possible.

### Service Account JSON File

The most explicit method - provide a path to your service account key file:

```python
from litestar_storages import GCSStorage, GCSConfig

storage = GCSStorage(
    config=GCSConfig(
        bucket="my-app-uploads",
        service_file="/path/to/service-account.json",
    )
)
```

Create a service account in the Google Cloud Console:

1. Go to IAM & Admin > Service Accounts
2. Create a new service account
3. Grant the "Storage Object Admin" role (or more restrictive roles as needed)
4. Create a key and download the JSON file

Required IAM roles for full functionality:

```
roles/storage.objectViewer    # For read operations (get, list, exists)
roles/storage.objectCreator   # For write operations (put)
roles/storage.objectAdmin     # For all operations including delete and copy
```

Minimal custom role permissions:

```
storage.objects.create
storage.objects.delete
storage.objects.get
storage.objects.list
storage.buckets.get
```

### Application Default Credentials (ADC)

When no explicit credentials are provided, GCSStorage uses Application Default Credentials:

```python
# Uses ADC automatically
storage = GCSStorage(
    config=GCSConfig(
        bucket="my-app-uploads",
        project="my-gcp-project",
    )
)
```

Set up ADC locally with the gcloud CLI:

```bash
# Authenticate with your user account
gcloud auth application-default login

# Or use a service account
gcloud auth activate-service-account \
    --key-file=/path/to/service-account.json
```

### Running on GCP (Auto-Detection)

When running on GCP infrastructure, credentials are automatically available:

```python
# No credentials needed on GKE, Cloud Run, Compute Engine, etc.
storage = GCSStorage(
    config=GCSConfig(
        bucket="my-app-uploads",
        # Credentials auto-detected from environment
    )
)
```

**Compute Engine / GKE:** Uses the service account attached to the VM or node pool.

**Cloud Run:** Uses the service account configured for the Cloud Run service.

**Cloud Functions:** Uses the function's service account.

Ensure the service account has the necessary Storage permissions.

### Emulator Support (fake-gcs-server)

For local development and testing, use the `api_root` option to connect to an emulator:

```python
storage = GCSStorage(
    config=GCSConfig(
        bucket="test-bucket",
        api_root="http://localhost:4443",
    )
)
```

See the [Emulator Setup](#emulator-setup-for-testing) section for running fake-gcs-server.

## Usage Examples

### Basic Upload and Download

```python
from litestar_storages import GCSStorage, GCSConfig

storage = GCSStorage(
    config=GCSConfig(
        bucket="my-bucket",
        project="my-project",
    )
)

# Upload a file
result = await storage.put(
    "documents/report.pdf",
    b"PDF content here...",
    content_type="application/pdf",
    metadata={"author": "Jane Doe", "version": "1.0"},
)
print(f"Uploaded: {result.key}, size: {result.size}, etag: {result.etag}")

# Check if file exists
exists = await storage.exists("documents/report.pdf")

# Download as bytes
content = await storage.get_bytes("documents/report.pdf")

# Get file info without downloading
info = await storage.info("documents/report.pdf")
print(f"Size: {info.size}, Type: {info.content_type}")

# Delete the file
await storage.delete("documents/report.pdf")
```

### Signed URLs

Signed URLs provide temporary access to private files without exposing credentials:

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

**Generating download links in API responses:**

```python
from litestar import get
from litestar_storages import Storage


@get("/files/{key:path}/download-url")
async def get_download_url(
    key: str,
    storage: Storage,
) -> dict[str, str]:
    """Generate a temporary download URL."""
    url = await storage.url(key, expires_in=timedelta(minutes=30))
    return {"download_url": url, "expires_in": "30 minutes"}
```

**Direct browser downloads:**

```python
from litestar import get
from litestar.response import Redirect


@get("/files/{key:path}/download")
async def download_file(
    key: str,
    storage: Storage,
) -> Redirect:
    """Redirect to signed URL for download."""
    url = await storage.url(key, expires_in=timedelta(minutes=5))
    return Redirect(url)
```

### Using with Prefix

Prefixes help organize files within a single bucket:

```python
# All operations will be prefixed with "app-name/uploads/"
storage = GCSStorage(
    config=GCSConfig(
        bucket="shared-bucket",
        prefix="app-name/uploads/",
    )
)

# Stores at: gs://shared-bucket/app-name/uploads/images/photo.jpg
await storage.put("images/photo.jpg", data)

# Lists only files under the prefix
async for file in storage.list("images/"):
    print(file.key)  # Returns "images/photo.jpg", not full path
```

This is useful for:

- Multiple applications sharing a bucket
- Environment separation (production/, staging/)
- Tenant isolation in multi-tenant applications

### Streaming Large Files

```python
from litestar import get
from litestar.response import Stream


@get("/files/{key:path}")
async def stream_file(
    key: str,
    storage: Storage,
) -> Stream:
    """Stream a file directly from GCS."""
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

### File Upload with Metadata

```python
from litestar import post
from litestar.datastructures import UploadFile
from litestar_storages import Storage, StoredFile


@post("/upload")
async def upload_file(
    data: UploadFile,
    storage: Storage,
) -> dict:
    """Upload a file and return download URL."""
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

    download_url = await storage.url(result.key, expires_in=timedelta(hours=24))

    return {
        "key": result.key,
        "size": result.size,
        "content_type": result.content_type,
        "download_url": download_url,
    }
```

### Listing Files

```python
# List all files
async for file in storage.list():
    print(f"{file.key}: {file.size} bytes")

# List files with a prefix filter
async for file in storage.list("images/"):
    print(f"{file.key}: {file.content_type}")

# Limit results
async for file in storage.list(limit=10):
    print(file.key)
```

### Copy and Move Operations

```python
from litestar_storages import StoredFile


async def publish_draft(key: str, storage: Storage) -> StoredFile:
    """Move a file from drafts to published."""
    source = f"drafts/{key}"
    destination = f"published/{key}"

    result = await storage.copy(source, destination)
    await storage.delete(source)

    return result


# Or use the built-in move method
async def archive_file(key: str, storage: Storage) -> StoredFile:
    """Move a file to the archive."""
    return await storage.move(key, f"archive/{key}")
```

## Emulator Setup for Testing

Use [fake-gcs-server](https://github.com/fsouza/fake-gcs-server) for local testing without GCP credentials.

### Running with Docker

```bash
# Start fake-gcs-server
docker run -d \
    --name fake-gcs \
    -p 4443:4443 \
    -v $(pwd)/gcs-data:/data \
    fsouza/fake-gcs-server:latest \
    -scheme http \
    -port 4443

# Create a test bucket (optional - fake-gcs-server auto-creates buckets)
curl -X POST "http://localhost:4443/storage/v1/b?project=test-project" \
    -H "Content-Type: application/json" \
    -d '{"name": "test-bucket"}'
```

### Configuring GCSStorage for Emulator

```python
storage = GCSStorage(
    config=GCSConfig(
        bucket="test-bucket",
        api_root="http://localhost:4443",
        # No service_file needed for emulator
    )
)
```

### Pytest Fixture Example

```python
import pytest
import subprocess
import time
from litestar_storages import GCSStorage, GCSConfig


@pytest.fixture(scope="session")
def gcs_emulator():
    """Start fake-gcs-server for the test session."""
    container = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", "test-gcs",
            "-p", "4443:4443",
            "fsouza/fake-gcs-server:latest",
            "-scheme", "http",
            "-port", "4443",
        ],
        capture_output=True,
        text=True,
    )
    container_id = container.stdout.strip()
    time.sleep(2)  # Wait for server to start

    yield "http://localhost:4443"

    # Cleanup
    subprocess.run(["docker", "stop", container_id])
    subprocess.run(["docker", "rm", container_id])


@pytest.fixture
async def gcs_storage(gcs_emulator):
    """Provide GCS storage connected to emulator."""
    storage = GCSStorage(
        config=GCSConfig(
            bucket="test-bucket",
            api_root=gcs_emulator,
        )
    )
    yield storage
    await storage.close()


async def test_upload_download(gcs_storage):
    """Test file upload and download."""
    await gcs_storage.put("test.txt", b"Hello, GCS!")
    content = await gcs_storage.get_bytes("test.txt")
    assert content == b"Hello, GCS!"
```

### Docker Compose Setup

```yaml
# docker-compose.yml
services:
  fake-gcs:
    image: fsouza/fake-gcs-server:latest
    command: ["-scheme", "http", "-port", "4443"]
    ports:
      - "4443:4443"
    volumes:
      - gcs-data:/data

volumes:
  gcs-data:
```

## Best Practices and Credential Management

### Credential Hierarchy

GCSStorage uses credentials in this order:

1. Explicit `service_file` in config
2. `GOOGLE_APPLICATION_CREDENTIALS` environment variable
3. Application Default Credentials (ADC)
4. Metadata server (when running on GCP)

**Recommended approach by environment:**

| Environment | Credential Method |
|-------------|-------------------|
| Local development | ADC via `gcloud auth application-default login` |
| CI/CD | Service account JSON (as secret) |
| GKE | Workload Identity |
| Cloud Run | Service account attached to the service |
| Compute Engine | Service account attached to the VM |

### Environment Variable Configuration

```bash
# Set service account credentials via environment variable
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# Set default project
export GCLOUD_PROJECT="my-gcp-project"
```

### Never Commit Credentials

```python
# BAD - credentials path hardcoded
storage = GCSStorage(GCSConfig(
    bucket="my-bucket",
    service_file="/home/user/my-service-account.json",  # Never do this!
))

# GOOD - credentials from environment
import os

storage = GCSStorage(GCSConfig(
    bucket=os.environ["GCS_BUCKET"],
    project=os.environ.get("GCP_PROJECT"),
    # Credentials loaded via ADC or GOOGLE_APPLICATION_CREDENTIALS
))
```

### Workload Identity (GKE)

For GKE deployments, use Workload Identity instead of service account keys:

```yaml
# Kubernetes ServiceAccount with Workload Identity
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app
  annotations:
    iam.gke.io/gcp-service-account: my-app@my-project.iam.gserviceaccount.com
```

```python
# No credentials needed - Workload Identity provides them
storage = GCSStorage(
    config=GCSConfig(
        bucket="my-bucket",
    )
)
```

### Principle of Least Privilege

Create custom IAM roles with minimal required permissions:

```yaml
# custom-storage-role.yaml
title: "Custom Storage Writer"
description: "Minimal permissions for application storage"
stage: GA
includedPermissions:
  - storage.objects.create
  - storage.objects.get
  - storage.objects.delete
  - storage.objects.list
```

## Error Handling

```python
from litestar_storages import (
    StorageError,
    StorageFileNotFoundError,
    StorageConnectionError,
    ConfigurationError,
)


async def safe_download(key: str, storage: Storage) -> bytes | None:
    """Download a file with comprehensive error handling."""
    try:
        return await storage.get_bytes(key)
    except StorageFileNotFoundError:
        # File does not exist
        return None
    except StorageConnectionError as e:
        # Network or authentication issues
        logger.error(f"Connection error: {e}")
        raise
    except ConfigurationError as e:
        # Missing dependencies or invalid config
        logger.error(f"Configuration error: {e}")
        raise
    except StorageError as e:
        # Generic storage error
        logger.error(f"Storage error: {e}")
        raise
```

### Common Error Scenarios

| Error | Cause | Solution |
|-------|-------|----------|
| `ConfigurationError` | Missing gcloud-aio-storage | `pip install litestar-storages[gcs]` |
| `ConfigurationError` | Empty bucket name | Provide a valid bucket name |
| `StorageFileNotFoundError` | File does not exist | Check the key and prefix |
| `StorageConnectionError` | Invalid credentials | Verify service account or ADC |
| `StorageError` | Signed URL failure | Ensure service account has signing permissions |

## Comparison with Other Backends

| Feature | GCSStorage | S3Storage | FileSystemStorage |
|---------|------------|-----------|-------------------|
| Setup complexity | Moderate | Moderate | Simple |
| Multi-region | Native | Via replication | No |
| Signed URLs | Yes | Yes (presigned) | With base_url only |
| Streaming | Yes | Yes | Yes |
| GCP integration | Native | Via S3-compatible API | No |
| Local testing | fake-gcs-server | moto/MinIO | Directory |

## Next Steps

- Learn about [Memory storage](memory.md) for testing without external dependencies
- Explore [S3 storage](s3.md) for AWS or S3-compatible services
- Review [FileSystem storage](filesystem.md) for local deployments
- Create [custom backends](../advanced/custom-backends.md) for other cloud providers
