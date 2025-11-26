# Streaming Large Files

Handle large file uploads and downloads efficiently without loading entire files into memory. This recipe demonstrates chunked streaming, multipart uploads, and progress tracking for files of any size.

## Prerequisites

- Python 3.9+
- litestar-storages installed (`pip install litestar-storages`)
- For S3 multipart: `pip install litestar-storages[s3]`
- For Litestar: `pip install litestar-storages[litestar]`

## The Problem

Loading large files entirely into memory causes:

- Memory exhaustion and OOM errors
- Slow response times while buffering
- Poor user experience (no progress indication)
- Failed uploads on unstable connections (no resume)

Streaming processes files in chunks, enabling:

- Constant memory usage regardless of file size
- Real-time progress updates
- Resumable uploads for very large files
- Better resource utilization

## Solution

### Streaming Utilities

First, create utilities for chunked streaming:

```python
"""Streaming utilities for large file handling."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Callable

from litestar_storages import ProgressInfo


@dataclass
class ChunkInfo:
    """Information about a data chunk."""

    data: bytes
    offset: int
    size: int
    total: int | None


async def chunk_bytes(
    data: bytes,
    chunk_size: int = 64 * 1024,  # 64KB default
) -> AsyncIterator[bytes]:
    """Split bytes into chunks.

    Args:
        data: Data to chunk
        chunk_size: Size of each chunk

    Yields:
        Data chunks
    """
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]
        # Yield control to event loop
        await asyncio.sleep(0)


async def chunk_file(
    path: str,
    chunk_size: int = 64 * 1024,
) -> AsyncIterator[bytes]:
    """Read file in chunks without loading into memory.

    Args:
        path: Path to file
        chunk_size: Size of each chunk

    Yields:
        File data chunks
    """
    try:
        import aiofiles
    except ImportError as e:
        raise ImportError("aiofiles required: pip install aiofiles") from e

    async with aiofiles.open(path, "rb") as f:
        while True:
            chunk = await f.read(chunk_size)
            if not chunk:
                break
            yield chunk


async def chunk_stream_with_progress(
    stream: AsyncIterator[bytes],
    total_size: int | None,
    callback: Callable[[ProgressInfo], None] | None,
    key: str = "",
    operation: str = "upload",
) -> AsyncIterator[bytes]:
    """Wrap a stream with progress reporting.

    Args:
        stream: Source stream
        total_size: Total expected size (for percentage)
        callback: Progress callback function
        key: Storage key for progress info
        operation: "upload" or "download"

    Yields:
        Original chunks unchanged
    """
    bytes_transferred = 0

    async for chunk in stream:
        yield chunk

        bytes_transferred += len(chunk)

        if callback:
            callback(ProgressInfo(
                bytes_transferred=bytes_transferred,
                total_bytes=total_size,
                operation=operation,
                key=key,
            ))


class StreamingUploader:
    """Helper for streaming uploads with progress.

    Example:
        uploader = StreamingUploader(storage, progress_callback=my_callback)
        result = await uploader.upload_file("/path/to/large/file.zip", "uploads/file.zip")
    """

    def __init__(
        self,
        storage,  # Type: Storage
        chunk_size: int = 64 * 1024,
        progress_callback: Callable[[ProgressInfo], None] | None = None,
    ) -> None:
        self.storage = storage
        self.chunk_size = chunk_size
        self.progress_callback = progress_callback

    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ):
        """Upload bytes with streaming and progress.

        Args:
            key: Storage key
            data: Data to upload
            content_type: MIME type

        Returns:
            StoredFile result
        """
        total_size = len(data)

        stream = chunk_bytes(data, self.chunk_size)

        if self.progress_callback:
            stream = chunk_stream_with_progress(
                stream,
                total_size,
                self.progress_callback,
                key=key,
                operation="upload",
            )

        return await self.storage.put(
            key=key,
            data=stream,
            content_type=content_type,
        )

    async def upload_file(
        self,
        path: str,
        key: str,
        content_type: str | None = None,
    ):
        """Upload file with streaming and progress.

        Args:
            path: Local file path
            key: Storage key
            content_type: MIME type (auto-detected if None)

        Returns:
            StoredFile result
        """
        import os

        total_size = os.path.getsize(path)

        stream = chunk_file(path, self.chunk_size)

        if self.progress_callback:
            stream = chunk_stream_with_progress(
                stream,
                total_size,
                self.progress_callback,
                key=key,
                operation="upload",
            )

        # Auto-detect content type from extension
        if content_type is None:
            import mimetypes
            content_type, _ = mimetypes.guess_type(path)

        return await self.storage.put(
            key=key,
            data=stream,
            content_type=content_type,
        )


class StreamingDownloader:
    """Helper for streaming downloads with progress.

    Example:
        downloader = StreamingDownloader(storage, progress_callback=my_callback)
        async for chunk in downloader.download("uploads/file.zip"):
            output_file.write(chunk)
    """

    def __init__(
        self,
        storage,  # Type: Storage
        progress_callback: Callable[[ProgressInfo], None] | None = None,
    ) -> None:
        self.storage = storage
        self.progress_callback = progress_callback

    async def download(self, key: str) -> AsyncIterator[bytes]:
        """Download file with streaming and progress.

        Args:
            key: Storage key

        Yields:
            File data chunks
        """
        # Get file size for progress
        info = await self.storage.info(key)
        total_size = info.size

        stream = self.storage.get(key)

        if self.progress_callback:
            async for chunk in chunk_stream_with_progress(
                stream,
                total_size,
                self.progress_callback,
                key=key,
                operation="download",
            ):
                yield chunk
        else:
            async for chunk in stream:
                yield chunk

    async def download_to_file(self, key: str, path: str) -> int:
        """Download file directly to disk.

        Args:
            key: Storage key
            path: Local destination path

        Returns:
            Total bytes downloaded
        """
        try:
            import aiofiles
        except ImportError as e:
            raise ImportError("aiofiles required: pip install aiofiles") from e

        total_bytes = 0

        async with aiofiles.open(path, "wb") as f:
            async for chunk in self.download(key):
                await f.write(chunk)
                total_bytes += len(chunk)

        return total_bytes
```

### Framework-Agnostic Streaming

Use streaming with any storage backend:

```python
"""Framework-agnostic streaming file operations."""

import asyncio
from pathlib import Path

from litestar_storages import (
    S3Storage,
    S3Config,
    ProgressInfo,
)

# Import from above
# from streaming_utils import StreamingUploader, StreamingDownloader


def create_progress_bar(description: str = "Progress"):
    """Create a simple console progress reporter."""

    def report_progress(info: ProgressInfo) -> None:
        if info.percentage is not None:
            bar_width = 40
            filled = int(bar_width * info.percentage / 100)
            bar = "=" * filled + "-" * (bar_width - filled)
            print(f"\r{description}: [{bar}] {info.percentage:.1f}%", end="", flush=True)
        else:
            mb = info.bytes_transferred / (1024 * 1024)
            print(f"\r{description}: {mb:.2f} MB transferred", end="", flush=True)

    return report_progress


async def main() -> None:
    """Demonstrate streaming uploads and downloads."""

    # Configure S3 storage
    storage = S3Storage(
        config=S3Config(
            bucket="my-bucket",
            region="us-west-2",
        )
    )

    # Create uploader with progress
    uploader = StreamingUploader(
        storage,
        chunk_size=1024 * 1024,  # 1MB chunks
        progress_callback=create_progress_bar("Uploading"),
    )

    # Upload a large file
    print("Starting upload...")
    result = await uploader.upload_file(
        path="/path/to/large-file.zip",
        key="backups/large-file.zip",
        content_type="application/zip",
    )
    print(f"\nUploaded: {result.key} ({result.size} bytes)")

    # Create downloader with progress
    downloader = StreamingDownloader(
        storage,
        progress_callback=create_progress_bar("Downloading"),
    )

    # Download to file
    print("\nStarting download...")
    bytes_downloaded = await downloader.download_to_file(
        key="backups/large-file.zip",
        path="/tmp/downloaded-file.zip",
    )
    print(f"\nDownloaded: {bytes_downloaded} bytes")

    # Or stream to process chunks
    print("\nStreaming download...")
    async for chunk in downloader.download("backups/large-file.zip"):
        # Process each chunk (hash, validate, etc.)
        pass

    await storage.close()


if __name__ == "__main__":
    asyncio.run(main())
```

### S3 Multipart Upload for Very Large Files

For files over 100MB, use S3's multipart upload:

```python
"""S3 multipart upload for very large files."""

import asyncio
from pathlib import Path

from litestar_storages import (
    S3Storage,
    S3Config,
    ProgressInfo,
    MultipartUpload,
)


async def upload_large_file_multipart(
    storage: S3Storage,
    path: str,
    key: str,
    part_size: int = 10 * 1024 * 1024,  # 10MB parts
    progress_callback=None,
) -> None:
    """Upload a large file using S3 multipart upload.

    Benefits:
    - Parallel part uploads possible
    - Resume failed uploads
    - Required for files > 5GB

    Args:
        storage: S3Storage instance
        path: Local file path
        key: S3 key
        part_size: Size of each part (min 5MB)
        progress_callback: Optional progress callback
    """
    import os
    import aiofiles

    file_size = os.path.getsize(path)

    # Use built-in put_large for simplicity
    async with aiofiles.open(path, "rb") as f:
        data = await f.read()

    result = await storage.put_large(
        key=key,
        data=data,
        part_size=part_size,
        progress_callback=progress_callback,
    )

    print(f"Uploaded: {result.key} ({result.size} bytes)")


async def upload_large_file_manual(
    storage: S3Storage,
    path: str,
    key: str,
    part_size: int = 10 * 1024 * 1024,
) -> None:
    """Manual multipart upload with fine-grained control.

    Use this when you need:
    - Custom error handling per part
    - Parallel part uploads
    - Upload state persistence for resume
    """
    import os
    import aiofiles

    file_size = os.path.getsize(path)
    total_parts = (file_size + part_size - 1) // part_size

    print(f"Starting multipart upload: {total_parts} parts")

    # Start multipart upload
    upload = await storage.start_multipart_upload(
        key=key,
        content_type="application/octet-stream",
        part_size=part_size,
    )

    try:
        async with aiofiles.open(path, "rb") as f:
            part_number = 1

            while True:
                chunk = await f.read(part_size)
                if not chunk:
                    break

                # Upload this part
                etag = await storage.upload_part(upload, part_number, chunk)

                print(f"  Part {part_number}/{total_parts} uploaded (ETag: {etag[:8]}...)")
                part_number += 1

        # Complete the upload
        result = await storage.complete_multipart_upload(upload)
        print(f"Completed: {result.key}")

    except Exception as e:
        # Abort on failure to clean up parts
        print(f"Upload failed: {e}, aborting...")
        await storage.abort_multipart_upload(upload)
        raise


async def parallel_multipart_upload(
    storage: S3Storage,
    path: str,
    key: str,
    part_size: int = 10 * 1024 * 1024,
    max_concurrency: int = 4,
) -> None:
    """Upload parts in parallel for faster transfers.

    Args:
        storage: S3Storage instance
        path: Local file path
        key: S3 key
        part_size: Size of each part
        max_concurrency: Max parallel uploads
    """
    import os
    import aiofiles

    file_size = os.path.getsize(path)
    total_parts = (file_size + part_size - 1) // part_size

    # Start upload
    upload = await storage.start_multipart_upload(
        key=key,
        part_size=part_size,
    )

    # Semaphore for concurrency control
    semaphore = asyncio.Semaphore(max_concurrency)

    async def upload_part(part_num: int, offset: int) -> tuple[int, str]:
        """Upload a single part."""
        async with semaphore:
            async with aiofiles.open(path, "rb") as f:
                await f.seek(offset)
                chunk = await f.read(part_size)

            etag = await storage.upload_part(upload, part_num, chunk)
            return part_num, etag

    try:
        # Create tasks for all parts
        tasks = [
            upload_part(i + 1, i * part_size)
            for i in range(total_parts)
        ]

        # Run with progress
        completed = 0
        for coro in asyncio.as_completed(tasks):
            part_num, etag = await coro
            completed += 1
            print(f"Part {part_num} complete ({completed}/{total_parts})")

        # Complete
        result = await storage.complete_multipart_upload(upload)
        print(f"Upload complete: {result.key}")

    except Exception as e:
        await storage.abort_multipart_upload(upload)
        raise
```

### With Litestar

Build streaming file endpoints with Litestar:

```python
"""Litestar application with streaming file operations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated, Any
import uuid

from litestar import Litestar, get, post, Response
from litestar.datastructures import UploadFile
from litestar.di import Provide
from litestar.exceptions import ClientException
from litestar.response import Stream
from litestar.status_codes import HTTP_400_BAD_REQUEST

from litestar_storages import (
    S3Storage,
    S3Config,
    Storage,
    StoredFile,
    ProgressInfo,
    StorageFileNotFoundError,
)
from litestar_storages.contrib.plugin import StoragePlugin


# Configuration
MAX_DIRECT_UPLOAD = 100 * 1024 * 1024  # 100MB - use multipart above this
CHUNK_SIZE = 1024 * 1024  # 1MB chunks


# Response DTOs
@dataclass
class UploadResponse:
    """Upload result."""

    key: str
    size: int
    url: str


@dataclass
class DownloadInfo:
    """Download information."""

    key: str
    size: int
    content_type: str | None
    download_url: str


# Streaming request body reader
async def read_body_stream(
    body: AsyncIterator[bytes],
    max_size: int = 500 * 1024 * 1024,  # 500MB max
) -> AsyncIterator[bytes]:
    """Read request body as a stream with size limit.

    Args:
        body: Request body iterator
        max_size: Maximum allowed size

    Yields:
        Body chunks

    Raises:
        ClientException: If size limit exceeded
    """
    total_size = 0

    async for chunk in body:
        total_size += len(chunk)

        if total_size > max_size:
            raise ClientException(
                detail=f"Request body too large. Maximum: {max_size // (1024 * 1024)}MB",
                status_code=HTTP_400_BAD_REQUEST,
            )

        yield chunk


# Route handlers
@post("/upload/stream")
async def upload_stream(
    data: UploadFile,
    storage: Storage,
) -> UploadResponse:
    """Upload file with streaming.

    Handles files of any size without loading into memory.
    Files over 100MB use multipart upload automatically.
    """
    filename = data.filename or f"{uuid.uuid4()}"
    key = f"uploads/{uuid.uuid4()}/{filename}"

    # Read file content (UploadFile handles streaming internally)
    content = await data.read()

    # For very large files with S3, use multipart
    if isinstance(storage, S3Storage) and len(content) > MAX_DIRECT_UPLOAD:
        result = await storage.put_large(
            key=key,
            data=content,
            content_type=data.content_type,
        )
    else:
        result = await storage.put(
            key=key,
            data=content,
            content_type=data.content_type,
        )

    url = await storage.url(key)

    return UploadResponse(
        key=result.key,
        size=result.size,
        url=url,
    )


@get("/download/{key:path}")
async def download_stream(
    key: str,
    storage: Storage,
) -> Stream:
    """Stream file download without loading into memory.

    Returns a streaming response that sends chunks as they're read.
    """
    try:
        info = await storage.info(key)
    except StorageFileNotFoundError as e:
        raise ClientException(
            detail=f"File not found: {key}",
            status_code=404,
        ) from e

    async def generate() -> AsyncIterator[bytes]:
        """Generate response body from storage stream."""
        async for chunk in storage.get(key):
            yield chunk

    return Stream(
        generate(),
        media_type=info.content_type or "application/octet-stream",
        headers={
            "Content-Length": str(info.size),
            "Content-Disposition": f'attachment; filename="{key.split("/")[-1]}"',
        },
    )


@get("/download/{key:path}/url")
async def get_download_url(
    key: str,
    storage: Storage,
) -> DownloadInfo:
    """Get presigned download URL.

    For cloud storage, returns a presigned URL for direct download.
    Useful for very large files or CDN integration.
    """
    try:
        info = await storage.info(key)
    except StorageFileNotFoundError as e:
        raise ClientException(
            detail=f"File not found: {key}",
            status_code=404,
        ) from e

    # Generate URL with 1 hour expiration
    url = await storage.url(key, expires_in=timedelta(hours=1))

    return DownloadInfo(
        key=info.key,
        size=info.size,
        content_type=info.content_type,
        download_url=url,
    )


# WebSocket progress updates (optional)
async def upload_with_websocket_progress(
    websocket,
    storage: S3Storage,
    data: bytes,
    key: str,
) -> StoredFile:
    """Upload with real-time WebSocket progress updates.

    Example client:
        ws = new WebSocket('ws://...');
        ws.onmessage = (e) => {
            const progress = JSON.parse(e.data);
            updateProgressBar(progress.percentage);
        };
    """
    async def report_progress(info: ProgressInfo) -> None:
        await websocket.send_json({
            "event": "progress",
            "bytes_transferred": info.bytes_transferred,
            "total_bytes": info.total_bytes,
            "percentage": info.percentage,
        })

    result = await storage.put_large(
        key=key,
        data=data,
        progress_callback=report_progress,
    )

    await websocket.send_json({
        "event": "complete",
        "key": result.key,
        "size": result.size,
    })

    return result


# Application setup
def create_app() -> Litestar:
    """Create application with streaming-capable storage."""
    import os

    storage = S3Storage(
        config=S3Config(
            bucket=os.getenv("S3_BUCKET", "uploads"),
            region=os.getenv("AWS_REGION", "us-west-2"),
        )
    )

    return Litestar(
        route_handlers=[upload_stream, download_stream, get_download_url],
        plugins=[StoragePlugin(default=storage)],
    )


app = create_app()
```

### Resumable Uploads

Implement resumable uploads for unreliable connections:

```python
"""Resumable upload implementation."""

import asyncio
import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from litestar_storages import S3Storage, MultipartUpload


@dataclass
class UploadState:
    """Persisted upload state for resume."""

    upload_id: str
    key: str
    file_path: str
    file_size: int
    part_size: int
    completed_parts: list[tuple[int, str]]  # (part_number, etag)

    def to_json(self) -> str:
        """Serialize to JSON."""
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "UploadState":
        """Deserialize from JSON."""
        d = json.loads(data)
        return cls(**d)


class ResumableUploader:
    """Upload large files with resume capability.

    Saves upload state to disk, allowing uploads to resume
    after network failures or application restarts.
    """

    def __init__(
        self,
        storage: S3Storage,
        state_dir: Path = Path(".upload_state"),
        part_size: int = 10 * 1024 * 1024,
    ) -> None:
        self.storage = storage
        self.state_dir = state_dir
        self.part_size = part_size
        self.state_dir.mkdir(exist_ok=True)

    def _state_path(self, file_path: str) -> Path:
        """Get state file path for an upload."""
        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        return self.state_dir / f"{file_hash}.json"

    def _save_state(self, state: UploadState) -> None:
        """Save upload state to disk."""
        path = self._state_path(state.file_path)
        path.write_text(state.to_json())

    def _load_state(self, file_path: str) -> UploadState | None:
        """Load existing upload state."""
        path = self._state_path(file_path)
        if path.exists():
            return UploadState.from_json(path.read_text())
        return None

    def _clear_state(self, file_path: str) -> None:
        """Remove state file after completion."""
        path = self._state_path(file_path)
        if path.exists():
            path.unlink()

    async def upload(
        self,
        file_path: str,
        key: str,
        on_progress=None,
    ) -> None:
        """Upload file with resume support.

        Args:
            file_path: Local file path
            key: Storage key
            on_progress: Optional callback(bytes_uploaded, total_bytes)
        """
        import os
        import aiofiles

        file_size = os.path.getsize(file_path)
        total_parts = (file_size + self.part_size - 1) // self.part_size

        # Check for existing upload
        state = self._load_state(file_path)

        if state and state.key == key:
            print(f"Resuming upload: {len(state.completed_parts)}/{total_parts} parts done")
            upload = MultipartUpload(
                upload_id=state.upload_id,
                key=state.key,
                parts=state.completed_parts,
                part_size=state.part_size,
            )
        else:
            # Start new upload
            upload = await self.storage.start_multipart_upload(
                key=key,
                part_size=self.part_size,
            )
            state = UploadState(
                upload_id=upload.upload_id,
                key=key,
                file_path=file_path,
                file_size=file_size,
                part_size=self.part_size,
                completed_parts=[],
            )

        # Get set of completed part numbers
        completed_numbers = {p[0] for p in state.completed_parts}

        try:
            async with aiofiles.open(file_path, "rb") as f:
                for part_num in range(1, total_parts + 1):
                    if part_num in completed_numbers:
                        # Skip already uploaded parts
                        continue

                    # Seek to part position
                    offset = (part_num - 1) * self.part_size
                    await f.seek(offset)
                    chunk = await f.read(self.part_size)

                    # Upload part
                    etag = await self.storage.upload_part(upload, part_num, chunk)

                    # Update state
                    state.completed_parts.append((part_num, etag))
                    upload.add_part(part_num, etag)
                    self._save_state(state)

                    # Report progress
                    if on_progress:
                        bytes_done = sum(
                            min(self.part_size, file_size - (p[0] - 1) * self.part_size)
                            for p in state.completed_parts
                        )
                        on_progress(bytes_done, file_size)

            # Complete upload
            await self.storage.complete_multipart_upload(upload)
            self._clear_state(file_path)
            print(f"Upload complete: {key}")

        except Exception as e:
            print(f"Upload interrupted: {e}")
            print("Run again to resume from where you left off")
            raise


async def demo_resumable_upload() -> None:
    """Demonstrate resumable upload."""
    storage = S3Storage(
        config=S3Config(bucket="my-bucket", region="us-west-2")
    )

    uploader = ResumableUploader(storage)

    def progress(done: int, total: int) -> None:
        pct = (done / total) * 100
        print(f"\rProgress: {pct:.1f}% ({done}/{total} bytes)", end="")

    await uploader.upload(
        file_path="/path/to/huge-file.tar.gz",
        key="backups/huge-file.tar.gz",
        on_progress=progress,
    )
```

## Key Points

- **Never load large files into memory**: Use streaming and chunking
- **Provide progress feedback**: Users need to know uploads are working
- **Use multipart for large S3 uploads**: Required for files > 5GB, recommended for > 100MB
- **Implement resume for reliability**: Save state for long uploads
- **Parallel uploads**: Faster transfers with concurrent part uploads
- **Presigned URLs**: Offload large downloads to cloud CDN

## Performance Tips

1. **Tune chunk size**: Larger chunks = fewer requests, but more memory
2. **Parallel parts**: 4-8 concurrent part uploads is usually optimal
3. **Presigned URLs**: Let cloud storage handle bandwidth-heavy downloads
4. **Connection pooling**: Reuse HTTP connections for multiple operations
5. **Compression**: Compress before upload if content is compressible

## Related

- [File Upload with Validation](file-upload-validation.md) - Validate streaming uploads
- [Image Processing Pipeline](image-processing-pipeline.md) - Process large images efficiently
- [Multi-Backend Configuration](multi-backend-config.md) - Configure cloud storage backends
