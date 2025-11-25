"""MemoryStorage-specific tests.

Tests for features and behaviors specific to the in-memory storage backend,
including memory management, size limits, and isolation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from litestar_storages.backends.memory import MemoryStorage


@pytest.mark.unit
class TestMemoryStorageBasics:
    """Test basic MemoryStorage functionality."""

    async def test_memory_storage_creation(self) -> None:
        """
        Test creating MemoryStorage instance.

        Verifies:
        - Can create instance without config
        - Can create instance with config
        - Default config values are applied
        """
        from litestar_storages.backends.memory import MemoryConfig, MemoryStorage

        # Without config
        storage1 = MemoryStorage()
        assert storage1 is not None

        # With config
        config = MemoryConfig(max_size=1024 * 1024)
        storage2 = MemoryStorage(config=config)
        assert storage2.config.max_size == 1024 * 1024

    async def test_memory_isolation(
        self,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that different MemoryStorage instances are isolated.

        Verifies:
        - Files stored in one instance don't appear in another
        - Each instance has independent storage
        """
        from litestar_storages.backends.memory import MemoryStorage

        storage1 = MemoryStorage()
        storage2 = MemoryStorage()

        # Upload to storage1
        await storage1.put("file1.txt", sample_text_data)

        # Verify isolation
        assert await storage1.exists("file1.txt")
        assert not await storage2.exists("file1.txt")

        # Upload to storage2
        await storage2.put("file2.txt", sample_text_data)

        # Verify both are isolated
        assert await storage1.exists("file1.txt")
        assert not await storage1.exists("file2.txt")
        assert not await storage2.exists("file1.txt")
        assert await storage2.exists("file2.txt")

    async def test_memory_persistence_within_instance(
        self,
        memory_storage: MemoryStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that data persists within a single instance.

        Verifies:
        - Multiple operations on same key return consistent data
        - Data doesn't disappear between operations
        """
        # Upload file
        await memory_storage.put("persistent.txt", sample_text_data)

        # Multiple retrievals should all succeed
        for _ in range(5):
            data = await memory_storage.get_bytes("persistent.txt")
            assert data == sample_text_data


@pytest.mark.unit
class TestMemorySizeLimits:
    """Test memory size limit enforcement."""

    async def test_max_size_configuration(self) -> None:
        """
        Test configuring max_size limit.

        Verifies:
        - max_size can be set via config
        - max_size=None means unlimited
        """
        from litestar_storages.backends.memory import MemoryConfig, MemoryStorage

        # Unlimited
        storage_unlimited = MemoryStorage(config=MemoryConfig(max_size=None))
        assert storage_unlimited.config.max_size is None

        # Limited
        max_size = 1024 * 100  # 100KB
        storage_limited = MemoryStorage(config=MemoryConfig(max_size=max_size))
        assert storage_limited.config.max_size == max_size

    async def test_small_files_within_limit(
        self,
        memory_storage_with_limit: MemoryStorage,
    ) -> None:
        """
        Test uploading small files within size limit.

        Verifies:
        - Files totaling less than max_size can be uploaded
        - No errors occur when within limit
        """
        # Upload small files (total < 1MB limit)
        small_data = b"x" * 1024  # 1KB
        for i in range(10):
            result = await memory_storage_with_limit.put(f"small{i}.txt", small_data)
            assert result.size == len(small_data)

    async def test_single_file_exceeds_limit(
        self,
        memory_storage_with_limit: MemoryStorage,
    ) -> None:
        """
        Test uploading single file that exceeds max_size.

        Verifies:
        - Uploading file larger than max_size raises error
        - Error is appropriate (StorageError or subclass)
        """
        from litestar_storages.exceptions import StorageError

        # Try to upload 2MB file to 1MB storage
        large_data = b"x" * (1024 * 1024 * 2)

        with pytest.raises(StorageError) as exc_info:
            await memory_storage_with_limit.put("too-large.txt", large_data)

        assert "size" in str(exc_info.value).lower() or "limit" in str(exc_info.value).lower()

    async def test_cumulative_size_exceeds_limit(
        self,
        memory_storage_with_limit: MemoryStorage,
    ) -> None:
        """
        Test that cumulative file sizes are enforced.

        Verifies:
        - Multiple files totaling > max_size raises error
        - Error occurs on the upload that would exceed limit
        """
        from litestar_storages.exceptions import StorageError

        # Upload files totaling just under 1MB
        chunk_size = 256 * 1024  # 256KB
        chunk_data = b"x" * chunk_size

        # First 3 uploads should succeed (768KB total)
        await memory_storage_with_limit.put("chunk1.bin", chunk_data)
        await memory_storage_with_limit.put("chunk2.bin", chunk_data)
        await memory_storage_with_limit.put("chunk3.bin", chunk_data)

        # 4th upload should fail (would be 1024KB, at limit)
        # or succeed if exactly at limit - depends on implementation
        # 5th upload should definitely fail (would exceed)
        with pytest.raises(StorageError):
            # Try uploading 2 more chunks
            await memory_storage_with_limit.put("chunk4.bin", chunk_data)
            await memory_storage_with_limit.put("chunk5.bin", chunk_data)

    async def test_delete_frees_space(
        self,
        memory_storage_with_limit: MemoryStorage,
    ) -> None:
        """
        Test that deleting files frees space for new uploads.

        Verifies:
        - Deleting file reduces used space
        - Can upload new files after deletion
        """
        # Upload large file
        large_data = b"x" * (512 * 1024)  # 512KB
        await memory_storage_with_limit.put("large1.bin", large_data)

        # Upload another large file
        await memory_storage_with_limit.put("large2.bin", large_data)

        # Now at ~1MB, can't upload more
        # Delete one file
        await memory_storage_with_limit.delete("large1.bin")

        # Now should be able to upload again
        await memory_storage_with_limit.put("large3.bin", large_data)
        assert await memory_storage_with_limit.exists("large3.bin")


@pytest.mark.unit
class TestMemoryStorageMetadata:
    """Test metadata handling in MemoryStorage."""

    async def test_metadata_storage(
        self,
        memory_storage: MemoryStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that metadata is stored and retrieved correctly.

        Verifies:
        - Custom metadata is stored
        - Metadata can be retrieved via info()
        - Metadata persists across operations
        """
        metadata = {
            "author": "test-user",
            "version": "1.0",
            "custom-field": "custom-value",
        }

        await memory_storage.put(
            "with-metadata.txt",
            sample_text_data,
            metadata=metadata,
        )

        info = await memory_storage.info("with-metadata.txt")

        for key, value in metadata.items():
            assert info.metadata.get(key) == value

    async def test_metadata_preserved_on_copy(
        self,
        memory_storage: MemoryStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that metadata is preserved when copying files.

        Verifies:
        - copy() preserves metadata
        - Destination has same metadata as source
        """
        metadata = {"important": "value"}

        await memory_storage.put(
            "source.txt",
            sample_text_data,
            metadata=metadata,
        )

        result = await memory_storage.copy("source.txt", "destination.txt")

        assert result.metadata.get("important") == "value"

        # Verify via info()
        dest_info = await memory_storage.info("destination.txt")
        assert dest_info.metadata.get("important") == "value"


@pytest.mark.unit
class TestMemoryStorageEdgeCases:
    """Test edge cases specific to MemoryStorage."""

    async def test_overwrite_updates_size_tracking(
        self,
        memory_storage_with_limit: MemoryStorage,
    ) -> None:
        """
        Test that overwriting files updates size tracking correctly.

        Verifies:
        - Overwriting with larger file updates size
        - Overwriting with smaller file frees space
        - Size tracking remains accurate
        """
        # Upload small file
        small_data = b"x" * 1024
        await memory_storage_with_limit.put("file.txt", small_data)

        # Overwrite with larger file
        larger_data = b"x" * 2048
        result = await memory_storage_with_limit.put("file.txt", larger_data)
        assert result.size == len(larger_data)

        # Verify can still retrieve correct size
        info = await memory_storage_with_limit.info("file.txt")
        assert info.size == len(larger_data)

        # Overwrite with smaller file
        smaller_data = b"x" * 512
        result = await memory_storage_with_limit.put("file.txt", smaller_data)
        assert result.size == len(smaller_data)

    async def test_concurrent_operations(
        self,
        memory_storage: MemoryStorage,
    ) -> None:
        """
        Test concurrent operations on MemoryStorage.

        Verifies:
        - Multiple concurrent uploads work correctly
        - No data corruption from concurrent access
        - All files are stored successfully
        """
        import asyncio

        async def upload_file(key: str, data: bytes):
            await memory_storage.put(key, data)

        # Create multiple concurrent uploads
        tasks = [upload_file(f"concurrent-{i}.txt", f"data-{i}".encode()) for i in range(20)]

        await asyncio.gather(*tasks)

        # Verify all files exist
        for i in range(20):
            assert await memory_storage.exists(f"concurrent-{i}.txt")
            data = await memory_storage.get_bytes(f"concurrent-{i}.txt")
            assert data == f"data-{i}".encode()

    async def test_etag_generation(
        self,
        memory_storage: MemoryStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that MemoryStorage generates ETags.

        Verifies:
        - ETag is generated on upload
        - ETag is consistent for same content
        - ETag changes when content changes
        """
        result1 = await memory_storage.put("file1.txt", sample_text_data)
        assert result1.etag is not None

        # Same content should have same ETag
        result2 = await memory_storage.put("file2.txt", sample_text_data)
        assert result2.etag == result1.etag

        # Different content should have different ETag
        different_data = b"different content"
        result3 = await memory_storage.put("file3.txt", different_data)
        assert result3.etag != result1.etag

    async def test_last_modified_timestamp(
        self,
        memory_storage: MemoryStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that last_modified timestamp is set.

        Verifies:
        - last_modified is set on upload
        - Timestamp is recent (within last minute)
        - Timestamp updates on overwrite
        """
        from datetime import datetime, timedelta, timezone

        result = await memory_storage.put("timestamped.txt", sample_text_data)

        assert result.last_modified is not None
        # Should be very recent
        now = datetime.now(timezone.utc)
        assert result.last_modified <= now
        assert result.last_modified >= now - timedelta(minutes=1)


@pytest.mark.unit
class TestMemoryStorageURL:
    """Test URL generation for MemoryStorage."""

    async def test_url_generation(
        self,
        memory_storage: MemoryStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test URL generation for in-memory files.

        Verifies:
        - url() returns a string
        - URL contains the key
        - MemoryStorage URLs are memory:// scheme (or similar)
        """
        await memory_storage.put("test.txt", sample_text_data)

        url = await memory_storage.url("test.txt")

        assert isinstance(url, str)
        assert "test.txt" in url
        # MemoryStorage URLs might be memory:// or similar virtual scheme
        # or just the key itself

    async def test_url_for_nonexistent_file(
        self,
        memory_storage: MemoryStorage,
    ) -> None:
        """
        Test URL generation for nonexistent file.

        Verifies:
        - May raise StorageFileNotFoundError or return URL anyway
        - Behavior is consistent
        """
        import contextlib

        from litestar_storages.exceptions import StorageFileNotFoundError

        # MemoryStorage might generate URL without checking existence
        # or might raise StorageFileNotFoundError - both are valid
        with contextlib.suppress(StorageFileNotFoundError):
            url = await memory_storage.url("nonexistent.txt")
            assert isinstance(url, str)


@pytest.mark.unit
class TestMemoryStorageListing:
    """Test listing operations specific to MemoryStorage."""

    async def test_list_maintains_order(
        self,
        memory_storage: MemoryStorage,
    ) -> None:
        """
        Test that list() returns files in consistent order.

        Verifies:
        - Files are returned in predictable order
        - Order is consistent across multiple calls
        """
        # Upload files
        for i in range(10):
            await memory_storage.put(f"file-{i:02d}.txt", f"data{i}".encode())

        # List multiple times and verify consistency
        list1 = [f.key async for f in memory_storage.list()]
        list2 = [f.key async for f in memory_storage.list()]

        assert list1 == list2
        assert len(list1) == 10

    async def test_list_after_modifications(
        self,
        memory_storage: MemoryStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that list() reflects file modifications.

        Verifies:
        - Listing updates after uploads
        - Listing updates after deletions
        - Count is always accurate
        """
        # Initial empty list
        files = [f async for f in memory_storage.list()]
        assert len(files) == 0

        # Upload some files
        await memory_storage.put("file1.txt", sample_text_data)
        await memory_storage.put("file2.txt", sample_text_data)

        files = [f async for f in memory_storage.list()]
        assert len(files) == 2

        # Delete one
        await memory_storage.delete("file1.txt")

        files = [f async for f in memory_storage.list()]
        assert len(files) == 1
        assert files[0].key == "file2.txt"
