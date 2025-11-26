# Multipart Uploads

Multipart uploads enable efficient handling of large files by splitting them into smaller parts that can be uploaded independently. This provides better reliability, parallel upload capability, and the ability to resume interrupted uploads.

## When to Use Multipart Uploads

Use multipart uploads when:

- **File size exceeds 100MB** - Single uploads become unreliable
- **Network is unstable** - Parts can be retried independently
- **Upload speed matters** - Parts can be uploaded in parallel
- **Resumable uploads needed** - Track progress and resume after failure

For files under 100MB, the standard `put()` method is usually sufficient.

## The put_large() Convenience Method

For most use cases, `put_large()` handles all the complexity automatically:

```python
from litestar_storages import S3Storage, S3Config

storage = S3Storage(S3Config(bucket="my-bucket"))

# Upload a large file - automatically uses multipart
result = await storage.put_large(
    key="backups/database.sql.gz",
    data=large_file_bytes,
    content_type="application/gzip",
)

print(f"Uploaded {result.size} bytes to {result.key}")
```

### put_large() Parameters

```python
result = await storage.put_large(
    key="videos/presentation.mp4",
    data=video_bytes,                    # bytes or AsyncIterator[bytes]
    content_type="video/mp4",            # Optional MIME type
    metadata={"author": "Jane"},         # Optional custom metadata
    part_size=10 * 1024 * 1024,          # Part size (default 10MB)
    progress_callback=my_callback,       # Optional progress tracking
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `key` | `str` | Required | Storage path for the file |
| `data` | `bytes \| AsyncIterator[bytes]` | Required | File content |
| `content_type` | `str \| None` | `None` | MIME type |
| `metadata` | `dict[str, str] \| None` | `None` | Custom metadata |
| `part_size` | `int` | 10MB | Size of each part in bytes |
| `progress_callback` | `ProgressCallback \| None` | `None` | Progress tracking callback |

### Automatic Fallback

`put_large()` intelligently uses regular `put()` for small files:

```python
# Files smaller than part_size use regular put()
small_result = await storage.put_large("small.txt", b"Hello")  # Uses put()

# Files larger than part_size use multipart
large_result = await storage.put_large("large.bin", large_data)  # Uses multipart
```

## Manual Multipart Upload

For fine-grained control, use the multipart upload API directly:

```python
from litestar_storages import S3Storage, S3Config

storage = S3Storage(S3Config(bucket="my-bucket"))

# Step 1: Start the multipart upload
upload = await storage.start_multipart_upload(
    key="large-file.zip",
    content_type="application/zip",
    metadata={"source": "backup-system"},
)

print(f"Started upload: {upload.upload_id}")

# Step 2: Upload parts (must be at least 5MB each, except the last part)
part_size = 10 * 1024 * 1024  # 10MB
data = load_large_file()

part_number = 1
for i in range(0, len(data), part_size):
    part_data = data[i:i + part_size]
    etag = await storage.upload_part(upload, part_number, part_data)
    print(f"Uploaded part {part_number}: {etag}")
    part_number += 1

# Step 3: Complete the upload
result = await storage.complete_multipart_upload(upload)
print(f"Completed: {result.key} ({result.size} bytes)")
```

### MultipartUpload Object

The `MultipartUpload` dataclass tracks upload state:

```python
from litestar_storages import MultipartUpload

@dataclass
class MultipartUpload:
    upload_id: str                              # Unique identifier for the upload
    key: str                                    # Storage key being uploaded to
    parts: list[tuple[int, str]]                # Completed (part_number, etag) pairs
    part_size: int = 5 * 1024 * 1024           # Size of each part (default 5MB)
    total_parts: int | None = None             # Expected total parts (if known)
```

Properties and methods:

```python
upload = await storage.start_multipart_upload("file.zip")

# After uploading some parts...
print(f"Completed parts: {upload.completed_parts}")  # Number of parts uploaded
print(f"Parts list: {upload.parts}")                 # [(1, "etag1"), (2, "etag2"), ...]
```

## Error Handling and Cleanup

Always handle errors to avoid orphaned multipart uploads (which incur storage costs):

```python
upload = await storage.start_multipart_upload("important.dat")

try:
    # Upload parts...
    for part_num, part_data in enumerate(chunks, 1):
        await storage.upload_part(upload, part_num, part_data)

    # Complete the upload
    result = await storage.complete_multipart_upload(upload)

except Exception as e:
    # Clean up on failure
    await storage.abort_multipart_upload(upload)
    raise

```

### Using put_large() for Automatic Cleanup

The `put_large()` method handles cleanup automatically:

```python
try:
    # If this fails partway through, incomplete parts are automatically cleaned up
    result = await storage.put_large("file.zip", data)
except StorageError:
    # No orphaned parts to worry about
    raise
```

## Progress Tracking

Track upload progress using callbacks:

```python
from litestar_storages import ProgressInfo

def show_progress(info: ProgressInfo) -> None:
    """Display upload progress."""
    if info.percentage is not None:
        print(f"Uploading {info.key}: {info.percentage:.1f}%")
    else:
        print(f"Uploading {info.key}: {info.bytes_transferred} bytes")

result = await storage.put_large(
    "large-video.mp4",
    video_data,
    progress_callback=show_progress,
)
```

For detailed progress tracking options, see [Progress Callbacks](progress-callbacks.md).

## Parallel Part Uploads

For maximum upload speed, upload parts in parallel:

```python
import asyncio
from litestar_storages import S3Storage, MultipartUpload

async def upload_parts_parallel(
    storage: S3Storage,
    upload: MultipartUpload,
    data: bytes,
    part_size: int,
    max_concurrent: int = 4,
) -> None:
    """Upload parts in parallel with concurrency limit."""

    semaphore = asyncio.Semaphore(max_concurrent)

    async def upload_part(part_num: int, part_data: bytes) -> None:
        async with semaphore:
            await storage.upload_part(upload, part_num, part_data)

    # Create tasks for all parts
    tasks = []
    part_number = 1
    for i in range(0, len(data), part_size):
        part_data = data[i:i + part_size]
        tasks.append(upload_part(part_number, part_data))
        part_number += 1

    # Run all uploads with concurrency limit
    await asyncio.gather(*tasks)


# Usage
storage = S3Storage(S3Config(bucket="my-bucket"))
upload = await storage.start_multipart_upload("large-file.bin")

try:
    await upload_parts_parallel(storage, upload, large_data, 10 * 1024 * 1024)
    result = await storage.complete_multipart_upload(upload)
except Exception:
    await storage.abort_multipart_upload(upload)
    raise
```

## Resumable Uploads

For truly resumable uploads, persist the upload state:

```python
import json
from pathlib import Path
from litestar_storages import S3Storage, MultipartUpload

class ResumableUpload:
    """Manage resumable multipart uploads."""

    def __init__(self, storage: S3Storage, state_file: Path):
        self.storage = storage
        self.state_file = state_file

    def save_state(self, upload: MultipartUpload) -> None:
        """Persist upload state to disk."""
        state = {
            "upload_id": upload.upload_id,
            "key": upload.key,
            "parts": upload.parts,
            "part_size": upload.part_size,
        }
        self.state_file.write_text(json.dumps(state))

    def load_state(self) -> MultipartUpload | None:
        """Load upload state from disk."""
        if not self.state_file.exists():
            return None

        state = json.loads(self.state_file.read_text())
        return MultipartUpload(
            upload_id=state["upload_id"],
            key=state["key"],
            parts=[tuple(p) for p in state["parts"]],
            part_size=state["part_size"],
        )

    def clear_state(self) -> None:
        """Remove saved state."""
        if self.state_file.exists():
            self.state_file.unlink()

    async def upload(
        self,
        key: str,
        data: bytes,
        part_size: int = 10 * 1024 * 1024,
    ) -> None:
        """Upload with resume capability."""

        # Check for existing upload
        upload = self.load_state()
        start_part = 1

        if upload and upload.key == key:
            # Resume existing upload
            start_part = upload.completed_parts + 1
            print(f"Resuming from part {start_part}")
        else:
            # Start new upload
            upload = await self.storage.start_multipart_upload(key, part_size=part_size)

        try:
            # Upload remaining parts
            for i, part_num in enumerate(range(start_part, -(-len(data) // part_size) + 1)):
                start = (part_num - 1) * part_size
                part_data = data[start:start + part_size]

                await self.storage.upload_part(upload, part_num, part_data)

                # Save state after each part
                self.save_state(upload)
                print(f"Part {part_num} complete")

            # Complete upload
            await self.storage.complete_multipart_upload(upload)
            self.clear_state()

        except Exception:
            # State is already saved - can resume later
            raise


# Usage
storage = S3Storage(S3Config(bucket="my-bucket"))
uploader = ResumableUpload(storage, Path(".upload_state.json"))

await uploader.upload("huge-file.tar.gz", file_data)
```

## Part Size Guidelines

Choose part sizes based on your use case:

| File Size | Recommended Part Size | Reasoning |
|-----------|----------------------|-----------|
| 100MB - 1GB | 10MB | Good balance of parallelism and overhead |
| 1GB - 10GB | 50MB | Fewer parts to manage |
| 10GB+ | 100MB | Minimize API calls |

### S3 Limits

Be aware of S3's multipart upload limits:

- **Minimum part size**: 5MB (except last part)
- **Maximum part size**: 5GB
- **Maximum parts per upload**: 10,000
- **Maximum file size**: 5TB

```python
# The minimum part size is enforced automatically
upload = await storage.start_multipart_upload(
    "file.bin",
    part_size=1024 * 1024,  # 1MB requested
)
# upload.part_size will be 5MB (minimum enforced)
```

## Best Practices

### 1. Use put_large() Unless You Need Control

```python
# Simple and handles errors automatically
result = await storage.put_large("file.zip", data)
```

### 2. Always Clean Up Failed Uploads

```python
# Manual multipart - always use try/finally
upload = await storage.start_multipart_upload("file.zip")
try:
    # ... upload parts ...
    await storage.complete_multipart_upload(upload)
finally:
    if not upload_completed:
        await storage.abort_multipart_upload(upload)
```

### 3. Monitor Incomplete Uploads

Configure S3 lifecycle rules to auto-delete incomplete uploads:

```json
{
    "Rules": [
        {
            "ID": "AbortIncompleteMultipartUploads",
            "Status": "Enabled",
            "Filter": {},
            "AbortIncompleteMultipartUpload": {
                "DaysAfterInitiation": 7
            }
        }
    ]
}
```

### 4. Use Progress Callbacks for User Feedback

```python
async def upload_with_ui(storage: S3Storage, key: str, data: bytes) -> None:
    """Upload with progress feedback."""

    def update_ui(info: ProgressInfo) -> None:
        percent = info.percentage or 0
        print(f"\rUploading: {percent:.0f}%", end="", flush=True)

    await storage.put_large(key, data, progress_callback=update_ui)
    print("\nComplete!")
```

## Backend-Specific Behavior

While all backends support the same multipart upload API, their underlying implementations differ significantly.

### S3 Storage

S3 uses true multipart uploads with server-side part tracking:

- Parts are uploaded directly to S3 and stored until committed
- Each part returns an ETag used to verify integrity
- Minimum part size: 5MB (except last part)
- Maximum parts per upload: 10,000
- Maximum file size: 5TB
- Incomplete uploads incur storage costs until aborted

```python
from litestar_storages import S3Storage, S3Config

storage = S3Storage(S3Config(bucket="my-bucket"))

# S3 natively tracks parts on the server
upload = await storage.start_multipart_upload("large-file.bin")
await storage.upload_part(upload, 1, part_data)  # Stored on S3
result = await storage.complete_multipart_upload(upload)  # Commits parts
```

### Azure Blob Storage

Azure uses Block Blobs with staged blocks:

- Blocks are staged (uploaded) but not visible until committed
- Block IDs are base64-encoded strings (handled automatically)
- Maximum blocks per blob: 50,000
- Maximum block size: 4000MB
- Uncommitted blocks are automatically garbage-collected after 7 days
- No explicit abort needed - uncommitted blocks expire automatically

```python
from litestar_storages import AzureStorage, AzureConfig

storage = AzureStorage(
    AzureConfig(
        container="my-container",
        connection_string="DefaultEndpointsProtocol=https;...",
    )
)

# Azure stages blocks, then commits them as a block list
upload = await storage.start_multipart_upload(
    "large-file.bin",
    part_size=4 * 1024 * 1024,  # 4MB default for Azure
)

# Each part is staged as a block
for part_num, chunk in enumerate(chunks, 1):
    await storage.upload_part(upload, part_num, chunk)

# Commit all blocks as a single blob
result = await storage.complete_multipart_upload(upload)
```

**Azure-specific notes:**

- The `upload_id` is generated client-side (Azure doesn't have a server-side upload ID)
- Content type and metadata are applied when committing the block list
- Aborting is a no-op since uncommitted blocks auto-expire

### Google Cloud Storage

GCS uses a buffering approach since gcloud-aio-storage doesn't expose resumable uploads:

- Parts are buffered in memory until `complete_multipart_upload` is called
- All parts are combined and uploaded as a single request
- Memory usage equals total file size during upload
- Best suited for files up to a few hundred MB

```python
from litestar_storages import GCSStorage, GCSConfig

storage = GCSStorage(
    GCSConfig(
        bucket="my-bucket",
        project="my-project",
    )
)

# GCS buffers parts in memory
upload = await storage.start_multipart_upload(
    "large-file.bin",
    part_size=10 * 1024 * 1024,  # 10MB default
)

# Parts are buffered locally
for part_num, chunk in enumerate(chunks, 1):
    await storage.upload_part(upload, part_num, chunk)  # Stored in memory

# All buffered data is uploaded at once
result = await storage.complete_multipart_upload(upload)  # Single upload
```

**GCS-specific notes:**

- Memory consumption: buffering means total file data is held in memory
- For very large files (multi-GB), consider using GCS's native resumable upload API directly
- Aborting simply clears the buffered data from memory
- No server-side storage until the upload is completed

### Backend Comparison

| Feature | S3 | Azure | GCS |
|---------|-----|-------|-----|
| Server-side part storage | Yes | Yes (staged blocks) | No (memory buffer) |
| Minimum part size | 5MB | None | None |
| Maximum part size | 5GB | 4000MB | N/A |
| Maximum parts | 10,000 | 50,000 | N/A |
| Maximum file size | 5TB | ~190TB | Memory-limited |
| Cleanup required | Yes (abort or lifecycle) | Auto (7 days) | No |
| Memory efficiency | High | High | Low |
| Resume after restart | Yes | Yes (with block IDs) | No |

## Choosing the Right Approach

### Use `put_large()` when:

- You want automatic handling of chunking and errors
- File sizes are under a few GB
- You don't need to resume uploads across restarts

```python
# Recommended for most cases
result = await storage.put_large("file.bin", data, progress_callback=show_progress)
```

### Use manual multipart when:

- You need resumable uploads that survive application restarts (S3/Azure only)
- You want parallel part uploads for maximum speed
- You need fine-grained control over part sizes and timing

```python
# For advanced control
upload = await storage.start_multipart_upload("file.bin")
# ... custom upload logic ...
await storage.complete_multipart_upload(upload)
```

### Consider regular `put()` when:

- Files are under 100MB
- Network is reliable
- Simplicity is more important than resumability

```python
# For smaller files
result = await storage.put("file.bin", data)
```

## Next Steps

- Learn about [progress callbacks](progress-callbacks.md) for detailed progress tracking
- Explore [retry utilities](retry.md) for reliable uploads
- See [S3 storage](../backends/s3.md) for full S3Storage documentation
- See [Azure storage](../backends/azure.md) for Azure-specific features
- See [GCS storage](../backends/gcs.md) for Google Cloud Storage details
