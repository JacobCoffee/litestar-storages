# Custom Backends

This guide explains how to implement custom storage backends for litestar-storages. Whether you need to integrate with a proprietary storage system, add features to existing backends, or create a completely new implementation, this guide covers the patterns and requirements.

## The Storage Protocol

All storage backends must implement the `Storage` protocol:

```python
from typing import Protocol, AsyncIterator, runtime_checkable
from datetime import timedelta
from litestar_storages import StoredFile


@runtime_checkable
class Storage(Protocol):
    """Async storage protocol that all backends must implement."""

    async def put(
        self,
        key: str,
        data: bytes | AsyncIterator[bytes],
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredFile:
        """Store data at the given key."""
        ...

    async def get(self, key: str) -> AsyncIterator[bytes]:
        """Retrieve file contents as an async byte stream."""
        ...

    async def get_bytes(self, key: str) -> bytes:
        """Retrieve entire file contents as bytes."""
        ...

    async def delete(self, key: str) -> None:
        """Delete a file."""
        ...

    async def exists(self, key: str) -> bool:
        """Check if a file exists."""
        ...

    async def list(
        self,
        prefix: str = "",
        *,
        limit: int | None = None,
    ) -> AsyncIterator[StoredFile]:
        """List files with optional prefix filter."""
        ...

    async def url(
        self,
        key: str,
        *,
        expires_in: timedelta | None = None,
    ) -> str:
        """Generate a URL for accessing the file."""
        ...

    async def copy(
        self,
        source: str,
        destination: str,
    ) -> StoredFile:
        """Copy a file within the storage backend."""
        ...

    async def move(
        self,
        source: str,
        destination: str,
    ) -> StoredFile:
        """Move/rename a file within the storage backend."""
        ...

    async def info(self, key: str) -> StoredFile:
        """Get metadata about a file without downloading it."""
        ...
```

## Extending BaseStorage

The `BaseStorage` abstract base class provides default implementations for convenience methods, reducing the amount of code you need to write:

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
from datetime import timedelta
from litestar_storages import StoredFile


class BaseStorage(ABC):
    """Abstract base class with default implementations."""

    # These methods MUST be implemented by subclasses
    @abstractmethod
    async def put(
        self,
        key: str,
        data: bytes | AsyncIterator[bytes],
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredFile:
        ...

    @abstractmethod
    async def get(self, key: str) -> AsyncIterator[bytes]:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    async def list(
        self,
        prefix: str = "",
        *,
        limit: int | None = None,
    ) -> AsyncIterator[StoredFile]:
        ...

    @abstractmethod
    async def url(
        self,
        key: str,
        *,
        expires_in: timedelta | None = None,
    ) -> str:
        ...

    @abstractmethod
    async def info(self, key: str) -> StoredFile:
        ...

    # These methods have default implementations
    async def get_bytes(self, key: str) -> bytes:
        """Default: collect stream into bytes."""
        chunks = []
        async for chunk in self.get(key):
            chunks.append(chunk)
        return b"".join(chunks)

    async def copy(self, source: str, destination: str) -> StoredFile:
        """Default: download and re-upload."""
        info = await self.info(source)
        data = await self.get_bytes(source)
        return await self.put(
            destination,
            data,
            content_type=info.content_type,
            metadata=info.metadata,
        )

    async def move(self, source: str, destination: str) -> StoredFile:
        """Default: copy then delete."""
        result = await self.copy(source, destination)
        await self.delete(source)
        return result
```

## Required vs Optional Methods

### Required Methods (Abstract)

These methods must be implemented in every backend:

| Method | Purpose |
|--------|---------|
| `put()` | Store file data |
| `get()` | Stream file contents |
| `delete()` | Remove a file |
| `exists()` | Check file existence |
| `list()` | Enumerate files |
| `url()` | Generate access URL |
| `info()` | Get file metadata |

### Optional Methods (Have Defaults)

These methods have default implementations in `BaseStorage`:

| Method | Default Behavior | When to Override |
|--------|------------------|------------------|
| `get_bytes()` | Collects `get()` stream | If backend has optimized single-read |
| `copy()` | Download + re-upload | If backend supports server-side copy |
| `move()` | Copy + delete | If backend supports atomic move/rename |

## Example: Custom Backend Implementation

Here's a complete example of a custom backend that stores files in a SQLite database:

```python
import sqlite3
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import AsyncIterator
from contextlib import asynccontextmanager

from litestar_storages import BaseStorage, StoredFile, FileNotFoundError


@dataclass
class SQLiteConfig:
    """Configuration for SQLite storage."""
    database_path: str
    table_name: str = "files"
    chunk_size: int = 64 * 1024  # 64KB chunks for streaming


class SQLiteStorage(BaseStorage):
    """
    SQLite-based storage backend.

    Stores files as BLOBs in a SQLite database. Useful for:
    - Embedded applications
    - Single-file deployments
    - Transactional file operations

    Example:
        storage = SQLiteStorage(
            config=SQLiteConfig(database_path="files.db")
        )
        await storage.put("doc.pdf", pdf_bytes)
    """

    def __init__(self, config: SQLiteConfig) -> None:
        self.config = config
        self._init_database()

    def _init_database(self) -> None:
        """Create the files table if it doesn't exist."""
        with sqlite3.connect(self.config.database_path) as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.config.table_name} (
                    key TEXT PRIMARY KEY,
                    data BLOB NOT NULL,
                    size INTEGER NOT NULL,
                    content_type TEXT,
                    etag TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.config.database_path)

    async def put(
        self,
        key: str,
        data: bytes | AsyncIterator[bytes],
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredFile:
        """Store data in the database."""
        # Collect data if it's a stream
        if not isinstance(data, bytes):
            chunks = []
            async for chunk in data:
                chunks.append(chunk)
            data = b"".join(chunks)

        etag = hashlib.md5(data).hexdigest()
        now = datetime.utcnow()
        metadata_json = str(metadata) if metadata else None

        with self._get_connection() as conn:
            conn.execute(
                f"""
                INSERT OR REPLACE INTO {self.config.table_name}
                (key, data, size, content_type, etag, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (key, data, len(data), content_type, etag, now, metadata_json),
            )

        return StoredFile(
            key=key,
            size=len(data),
            content_type=content_type,
            etag=etag,
            last_modified=now,
            metadata=metadata or {},
        )

    async def get(self, key: str) -> AsyncIterator[bytes]:
        """Stream file contents from the database."""
        with self._get_connection() as conn:
            row = conn.execute(
                f"SELECT data FROM {self.config.table_name} WHERE key = ?",
                (key,),
            ).fetchone()

        if row is None:
            raise FileNotFoundError(key)

        data = row[0]
        chunk_size = self.config.chunk_size

        # Yield in chunks for streaming compatibility
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

    async def delete(self, key: str) -> None:
        """Delete a file from the database."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.config.table_name} WHERE key = ?",
                (key,),
            )
            if cursor.rowcount == 0:
                raise FileNotFoundError(key)

    async def exists(self, key: str) -> bool:
        """Check if a file exists in the database."""
        with self._get_connection() as conn:
            row = conn.execute(
                f"SELECT 1 FROM {self.config.table_name} WHERE key = ?",
                (key,),
            ).fetchone()
        return row is not None

    async def list(
        self,
        prefix: str = "",
        *,
        limit: int | None = None,
    ) -> AsyncIterator[StoredFile]:
        """List files matching the prefix."""
        query = f"""
            SELECT key, size, content_type, etag, created_at
            FROM {self.config.table_name}
            WHERE key LIKE ?
        """
        params: list = [f"{prefix}%"]

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()

        for row in rows:
            yield StoredFile(
                key=row[0],
                size=row[1],
                content_type=row[2],
                etag=row[3],
                last_modified=datetime.fromisoformat(row[4]) if row[4] else None,
            )

    async def url(
        self,
        key: str,
        *,
        expires_in: timedelta | None = None,
    ) -> str:
        """Generate a pseudo-URL (SQLite doesn't support real URLs)."""
        return f"sqlite://{self.config.database_path}/{key}"

    async def info(self, key: str) -> StoredFile:
        """Get file metadata without downloading."""
        with self._get_connection() as conn:
            row = conn.execute(
                f"""
                SELECT key, size, content_type, etag, created_at
                FROM {self.config.table_name}
                WHERE key = ?
                """,
                (key,),
            ).fetchone()

        if row is None:
            raise FileNotFoundError(key)

        return StoredFile(
            key=row[0],
            size=row[1],
            content_type=row[2],
            etag=row[3],
            last_modified=datetime.fromisoformat(row[4]) if row[4] else None,
        )

    # Override get_bytes for efficiency - no need to chunk
    async def get_bytes(self, key: str) -> bytes:
        """Get entire file contents directly."""
        with self._get_connection() as conn:
            row = conn.execute(
                f"SELECT data FROM {self.config.table_name} WHERE key = ?",
                (key,),
            ).fetchone()

        if row is None:
            raise FileNotFoundError(key)

        return row[0]
```

## Testing Custom Backends

Use the protocol compliance test suite to verify your implementation:

```python
import pytest
from litestar_storages import Storage

# Import your custom backend
from mypackage import SQLiteStorage, SQLiteConfig


@pytest.fixture
def storage(tmp_path):
    """Create a SQLite storage instance for testing."""
    return SQLiteStorage(
        config=SQLiteConfig(database_path=str(tmp_path / "test.db"))
    )


class TestProtocolCompliance:
    """Verify the backend implements the Storage protocol correctly."""

    async def test_implements_protocol(self, storage):
        """Backend should be a valid Storage implementation."""
        assert isinstance(storage, Storage)

    async def test_put_and_get(self, storage):
        """Basic put/get cycle should work."""
        data = b"Hello, World!"
        result = await storage.put("test.txt", data)

        assert result.key == "test.txt"
        assert result.size == len(data)

        retrieved = await storage.get_bytes("test.txt")
        assert retrieved == data

    async def test_put_with_metadata(self, storage):
        """Put should accept content_type and metadata."""
        result = await storage.put(
            "doc.pdf",
            b"PDF content",
            content_type="application/pdf",
            metadata={"author": "Test"},
        )

        assert result.content_type == "application/pdf"

    async def test_get_streaming(self, storage):
        """Get should return an async iterator."""
        await storage.put("stream.txt", b"chunk1chunk2chunk3")

        chunks = []
        async for chunk in storage.get("stream.txt"):
            chunks.append(chunk)

        assert b"".join(chunks) == b"chunk1chunk2chunk3"

    async def test_delete(self, storage):
        """Delete should remove files."""
        await storage.put("to-delete.txt", b"data")
        assert await storage.exists("to-delete.txt")

        await storage.delete("to-delete.txt")
        assert not await storage.exists("to-delete.txt")

    async def test_delete_nonexistent(self, storage):
        """Delete of nonexistent file should raise FileNotFoundError."""
        from litestar_storages import FileNotFoundError

        with pytest.raises(FileNotFoundError):
            await storage.delete("nonexistent.txt")

    async def test_exists(self, storage):
        """Exists should return correct boolean."""
        assert not await storage.exists("new.txt")

        await storage.put("new.txt", b"data")
        assert await storage.exists("new.txt")

    async def test_list(self, storage):
        """List should return matching files."""
        await storage.put("a/1.txt", b"1")
        await storage.put("a/2.txt", b"2")
        await storage.put("b/3.txt", b"3")

        a_files = [f async for f in storage.list("a/")]
        assert len(a_files) == 2
        assert all(f.key.startswith("a/") for f in a_files)

    async def test_list_with_limit(self, storage):
        """List should respect limit parameter."""
        for i in range(10):
            await storage.put(f"file{i}.txt", b"data")

        files = [f async for f in storage.list(limit=5)]
        assert len(files) == 5

    async def test_info(self, storage):
        """Info should return file metadata."""
        await storage.put("info.txt", b"content", content_type="text/plain")

        info = await storage.info("info.txt")
        assert info.key == "info.txt"
        assert info.size == 7
        assert info.content_type == "text/plain"

    async def test_info_nonexistent(self, storage):
        """Info on nonexistent file should raise FileNotFoundError."""
        from litestar_storages import FileNotFoundError

        with pytest.raises(FileNotFoundError):
            await storage.info("nonexistent.txt")

    async def test_url(self, storage):
        """URL should return a string."""
        await storage.put("url.txt", b"data")
        url = await storage.url("url.txt")

        assert isinstance(url, str)
        assert len(url) > 0

    async def test_copy(self, storage):
        """Copy should duplicate a file."""
        await storage.put("original.txt", b"data")

        result = await storage.copy("original.txt", "copy.txt")

        assert result.key == "copy.txt"
        assert await storage.exists("original.txt")  # Original still exists
        assert await storage.exists("copy.txt")

        original = await storage.get_bytes("original.txt")
        copy = await storage.get_bytes("copy.txt")
        assert original == copy

    async def test_move(self, storage):
        """Move should relocate a file."""
        await storage.put("source.txt", b"data")

        result = await storage.move("source.txt", "dest.txt")

        assert result.key == "dest.txt"
        assert not await storage.exists("source.txt")  # Original gone
        assert await storage.exists("dest.txt")
```

## Best Practices

### Error Handling

Use the standard exception hierarchy:

```python
from litestar_storages import (
    StorageError,
    FileNotFoundError,
    FileExistsError,
    PermissionError,
    ConnectionError,
    ConfigurationError,
)

async def put(self, key: str, data: bytes, **kwargs) -> StoredFile:
    try:
        # Attempt storage operation
        ...
    except SomeBackendError as e:
        if "not found" in str(e):
            raise FileNotFoundError(key) from e
        elif "permission" in str(e):
            raise PermissionError(str(e)) from e
        else:
            raise StorageError(str(e)) from e
```

### Key Sanitization

Always sanitize keys to prevent security issues:

```python
def _sanitize_key(self, key: str) -> str:
    """Sanitize key to prevent path traversal."""
    # Normalize separators
    key = key.replace("\\", "/")
    # Remove leading slashes
    key = key.lstrip("/")
    # Resolve path components
    parts = []
    for part in key.split("/"):
        if part == "..":
            if parts:
                parts.pop()
        elif part and part != ".":
            parts.append(part)
    return "/".join(parts)
```

### Async Context Managers

If your backend needs cleanup, implement context manager protocol:

```python
class MyStorage(BaseStorage):
    async def __aenter__(self) -> "MyStorage":
        await self._connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self._disconnect()

# Usage
async with MyStorage(config) as storage:
    await storage.put("file.txt", data)
```

### Configuration Dataclasses

Use frozen dataclasses for configuration:

```python
from dataclasses import dataclass, field
from datetime import timedelta


@dataclass(frozen=True, slots=True)
class MyBackendConfig:
    """Immutable configuration for my backend."""
    endpoint: str
    api_key: str
    timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    max_retries: int = 3

    def __repr__(self) -> str:
        """Hide sensitive values in repr."""
        return f"MyBackendConfig(endpoint={self.endpoint!r}, api_key=***)"
```

## Next Steps

- Review the [FileSystem backend](../backends/filesystem.md) source for a reference implementation
- Check the [S3 backend](../backends/s3.md) for cloud integration patterns
- Use [Memory storage](../backends/memory.md) as a testing baseline
