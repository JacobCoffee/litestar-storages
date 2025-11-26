# Retry Utilities

The retry module provides robust retry logic with exponential backoff for storage operations. Network issues, rate limits, and transient failures are common in cloud storage - the retry utilities help your application handle them gracefully.

## When to Use Retries

Retries are appropriate for **transient** failures that may succeed on a subsequent attempt:

| Retryable | Not Retryable |
|-----------|---------------|
| Connection timeouts | Invalid credentials |
| Rate limiting (429) | File not found |
| Temporary network issues | Permission denied |
| Service unavailable (503) | Invalid configuration |

The retry utilities automatically distinguish between these cases - non-retryable exceptions are raised immediately without wasting time on doomed attempts.

## RetryConfig

The `RetryConfig` dataclass controls retry behavior:

```python
from litestar_storages import RetryConfig

config = RetryConfig(
    max_retries=3,           # Maximum retry attempts (0 = no retries)
    base_delay=1.0,          # Initial delay between retries (seconds)
    max_delay=60.0,          # Maximum delay cap (seconds)
    exponential_base=2.0,    # Base for exponential backoff
    jitter=True,             # Add randomness to prevent thundering herd
    retryable_exceptions=(   # Exception types that trigger retries
        StorageConnectionError,
        TimeoutError,
        ConnectionError,
    ),
)
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `max_retries` | `int` | `3` | Maximum number of retry attempts after initial failure |
| `base_delay` | `float` | `1.0` | Initial delay in seconds before first retry |
| `max_delay` | `float` | `60.0` | Maximum delay cap to prevent excessive waits |
| `exponential_base` | `float` | `2.0` | Multiplier for exponential backoff |
| `jitter` | `bool` | `True` | Add randomness to delays (recommended) |
| `retryable_exceptions` | `tuple` | See below | Exception types that should trigger retries |

### Default Retryable Exceptions

By default, these exceptions trigger retries:

- `StorageConnectionError` - Network connectivity issues
- `TimeoutError` - Operation timeouts
- `ConnectionError` - Python's built-in connection error

## The @retry Decorator

The `@retry` decorator adds retry logic to async functions:

```python
from litestar_storages import retry, RetryConfig, Storage

@retry()
async def upload_file(storage: Storage, key: str, data: bytes) -> None:
    """Upload with default retry settings (3 retries, exponential backoff)."""
    await storage.put(key, data)


@retry(RetryConfig(max_retries=5, base_delay=0.5))
async def upload_critical_file(storage: Storage, key: str, data: bytes) -> None:
    """Upload with custom retry settings for important files."""
    await storage.put(key, data)
```

### Basic Usage

```python
from litestar_storages import retry, Storage

@retry()
async def store_user_avatar(storage: Storage, user_id: str, image: bytes) -> str:
    """Store a user's avatar with automatic retry on failure."""
    key = f"avatars/{user_id}.jpg"
    result = await storage.put(key, image, content_type="image/jpeg")
    return result.key
```

### Custom Configuration

```python
from litestar_storages import retry, RetryConfig

# Aggressive retry for critical operations
critical_retry = RetryConfig(
    max_retries=5,
    base_delay=0.5,
    max_delay=30.0,
)

@retry(critical_retry)
async def store_payment_receipt(storage: Storage, receipt_id: str, pdf: bytes) -> None:
    """Store payment receipt - must succeed."""
    await storage.put(f"receipts/{receipt_id}.pdf", pdf)
```

### Custom Retryable Exceptions

Extend the retryable exceptions for specific backends:

```python
from litestar_storages import retry, RetryConfig, StorageConnectionError

# Include rate limit errors as retryable
@retry(RetryConfig(
    retryable_exceptions=(
        StorageConnectionError,
        TimeoutError,
        ConnectionError,
        RateLimitError,  # Your custom exception
    ),
))
async def upload_with_rate_limit_handling(storage: Storage, key: str, data: bytes) -> None:
    await storage.put(key, data)
```

## The with_retry() Function

For cases where you need inline retry logic without a decorator, use `with_retry()`:

```python
from litestar_storages import with_retry, RetryConfig, Storage

async def process_upload(storage: Storage, key: str, data: bytes) -> None:
    """Upload with inline retry logic."""

    # Retry just the storage operation
    await with_retry(
        lambda: storage.put(key, data),
        RetryConfig(max_retries=3),
    )
```

### When to Use with_retry()

Use `with_retry()` instead of `@retry` when:

- You need to retry only part of a function
- The retry configuration is determined at runtime
- You're working with lambdas or closures

```python
from litestar_storages import with_retry, RetryConfig

async def batch_upload(storage: Storage, files: dict[str, bytes]) -> list[str]:
    """Upload multiple files with per-file retry."""
    uploaded = []

    for key, data in files.items():
        # Each file gets its own retry attempts
        result = await with_retry(
            lambda k=key, d=data: storage.put(k, d),
            RetryConfig(max_retries=2),
        )
        uploaded.append(result.key)

    return uploaded
```

### Dynamic Configuration

```python
async def upload_with_priority(
    storage: Storage,
    key: str,
    data: bytes,
    priority: str,
) -> None:
    """Upload with retry config based on priority."""

    if priority == "critical":
        config = RetryConfig(max_retries=10, base_delay=0.1)
    elif priority == "high":
        config = RetryConfig(max_retries=5, base_delay=0.5)
    else:
        config = RetryConfig(max_retries=2, base_delay=1.0)

    await with_retry(lambda: storage.put(key, data), config)
```

## Exponential Backoff Explained

The retry delay grows exponentially with each attempt:

```
delay = min(base_delay * (exponential_base ** attempt), max_delay)
```

With default settings (`base_delay=1.0`, `exponential_base=2.0`, `max_delay=60.0`):

| Attempt | Delay (seconds) |
|---------|-----------------|
| 1 | 1.0 |
| 2 | 2.0 |
| 3 | 4.0 |
| 4 | 8.0 |
| 5 | 16.0 |
| 6 | 32.0 |
| 7+ | 60.0 (capped) |

### Why Jitter Matters

Without jitter, if multiple clients fail at the same time, they all retry at the same time, potentially causing another failure (thundering herd problem).

With jitter enabled (default), delays are randomized within +/-25%:

```
jittered_delay = delay * random(0.75, 1.25)
```

This spreads out retry attempts, reducing load spikes on the storage service.

## Logging

The retry utilities log warnings for each retry attempt and errors when retries are exhausted:

```python
import logging

# Enable logging to see retry activity
logging.basicConfig(level=logging.WARNING)

# Example log output:
# WARNING:litestar_storages.retry:Retry attempt 1/3 for upload_file after 1.23s: Connection timed out
# WARNING:litestar_storages.retry:Retry attempt 2/3 for upload_file after 2.67s: Connection timed out
# ERROR:litestar_storages.retry:All 3 retries exhausted for upload_file
```

To capture retry events in your application:

```python
import logging

logger = logging.getLogger("litestar_storages.retry")
logger.setLevel(logging.INFO)

# Add your handler
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
logger.addHandler(handler)
```

## Best Practices

### 1. Use Retries for Idempotent Operations

Retries work best with operations that can be safely repeated:

```python
# Good: PUT is idempotent - uploading the same file twice is fine
@retry()
async def upload(storage: Storage, key: str, data: bytes) -> None:
    await storage.put(key, data)

# Caution: Not idempotent - may create duplicates
async def create_unique_file(storage: Storage, data: bytes) -> str:
    key = f"files/{uuid4()}.dat"  # Generate key BEFORE retry loop
    await with_retry(lambda: storage.put(key, data))
    return key
```

### 2. Set Reasonable Timeouts

Combine retries with operation timeouts to avoid waiting forever:

```python
import asyncio
from litestar_storages import retry, RetryConfig

@retry(RetryConfig(max_retries=3, base_delay=1.0))
async def upload_with_timeout(storage: Storage, key: str, data: bytes) -> None:
    """Upload with both retry and timeout."""
    try:
        await asyncio.wait_for(
            storage.put(key, data),
            timeout=30.0,  # 30 second timeout per attempt
        )
    except asyncio.TimeoutError:
        raise TimeoutError(f"Upload of {key} timed out")
```

### 3. Don't Retry User-Facing Operations

For operations where users are waiting, prefer fast failure over long retry sequences:

```python
# API endpoint - fail fast for better UX
@retry(RetryConfig(max_retries=1, base_delay=0.5))
async def handle_upload(storage: Storage, key: str, data: bytes) -> None:
    await storage.put(key, data)

# Background job - can afford more retries
@retry(RetryConfig(max_retries=10, base_delay=5.0))
async def process_batch_upload(storage: Storage, key: str, data: bytes) -> None:
    await storage.put(key, data)
```

### 4. Monitor Retry Rates

High retry rates indicate underlying issues. Track them in production:

```python
from dataclasses import dataclass

@dataclass
class RetryMetrics:
    attempts: int = 0
    successes: int = 0
    failures: int = 0

metrics = RetryMetrics()

@retry()
async def upload_with_metrics(storage: Storage, key: str, data: bytes) -> None:
    metrics.attempts += 1
    try:
        await storage.put(key, data)
        metrics.successes += 1
    except Exception:
        metrics.failures += 1
        raise
```

## Integration with Storage Operations

### Wrapping Storage Methods

Create a retry-enabled wrapper for common operations:

```python
from litestar_storages import Storage, RetryConfig, with_retry

class RetryableStorage:
    """Storage wrapper with automatic retries."""

    def __init__(self, storage: Storage, config: RetryConfig | None = None):
        self._storage = storage
        self._config = config or RetryConfig()

    async def put(self, key: str, data: bytes, **kwargs):
        return await with_retry(
            lambda: self._storage.put(key, data, **kwargs),
            self._config,
        )

    async def get_bytes(self, key: str) -> bytes:
        return await with_retry(
            lambda: self._storage.get_bytes(key),
            self._config,
        )

    async def delete(self, key: str) -> None:
        return await with_retry(
            lambda: self._storage.delete(key),
            self._config,
        )
```

## Next Steps

- Learn about [multipart uploads](multipart-uploads.md) for large files
- Explore [progress callbacks](progress-callbacks.md) for upload monitoring
- Create [custom backends](custom-backends.md) with built-in retry support
