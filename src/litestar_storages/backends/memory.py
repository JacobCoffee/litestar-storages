"""In-memory storage backend for testing and development."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from litestar_storages.base import BaseStorage
from litestar_storages.exceptions import StorageFileNotFoundError
from litestar_storages.types import StoredFile


def _generate_etag(data: bytes) -> str:
    """Generate an ETag from file data using MD5 hash."""
    return f'"{hashlib.md5(data, usedforsecurity=False).hexdigest()}"'


__all__ = ("MemoryConfig", "MemoryStorage")


@dataclass
class MemoryConfig:
    """Configuration for in-memory storage.

    Attributes:
        max_size: Maximum total bytes to store (None for unlimited)
    """

    max_size: int | None = None


class MemoryStorage(BaseStorage):
    """In-memory storage backend for testing and development.

    This backend stores files in memory using a dictionary. It is not suitable
    for production use as data is lost on restart and consumes RAM.

    Example:
        >>> storage = MemoryStorage()
        >>> await storage.put("test.txt", b"hello world")
        StoredFile(key='test.txt', size=11, ...)
        >>> assert await storage.exists("test.txt")
        >>> data = await storage.get_bytes("test.txt")
        >>> assert data == b"hello world"

    Note:
        The URL method returns memory:// URLs that are not accessible externally.
        This is primarily useful for testing.
    """

    def __init__(self, config: MemoryConfig | None = None) -> None:
        """Initialize MemoryStorage.

        Args:
            config: Configuration for the storage backend (optional)
        """
        self.config = config or MemoryConfig()
        self._files: dict[str, tuple[bytes, StoredFile]] = {}

    async def put(
        self,
        key: str,
        data: bytes | AsyncIterator[bytes],
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredFile:
        """Store data at the given key.

        Args:
            key: Storage path/key for the file
            data: File contents as bytes or async byte stream
            content_type: MIME type of the content
            metadata: Additional metadata to store with the file

        Returns:
            StoredFile with metadata about the stored file

        Raises:
            StorageError: If max_size would be exceeded
        """
        # Collect data if it's an async iterator
        if isinstance(data, bytes):
            file_data = data
        else:
            chunks = []
            async for chunk in data:
                chunks.append(chunk)
            file_data = b"".join(chunks)

        # Check size limit
        if self.config.max_size is not None:
            current_size = sum(len(d) for d, _ in self._files.values())
            if current_size + len(file_data) > self.config.max_size:
                from litestar_storages.exceptions import StorageError

                raise StorageError(f"Max size {self.config.max_size} would be exceeded")

        # Create stored file metadata
        stored_file = StoredFile(
            key=key,
            size=len(file_data),
            content_type=content_type,
            etag=_generate_etag(file_data),
            last_modified=datetime.now(tz=timezone.utc),
            metadata=metadata or {},
        )

        # Store the data and metadata
        self._files[key] = (file_data, stored_file)

        return stored_file

    async def get(self, key: str) -> AsyncIterator[bytes]:
        """Retrieve file contents as an async byte stream.

        Args:
            key: Storage path/key for the file

        Yields:
            Chunks of file data as bytes (single chunk for memory storage)

        Raises:
            StorageFileNotFoundError: If the file does not exist
        """
        if key not in self._files:
            raise StorageFileNotFoundError(key)

        data, _ = self._files[key]
        yield data

    async def get_bytes(self, key: str) -> bytes:
        """Retrieve entire file contents as bytes.

        Args:
            key: Storage path/key for the file

        Returns:
            Complete file contents as bytes

        Raises:
            StorageFileNotFoundError: If the file does not exist
        """
        if key not in self._files:
            raise StorageFileNotFoundError(key)

        data, _ = self._files[key]
        return data

    async def delete(self, key: str) -> None:
        """Delete a file.

        Args:
            key: Storage path/key for the file

        Raises:
            StorageFileNotFoundError: If the file does not exist
        """
        if key not in self._files:
            raise StorageFileNotFoundError(key)

        del self._files[key]

    async def exists(self, key: str) -> bool:
        """Check if a file exists.

        Args:
            key: Storage path/key for the file

        Returns:
            True if the file exists, False otherwise
        """
        return key in self._files

    async def list(
        self,
        prefix: str = "",
        *,
        limit: int | None = None,
    ) -> AsyncGenerator[StoredFile, None]:
        """List files with optional prefix filter.

        Args:
            prefix: Filter results to keys starting with this prefix
            limit: Maximum number of results to return

        Yields:
            StoredFile metadata for each matching file
        """
        count = 0
        for key, (_, stored_file) in self._files.items():
            if key.startswith(prefix):
                yield stored_file
                count += 1
                if limit is not None and count >= limit:
                    break

    async def url(
        self,
        key: str,
        *,
        expires_in: timedelta | None = None,
    ) -> str:
        """Generate a URL for accessing the file.

        Args:
            key: Storage path/key for the file
            expires_in: Optional expiration time (ignored for memory storage)

        Returns:
            URL string in the format memory://{key}

        Note:
            Memory storage URLs are not accessible externally and are primarily
            useful for testing and development.
        """
        return f"memory://{key}"

    async def copy(
        self,
        source: str,
        destination: str,
    ) -> StoredFile:
        """Copy a file within the storage backend.

        Args:
            source: Source key to copy from
            destination: Destination key to copy to

        Returns:
            StoredFile metadata for the new copy

        Raises:
            StorageFileNotFoundError: If the source file does not exist
        """
        if source not in self._files:
            raise StorageFileNotFoundError(source)

        data, stored_file = self._files[source]

        # Create new stored file with updated key and timestamp
        new_stored_file = StoredFile(
            key=destination,
            size=stored_file.size,
            content_type=stored_file.content_type,
            etag=stored_file.etag,
            last_modified=datetime.now(tz=timezone.utc),
            metadata=stored_file.metadata,
        )

        self._files[destination] = (data, new_stored_file)

        return new_stored_file

    async def move(
        self,
        source: str,
        destination: str,
    ) -> StoredFile:
        """Move/rename a file within the storage backend.

        Args:
            source: Source key to move from
            destination: Destination key to move to

        Returns:
            StoredFile metadata for the moved file

        Raises:
            StorageFileNotFoundError: If the source file does not exist
        """
        if source not in self._files:
            raise StorageFileNotFoundError(source)

        data, stored_file = self._files[source]

        # Create new stored file with updated key and timestamp
        new_stored_file = StoredFile(
            key=destination,
            size=stored_file.size,
            content_type=stored_file.content_type,
            etag=stored_file.etag,
            last_modified=datetime.now(tz=timezone.utc),
            metadata=stored_file.metadata,
        )

        self._files[destination] = (data, new_stored_file)
        del self._files[source]

        return new_stored_file

    async def info(self, key: str) -> StoredFile:
        """Get metadata about a file without downloading it.

        Args:
            key: Storage path/key for the file

        Returns:
            StoredFile with metadata

        Raises:
            StorageFileNotFoundError: If the file does not exist
        """
        if key not in self._files:
            raise StorageFileNotFoundError(key)

        _, stored_file = self._files[key]
        return stored_file
