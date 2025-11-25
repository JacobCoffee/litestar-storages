# Progress Callbacks

Progress callbacks enable real-time tracking of upload and download operations. This is essential for providing user feedback during large file transfers, logging transfer statistics, and implementing progress bars.

## ProgressInfo Structure

The `ProgressInfo` dataclass provides information about transfer progress:

```python
from litestar_storages import ProgressInfo

@dataclass
class ProgressInfo:
    bytes_transferred: int        # Bytes transferred so far
    total_bytes: int | None       # Total bytes (None if unknown)
    operation: str                # "upload" or "download"
    key: str                      # Storage key being transferred

    @property
    def percentage(self) -> float | None:
        """Calculate completion percentage (0-100)."""
        if self.total_bytes is None or self.total_bytes == 0:
            return None
        return (self.bytes_transferred / self.total_bytes) * 100
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `bytes_transferred` | `int` | Number of bytes transferred so far |
| `total_bytes` | `int \| None` | Total transfer size (None if unknown, e.g., streaming) |
| `operation` | `str` | Type of operation: `"upload"` or `"download"` |
| `key` | `str` | The storage key being transferred |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `percentage` | `float \| None` | Completion percentage (0-100), or None if total is unknown |

## The ProgressCallback Protocol

Progress callbacks follow this protocol:

```python
from litestar_storages import ProgressCallback, ProgressInfo

class ProgressCallback(Protocol):
    """Protocol for progress callback functions."""

    def __call__(self, info: ProgressInfo) -> None:
        """Called with progress information."""
        ...
```

Any callable matching this signature works as a progress callback:

```python
# Function callback
def my_progress(info: ProgressInfo) -> None:
    print(f"{info.percentage:.1f}%")

# Lambda callback
lambda info: print(f"{info.bytes_transferred} bytes")

# Class-based callback
class ProgressTracker:
    def __call__(self, info: ProgressInfo) -> None:
        self.last_progress = info
```

## Basic Usage

### Simple Progress Logging

```python
from litestar_storages import S3Storage, S3Config, ProgressInfo

def log_progress(info: ProgressInfo) -> None:
    """Log upload progress."""
    if info.percentage is not None:
        print(f"[{info.operation}] {info.key}: {info.percentage:.1f}%")
    else:
        print(f"[{info.operation}] {info.key}: {info.bytes_transferred} bytes")

storage = S3Storage(S3Config(bucket="my-bucket"))

result = await storage.put_large(
    "large-file.zip",
    file_data,
    progress_callback=log_progress,
)
```

Output:

```
[upload] large-file.zip: 10.0%
[upload] large-file.zip: 20.0%
[upload] large-file.zip: 30.0%
...
[upload] large-file.zip: 100.0%
```

### Percentage-Based Callback

```python
def show_percentage(info: ProgressInfo) -> None:
    """Display percentage progress."""
    pct = info.percentage
    if pct is not None:
        # Only print at 10% intervals
        if pct % 10 < 1:
            print(f"Progress: {pct:.0f}%")
```

## Progress Bar Examples

### Using tqdm

[tqdm](https://github.com/tqdm/tqdm) is a popular progress bar library:

```python
from tqdm import tqdm
from litestar_storages import S3Storage, S3Config, ProgressInfo

async def upload_with_tqdm(storage: S3Storage, key: str, data: bytes) -> None:
    """Upload with tqdm progress bar."""

    pbar = tqdm(
        total=len(data),
        unit="B",
        unit_scale=True,
        desc=f"Uploading {key}",
    )
    last_transferred = 0

    def update_progress(info: ProgressInfo) -> None:
        nonlocal last_transferred
        delta = info.bytes_transferred - last_transferred
        pbar.update(delta)
        last_transferred = info.bytes_transferred

    try:
        await storage.put_large(key, data, progress_callback=update_progress)
    finally:
        pbar.close()


# Usage
storage = S3Storage(S3Config(bucket="my-bucket"))
await upload_with_tqdm(storage, "video.mp4", video_data)
```

Output:

```
Uploading video.mp4:  45%|████████▌          | 45.0M/100M [00:05<00:06, 8.50MB/s]
```

### Using rich

[rich](https://github.com/Textualize/rich) provides beautiful terminal output:

```python
from rich.progress import Progress, TaskID
from litestar_storages import S3Storage, ProgressInfo

async def upload_with_rich(storage: S3Storage, key: str, data: bytes) -> None:
    """Upload with rich progress bar."""

    with Progress() as progress:
        task = progress.add_task(f"[cyan]Uploading {key}", total=len(data))

        def update_progress(info: ProgressInfo) -> None:
            progress.update(task, completed=info.bytes_transferred)

        await storage.put_large(key, data, progress_callback=update_progress)


# Usage
await upload_with_rich(storage, "document.pdf", pdf_data)
```

### Console Progress Bar (No Dependencies)

```python
import sys
from litestar_storages import ProgressInfo

def console_progress_bar(info: ProgressInfo) -> None:
    """Display a simple ASCII progress bar."""
    if info.total_bytes is None:
        # Unknown total - show transferred bytes
        sys.stdout.write(f"\r{info.key}: {info.bytes_transferred:,} bytes")
        sys.stdout.flush()
        return

    # Calculate progress
    pct = info.bytes_transferred / info.total_bytes
    bar_width = 40
    filled = int(bar_width * pct)
    bar = "=" * filled + "-" * (bar_width - filled)

    # Format sizes
    transferred_mb = info.bytes_transferred / (1024 * 1024)
    total_mb = info.total_bytes / (1024 * 1024)

    sys.stdout.write(f"\r{info.key}: [{bar}] {transferred_mb:.1f}/{total_mb:.1f} MB ({pct*100:.0f}%)")
    sys.stdout.flush()

    # Newline when complete
    if info.bytes_transferred >= info.total_bytes:
        print()


# Usage
await storage.put_large("file.bin", data, progress_callback=console_progress_bar)
```

Output:

```
file.bin: [====================--------------------] 52.3/100.0 MB (52%)
```

## Class-Based Progress Tracking

For more complex scenarios, use a class-based callback:

```python
from dataclasses import dataclass, field
from datetime import datetime
from litestar_storages import ProgressInfo

@dataclass
class TransferStats:
    """Track transfer statistics."""

    key: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    total_bytes: int = 0
    bytes_transferred: int = 0
    updates: int = 0

    @property
    def duration_seconds(self) -> float | None:
        """Calculate transfer duration."""
        if not self.started_at:
            return None
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()

    @property
    def speed_mbps(self) -> float | None:
        """Calculate transfer speed in MB/s."""
        duration = self.duration_seconds
        if not duration or duration == 0:
            return None
        return (self.bytes_transferred / (1024 * 1024)) / duration


class ProgressTracker:
    """Track progress across multiple transfers."""

    def __init__(self):
        self.transfers: dict[str, TransferStats] = {}
        self.current: TransferStats | None = None

    def __call__(self, info: ProgressInfo) -> None:
        """Handle progress update."""
        # Get or create stats for this transfer
        if info.key not in self.transfers:
            self.transfers[info.key] = TransferStats(
                key=info.key,
                started_at=datetime.now(),
                total_bytes=info.total_bytes or 0,
            )

        stats = self.transfers[info.key]
        stats.bytes_transferred = info.bytes_transferred
        stats.updates += 1
        self.current = stats

        # Mark completion
        if info.total_bytes and info.bytes_transferred >= info.total_bytes:
            stats.completed_at = datetime.now()

        # Log progress
        if stats.speed_mbps:
            print(f"{info.key}: {info.percentage:.1f}% @ {stats.speed_mbps:.1f} MB/s")

    def summary(self) -> str:
        """Generate summary of all transfers."""
        lines = ["Transfer Summary", "=" * 40]
        for key, stats in self.transfers.items():
            speed = f"{stats.speed_mbps:.1f} MB/s" if stats.speed_mbps else "N/A"
            lines.append(f"  {key}: {stats.bytes_transferred:,} bytes ({speed})")
        return "\n".join(lines)


# Usage
tracker = ProgressTracker()

await storage.put_large("file1.zip", data1, progress_callback=tracker)
await storage.put_large("file2.zip", data2, progress_callback=tracker)

print(tracker.summary())
```

## Throttled Progress Updates

Reduce callback frequency for better performance:

```python
import time
from litestar_storages import ProgressInfo

class ThrottledProgress:
    """Throttle progress updates to reduce overhead."""

    def __init__(self, callback, min_interval: float = 0.5):
        self.callback = callback
        self.min_interval = min_interval
        self.last_update = 0.0

    def __call__(self, info: ProgressInfo) -> None:
        now = time.time()

        # Always call on completion
        is_complete = (
            info.total_bytes is not None
            and info.bytes_transferred >= info.total_bytes
        )

        if is_complete or (now - self.last_update) >= self.min_interval:
            self.callback(info)
            self.last_update = now


# Usage
def my_progress(info: ProgressInfo) -> None:
    print(f"{info.percentage:.1f}%")

throttled = ThrottledProgress(my_progress, min_interval=1.0)  # Max 1 update/second
await storage.put_large("file.zip", data, progress_callback=throttled)
```

## Web Application Integration

### WebSocket Progress Updates

Send progress updates to a browser via WebSocket:

```python
from litestar import WebSocket
from litestar_storages import ProgressInfo, S3Storage

async def upload_with_websocket(
    storage: S3Storage,
    websocket: WebSocket,
    key: str,
    data: bytes,
) -> None:
    """Upload with WebSocket progress updates."""

    async def send_progress(info: ProgressInfo) -> None:
        await websocket.send_json({
            "type": "progress",
            "key": info.key,
            "bytes_transferred": info.bytes_transferred,
            "total_bytes": info.total_bytes,
            "percentage": info.percentage,
        })

    # Note: put_large expects a sync callback
    # Wrap in a sync function that schedules the async send
    import asyncio
    loop = asyncio.get_event_loop()

    def sync_callback(info: ProgressInfo) -> None:
        loop.create_task(send_progress(info))

    await storage.put_large(key, data, progress_callback=sync_callback)

    await websocket.send_json({
        "type": "complete",
        "key": key,
    })
```

### Progress API Endpoint

Expose progress via HTTP polling:

```python
from litestar import Litestar, post, get
from litestar_storages import S3Storage, ProgressInfo
import asyncio

# Global progress tracking (use Redis in production)
upload_progress: dict[str, ProgressInfo] = {}

@post("/upload/{upload_id:str}")
async def start_upload(
    upload_id: str,
    data: bytes,
    storage: S3Storage,
) -> dict:
    """Start an upload with progress tracking."""

    def track_progress(info: ProgressInfo) -> None:
        upload_progress[upload_id] = info

    # Start upload in background
    asyncio.create_task(
        storage.put_large(f"uploads/{upload_id}", data, progress_callback=track_progress)
    )

    return {"upload_id": upload_id, "status": "started"}


@get("/upload/{upload_id:str}/progress")
async def get_progress(upload_id: str) -> dict:
    """Get upload progress."""
    info = upload_progress.get(upload_id)

    if info is None:
        return {"status": "not_found"}

    return {
        "status": "in_progress" if info.percentage < 100 else "complete",
        "bytes_transferred": info.bytes_transferred,
        "total_bytes": info.total_bytes,
        "percentage": info.percentage,
    }
```

## Logging Integration

Integrate progress with Python logging:

```python
import logging
from litestar_storages import ProgressInfo

logger = logging.getLogger(__name__)

class LoggingProgress:
    """Log progress at configurable intervals."""

    def __init__(self, log_every_percent: float = 25.0):
        self.log_every_percent = log_every_percent
        self.last_logged = 0.0

    def __call__(self, info: ProgressInfo) -> None:
        pct = info.percentage or 0

        # Log at specified intervals
        if pct - self.last_logged >= self.log_every_percent:
            logger.info(
                "Transfer progress",
                extra={
                    "key": info.key,
                    "operation": info.operation,
                    "bytes_transferred": info.bytes_transferred,
                    "total_bytes": info.total_bytes,
                    "percentage": pct,
                }
            )
            self.last_logged = pct

        # Always log completion
        if info.total_bytes and info.bytes_transferred >= info.total_bytes:
            logger.info(f"Transfer complete: {info.key}")


# Usage
await storage.put_large(
    "file.zip",
    data,
    progress_callback=LoggingProgress(log_every_percent=10),
)
```

## Best Practices

### 1. Keep Callbacks Fast

Progress callbacks run synchronously in the upload loop. Slow callbacks impact transfer performance:

```python
# Bad - slow callback blocks upload
def slow_callback(info: ProgressInfo) -> None:
    time.sleep(0.1)  # Don't do this!
    update_database(info)  # Or this!

# Good - fast callback with async follow-up
def fast_callback(info: ProgressInfo) -> None:
    asyncio.create_task(update_database_async(info))  # Non-blocking
```

### 2. Handle Unknown Totals

Streaming uploads may not know the total size:

```python
def safe_progress(info: ProgressInfo) -> None:
    if info.percentage is not None:
        print(f"Progress: {info.percentage:.1f}%")
    else:
        # Fallback for unknown total
        mb = info.bytes_transferred / (1024 * 1024)
        print(f"Transferred: {mb:.1f} MB")
```

### 3. Use Throttling for Large Files

Reduce overhead with throttled updates:

```python
# For 10GB file with 10MB parts = 1000 updates
# Throttle to reduce to ~20 updates
throttled = ThrottledProgress(callback, min_interval=5.0)
```

### 4. Clean Up Resources

Ensure progress bars are closed properly:

```python
from tqdm import tqdm

pbar = tqdm(total=file_size)
try:
    await storage.put_large(key, data, progress_callback=lambda i: pbar.update(...))
finally:
    pbar.close()  # Always close!
```

## Next Steps

- Learn about [multipart uploads](multipart-uploads.md) for large file handling
- Explore [retry utilities](retry.md) for reliable transfers
- See [S3 storage](../backends/s3.md) for full S3Storage documentation
