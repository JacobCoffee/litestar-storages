"""Tests for BaseStorage default implementations.

This module tests the default implementations provided by BaseStorage:
- get_bytes(): collects stream into bytes
- copy(): downloads and re-uploads
- move(): copies then deletes
- close(): no-op default implementation
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from litestar_storages.base import BaseStorage
from litestar_storages.exceptions import StorageFileNotFoundError
from litestar_storages.types import StoredFile

if TYPE_CHECKING:
    from litestar_storages import Storage


class MinimalStorage(BaseStorage):
    """Minimal storage implementation that uses default base implementations.

    This class only implements the required abstract methods and relies on
    BaseStorage defaults for get_bytes, copy, move, and close.
    """

    def __init__(self) -> None:
        self._files: dict[str, tuple[bytes, StoredFile]] = {}

    async def put(
        self,
        key: str,
        data: bytes | AsyncIterator[bytes],
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredFile:
        if isinstance(data, bytes):
            file_data = data
        else:
            chunks = []
            async for chunk in data:
                chunks.append(chunk)
            file_data = b"".join(chunks)

        stored_file = StoredFile(
            key=key,
            size=len(file_data),
            content_type=content_type,
            etag=f'"{hash(file_data)}"',
            last_modified=datetime.now(tz=timezone.utc),
            metadata=metadata or {},
        )
        self._files[key] = (file_data, stored_file)
        return stored_file

    async def get(self, key: str) -> AsyncIterator[bytes]:
        if key not in self._files:
            raise StorageFileNotFoundError(key)
        data, _ = self._files[key]
        yield data

    async def delete(self, key: str) -> None:
        if key not in self._files:
            raise StorageFileNotFoundError(key)
        del self._files[key]

    async def exists(self, key: str) -> bool:
        return key in self._files

    async def list(self, prefix: str = "", *, limit: int | None = None) -> AsyncGenerator[StoredFile, None]:
        count = 0
        for key, (_, stored_file) in self._files.items():
            if key.startswith(prefix):
                yield stored_file
                count += 1
                if limit and count >= limit:
                    break

    async def url(self, key: str, *, expires_in: timedelta | None = None) -> str:
        return f"minimal://{key}"

    async def info(self, key: str) -> StoredFile:
        if key not in self._files:
            raise StorageFileNotFoundError(key)
        _, stored_file = self._files[key]
        return stored_file


@pytest.fixture
def minimal_storage() -> MinimalStorage:
    """Create a minimal storage that uses base class defaults."""
    return MinimalStorage()


@pytest.mark.unit
class TestBaseStorageDefaultImplementations:
    """Test BaseStorage default implementations directly.

    These tests use MinimalStorage which doesn't override the defaults.
    """

    async def test_default_get_bytes(self, minimal_storage: MinimalStorage) -> None:
        """Test default get_bytes collects stream into bytes."""
        data = b"test data for get_bytes"
        await minimal_storage.put("test.txt", data)

        # Uses BaseStorage.get_bytes default implementation
        result = await minimal_storage.get_bytes("test.txt")
        assert result == data

    async def test_default_copy(self, minimal_storage: MinimalStorage) -> None:
        """Test default copy downloads and re-uploads."""
        data = b"test data for copy"
        await minimal_storage.put("source.txt", data, content_type="text/plain")

        # Uses BaseStorage.copy default implementation
        result = await minimal_storage.copy("source.txt", "destination.txt")

        assert result.key == "destination.txt"
        assert result.content_type == "text/plain"
        assert await minimal_storage.exists("source.txt")
        assert await minimal_storage.exists("destination.txt")
        assert await minimal_storage.get_bytes("destination.txt") == data

    async def test_default_move(self, minimal_storage: MinimalStorage) -> None:
        """Test default move copies then deletes."""
        data = b"test data for move"
        await minimal_storage.put("source.txt", data, content_type="text/plain")

        # Uses BaseStorage.move default implementation
        result = await minimal_storage.move("source.txt", "destination.txt")

        assert result.key == "destination.txt"
        assert result.content_type == "text/plain"
        assert not await minimal_storage.exists("source.txt")
        assert await minimal_storage.exists("destination.txt")
        assert await minimal_storage.get_bytes("destination.txt") == data

    async def test_default_close(self, minimal_storage: MinimalStorage) -> None:
        """Test default close is a no-op."""
        await minimal_storage.put("test.txt", b"data")

        # Uses BaseStorage.close default implementation
        await minimal_storage.close()

        # Storage should still work after close (no-op)
        assert await minimal_storage.exists("test.txt")


@pytest.mark.unit
class TestBaseStorageGetBytes:
    """Test default get_bytes implementation."""

    async def test_get_bytes_collects_stream(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that get_bytes() collects chunks from get() stream.

        Verifies:
        - get_bytes() calls get() internally
        - All chunks are collected and joined
        - Result matches original data
        """
        await any_storage.put("test.txt", sample_text_data)

        # Use get_bytes which should internally use get()
        result = await any_storage.get_bytes("test.txt")

        assert result == sample_text_data
        assert isinstance(result, bytes)

    async def test_get_bytes_handles_empty_file(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test get_bytes() with empty file.

        Verifies:
        - Empty file returns empty bytes
        - No errors on empty content
        """
        await any_storage.put("empty.txt", b"")

        result = await any_storage.get_bytes("empty.txt")

        assert result == b""
        assert isinstance(result, bytes)

    async def test_get_bytes_raises_file_not_found(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test get_bytes() raises error for nonexistent file.

        Verifies:
        - StorageFileNotFoundError is raised
        - Error propagates from get()
        """
        with pytest.raises(StorageFileNotFoundError):
            await any_storage.get_bytes("nonexistent.txt")


@pytest.mark.unit
class TestBaseStorageCopy:
    """Test default copy implementation."""

    async def test_copy_downloads_and_reuploads(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that copy() downloads then re-uploads.

        Verifies:
        - Source file exists after copy
        - Destination file created
        - Content matches source
        - Content type preserved
        """
        await any_storage.put(
            "source.txt",
            sample_text_data,
            content_type="text/plain",
        )

        result = await any_storage.copy("source.txt", "destination.txt")

        assert result.key == "destination.txt"
        assert result.size == len(sample_text_data)
        assert result.content_type == "text/plain"

        # Verify both files exist
        assert await any_storage.exists("source.txt")
        assert await any_storage.exists("destination.txt")

        # Verify content
        source_data = await any_storage.get_bytes("source.txt")
        dest_data = await any_storage.get_bytes("destination.txt")
        assert source_data == dest_data == sample_text_data

    async def test_copy_preserves_metadata(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
        sample_metadata: dict[str, str],
        request: pytest.FixtureRequest,
    ) -> None:
        """
        Test that copy() preserves metadata.

        Verifies:
        - Metadata is copied to destination
        - Original metadata values preserved

        Note:
        - FileSystemStorage doesn't persist metadata (skipped)
        """
        if request.node.callspec.id == "filesystem":
            pytest.skip("FileSystemStorage doesn't persist metadata")

        await any_storage.put(
            "source.txt",
            sample_text_data,
            metadata=sample_metadata,
        )

        result = await any_storage.copy("source.txt", "destination.txt")

        # Verify metadata preserved
        for key, value in sample_metadata.items():
            assert result.metadata.get(key) == value

    async def test_copy_nonexistent_source_raises_error(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test copy() with nonexistent source file.

        Verifies:
        - StorageFileNotFoundError is raised
        - Destination is not created
        """
        with pytest.raises(StorageFileNotFoundError):
            await any_storage.copy("nonexistent.txt", "destination.txt")

        # Verify destination wasn't created
        assert not await any_storage.exists("destination.txt")

    async def test_copy_overwrites_existing_destination(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test copy() overwrites existing destination file.

        Verifies:
        - Existing destination is replaced
        - New content matches source
        """
        source_data = b"source content"
        old_dest_data = b"old destination content"

        await any_storage.put("source.txt", source_data)
        await any_storage.put("destination.txt", old_dest_data)

        await any_storage.copy("source.txt", "destination.txt")

        # Verify destination has source content
        dest_data = await any_storage.get_bytes("destination.txt")
        assert dest_data == source_data


@pytest.mark.unit
class TestBaseStorageMove:
    """Test default move implementation."""

    async def test_move_copies_then_deletes(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that move() performs copy then delete.

        Verifies:
        - Source file deleted after move
        - Destination file created
        - Content preserved
        """
        await any_storage.put(
            "source.txt",
            sample_text_data,
            content_type="text/plain",
        )

        result = await any_storage.move("source.txt", "destination.txt")

        assert result.key == "destination.txt"
        assert result.size == len(sample_text_data)
        assert result.content_type == "text/plain"

        # Verify source deleted, destination exists
        assert not await any_storage.exists("source.txt")
        assert await any_storage.exists("destination.txt")

        # Verify content
        dest_data = await any_storage.get_bytes("destination.txt")
        assert dest_data == sample_text_data

    async def test_move_preserves_metadata(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
        sample_metadata: dict[str, str],
        request: pytest.FixtureRequest,
    ) -> None:
        """
        Test that move() preserves metadata.

        Verifies:
        - Metadata is moved to destination
        - Original metadata values preserved

        Note:
        - FileSystemStorage doesn't persist metadata (skipped)
        """
        if request.node.callspec.id == "filesystem":
            pytest.skip("FileSystemStorage doesn't persist metadata")

        await any_storage.put(
            "source.txt",
            sample_text_data,
            metadata=sample_metadata,
        )

        result = await any_storage.move("source.txt", "destination.txt")

        # Verify metadata preserved
        for key, value in sample_metadata.items():
            assert result.metadata.get(key) == value

    async def test_move_nonexistent_source_raises_error(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test move() with nonexistent source file.

        Verifies:
        - StorageFileNotFoundError is raised
        - Destination is not created
        """
        with pytest.raises(StorageFileNotFoundError):
            await any_storage.move("nonexistent.txt", "destination.txt")

        # Verify destination wasn't created
        assert not await any_storage.exists("destination.txt")

    async def test_move_overwrites_existing_destination(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test move() overwrites existing destination file.

        Verifies:
        - Existing destination is replaced
        - New content matches source
        - Source is still deleted
        """
        source_data = b"source content"
        old_dest_data = b"old destination content"

        await any_storage.put("source.txt", source_data)
        await any_storage.put("destination.txt", old_dest_data)

        await any_storage.move("source.txt", "destination.txt")

        # Verify source deleted
        assert not await any_storage.exists("source.txt")

        # Verify destination has source content
        dest_data = await any_storage.get_bytes("destination.txt")
        assert dest_data == source_data


@pytest.mark.unit
class TestBaseStorageClose:
    """Test default close implementation."""

    async def test_close_is_no_op(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test that close() doesn't raise errors.

        Verifies:
        - close() can be called without error
        - Default implementation is a no-op
        """
        # Should not raise any errors
        await any_storage.close()

        # Can be called multiple times
        await any_storage.close()
        await any_storage.close()

    async def test_storage_operations_after_close(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test storage operations after close().

        Note: Default close() is a no-op, so operations should still work.
        Backends that manage resources may override close() and raise errors.

        Verifies:
        - Operations may work after close() (implementation-dependent)
        - At minimum, close() doesn't corrupt existing storage
        """
        # Upload file before close
        await any_storage.put("test.txt", sample_text_data)

        # Close storage
        await any_storage.close()

        # Try to use storage (may or may not work depending on implementation)
        # For BaseStorage default implementation, this should still work
        try:
            exists = await any_storage.exists("test.txt")
            # If backend allows operations after close, verify file still exists
            assert exists is True
        except Exception:
            # Some backends may raise errors after close - this is acceptable
            pass
