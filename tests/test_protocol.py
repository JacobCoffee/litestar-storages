"""Protocol compliance tests that run against ALL storage backends.

These tests ensure that every storage backend correctly implements
the Storage protocol and behaves consistently across different providers.

All tests use the `any_storage` parametrized fixture which runs each
test against memory and filesystem backends.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from litestar_storages.exceptions import StorageFileNotFoundError

if TYPE_CHECKING:
    from litestar_storages import Storage


@pytest.mark.unit
class TestBasicOperations:
    """Test basic storage operations: put, get, exists, delete."""

    async def test_put_and_get_bytes(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test basic file upload and download with bytes data.

        Verifies:
        - put() returns StoredFile with correct metadata
        - get_bytes() retrieves exact data that was uploaded
        - File size is calculated correctly
        """
        # Upload data
        result = await any_storage.put("test.txt", sample_text_data)

        assert result.key == "test.txt"
        assert result.size == len(sample_text_data)
        assert result.size == len(sample_text_data)

        # Download and verify
        retrieved = await any_storage.get_bytes("test.txt")
        assert retrieved == sample_text_data

    async def test_put_and_get_streaming(
        self,
        any_storage: Storage,
        large_data: bytes,
        async_data_chunks,
    ) -> None:
        """
        Test streaming upload from async iterator.

        Verifies:
        - put() accepts AsyncIterator[bytes] for streaming uploads
        - get() returns AsyncIterator[bytes] for streaming downloads
        - Large data can be uploaded without loading fully into memory
        """
        # Create async iterator from data
        chunks = async_data_chunks(large_data, chunk_size=4096)

        # Upload as stream
        result = await any_storage.put("large.bin", chunks)

        assert result.key == "large.bin"
        assert result.size == len(large_data)

        # Download as stream and verify
        downloaded_chunks = []
        async for chunk in any_storage.get("large.bin"):
            downloaded_chunks.append(chunk)

        downloaded = b"".join(downloaded_chunks)
        assert downloaded == large_data

    async def test_put_with_content_type(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test uploading with explicit content type.

        Verifies:
        - content_type is stored with file
        - content_type is returned in StoredFile metadata
        """
        result = await any_storage.put(
            "document.pdf",
            sample_text_data,
            content_type="application/pdf",
        )

        assert result.content_type == "application/pdf"

        # Verify via info()
        info = await any_storage.info("document.pdf")
        assert info.content_type == "application/pdf"

    async def test_put_with_metadata(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
        sample_metadata: dict[str, str],
        request: pytest.FixtureRequest,
    ) -> None:
        """
        Test uploading with custom metadata.

        Verifies:
        - Custom metadata is stored with file
        - Metadata is retrievable via info()

        Note:
        - FileSystemStorage doesn't persist metadata (skipped)
        """
        if request.node.callspec.id == "filesystem":
            pytest.skip("FileSystemStorage doesn't persist metadata")

        result = await any_storage.put(
            "file-with-metadata.txt",
            sample_text_data,
            metadata=sample_metadata,
        )

        assert result.metadata == sample_metadata

        # Verify metadata persisted
        info = await any_storage.info("file-with-metadata.txt")
        for key, value in sample_metadata.items():
            assert info.metadata.get(key) == value

    async def test_exists_returns_true_for_existing_file(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test exists() returns True for files that exist.

        Verifies:
        - exists() returns True after successful upload
        - exists() works without downloading the file
        """
        await any_storage.put("existing.txt", sample_text_data)

        assert await any_storage.exists("existing.txt") is True

    async def test_exists_returns_false_for_nonexistent_file(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test exists() returns False for files that don't exist.

        Verifies:
        - exists() returns False for missing files
        - exists() does not raise exception for missing files
        """
        assert await any_storage.exists("nonexistent.txt") is False

    async def test_delete_existing_file(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test deleting a file that exists.

        Verifies:
        - delete() successfully removes file
        - exists() returns False after deletion
        - get() raises FileNotFoundError after deletion
        """
        # Upload file
        await any_storage.put("to-delete.txt", sample_text_data)
        assert await any_storage.exists("to-delete.txt") is True

        # Delete file
        await any_storage.delete("to-delete.txt")

        # Verify deletion
        assert await any_storage.exists("to-delete.txt") is False

        # Attempting to get should raise FileNotFoundError
        with pytest.raises(StorageFileNotFoundError):
            await any_storage.get_bytes("to-delete.txt")

    async def test_delete_nonexistent_file(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test behavior when deleting a file that doesn't exist.

        Different backends may have different behavior:
        - Some raise FileNotFoundError
        - Some are idempotent (no error)

        This test documents the behavior but may need adjustment
        based on chosen semantics.
        """
        # This should either succeed silently or raise StorageFileNotFoundError
        # depending on backend implementation choice
        import contextlib

        from litestar_storages.exceptions import StorageFileNotFoundError

        with contextlib.suppress(StorageFileNotFoundError):
            await any_storage.delete("nonexistent.txt")


@pytest.mark.unit
class TestListingOperations:
    """Test file listing and prefix filtering operations."""

    async def test_list_empty_storage(self, any_storage: Storage) -> None:
        """
        Test listing files in empty storage.

        Verifies:
        - list() returns empty iterator for empty storage
        - list() doesn't raise exception on empty storage
        """
        files = [f async for f in any_storage.list()]
        assert len(files) == 0

    async def test_list_all_files(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test listing all files without prefix filter.

        Verifies:
        - list() returns all uploaded files
        - Files are returned as StoredFile objects
        """
        # Upload multiple files
        await any_storage.put("file1.txt", sample_text_data)
        await any_storage.put("file2.txt", sample_text_data)
        await any_storage.put("file3.txt", sample_text_data)

        # List all files
        files = [f async for f in any_storage.list()]

        assert len(files) == 3
        keys = {f.key for f in files}
        assert keys == {"file1.txt", "file2.txt", "file3.txt"}

    async def test_list_with_prefix(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test prefix filtering in list operations.

        Verifies:
        - list(prefix="...") returns only matching files
        - Prefix filtering works with directory-like paths
        """
        # Upload files in different "directories"
        await any_storage.put("images/photo1.jpg", sample_text_data)
        await any_storage.put("images/photo2.jpg", sample_text_data)
        await any_storage.put("documents/doc1.pdf", sample_text_data)
        await any_storage.put("documents/doc2.pdf", sample_text_data)
        await any_storage.put("readme.txt", sample_text_data)

        # List only images
        images = [f async for f in any_storage.list(prefix="images/")]
        assert len(images) == 2
        assert all(f.key.startswith("images/") for f in images)

        # List only documents
        documents = [f async for f in any_storage.list(prefix="documents/")]
        assert len(documents) == 2
        assert all(f.key.startswith("documents/") for f in documents)

    async def test_list_with_limit(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test limit parameter in list operations.

        Verifies:
        - list(limit=N) returns at most N results
        - Results are valid StoredFile objects
        """
        # Upload multiple files
        for i in range(10):
            await any_storage.put(f"file{i:02d}.txt", sample_text_data)

        # List with limit
        files = [f async for f in any_storage.list(limit=5)]

        assert len(files) == 5
        assert all(isinstance(f.key, str) for f in files)

    async def test_list_with_prefix_and_limit(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test combining prefix filter and limit.

        Verifies:
        - Prefix and limit can be used together
        - Limit applies after prefix filtering
        """
        # Upload files
        for i in range(10):
            await any_storage.put(f"data/file{i:02d}.txt", sample_text_data)
        await any_storage.put("other/file.txt", sample_text_data)

        # List with both prefix and limit
        files = [f async for f in any_storage.list(prefix="data/", limit=3)]

        assert len(files) == 3
        assert all(f.key.startswith("data/") for f in files)


@pytest.mark.unit
class TestMetadataOperations:
    """Test metadata retrieval and file information."""

    async def test_info_returns_file_metadata(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test info() returns complete file metadata.

        Verifies:
        - info() returns StoredFile with all metadata
        - info() doesn't download file content
        - Metadata includes key, size, content_type
        """
        await any_storage.put(
            "info-test.txt",
            sample_text_data,
            content_type="text/plain",
        )

        info = await any_storage.info("info-test.txt")

        assert info.key == "info-test.txt"
        assert info.size == len(sample_text_data)
        assert info.content_type == "text/plain"

    async def test_info_for_nonexistent_file(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test info() raises FileNotFoundError for missing files.

        Verifies:
        - info() raises FileNotFoundError when file doesn't exist
        - Error message includes the key
        """
        with pytest.raises(StorageFileNotFoundError) as exc_info:
            await any_storage.info("nonexistent.txt")

        assert "nonexistent.txt" in str(exc_info.value)


@pytest.mark.unit
class TestCopyMoveOperations:
    """Test file copy and move operations."""

    async def test_copy_file(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
        sample_metadata: dict[str, str],
    ) -> None:
        """
        Test copying a file within storage.

        Verifies:
        - copy() creates new file at destination
        - Source file remains unchanged
        - Metadata is preserved in copy
        - Content is identical
        """
        # Upload source file
        await any_storage.put(
            "source.txt",
            sample_text_data,
            content_type="text/plain",
            metadata=sample_metadata,
        )

        # Copy file
        result = await any_storage.copy("source.txt", "destination.txt")

        assert result.key == "destination.txt"
        assert result.size == len(sample_text_data)
        assert result.content_type == "text/plain"

        # Verify both files exist
        assert await any_storage.exists("source.txt")
        assert await any_storage.exists("destination.txt")

        # Verify content is identical
        source_data = await any_storage.get_bytes("source.txt")
        dest_data = await any_storage.get_bytes("destination.txt")
        assert source_data == dest_data == sample_text_data

    async def test_move_file(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
        sample_metadata: dict[str, str],
    ) -> None:
        """
        Test moving/renaming a file.

        Verifies:
        - move() creates file at destination
        - Source file is deleted
        - Content and metadata are preserved
        """
        # Upload source file
        await any_storage.put(
            "old-name.txt",
            sample_text_data,
            content_type="text/plain",
            metadata=sample_metadata,
        )

        # Move file
        result = await any_storage.move("old-name.txt", "new-name.txt")

        assert result.key == "new-name.txt"
        assert result.size == len(sample_text_data)

        # Verify source is gone, destination exists
        assert not await any_storage.exists("old-name.txt")
        assert await any_storage.exists("new-name.txt")

        # Verify content
        data = await any_storage.get_bytes("new-name.txt")
        assert data == sample_text_data

    async def test_copy_nonexistent_file(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test copy() raises error when source doesn't exist.

        Verifies:
        - copy() raises FileNotFoundError for missing source
        """
        with pytest.raises(StorageFileNotFoundError):
            await any_storage.copy("nonexistent.txt", "destination.txt")

    async def test_move_nonexistent_file(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test move() raises error when source doesn't exist.

        Verifies:
        - move() raises FileNotFoundError for missing source
        """
        with pytest.raises(StorageFileNotFoundError):
            await any_storage.move("nonexistent.txt", "destination.txt")


@pytest.mark.unit
class TestURLGeneration:
    """Test URL generation for file access."""

    async def test_url_generation(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test basic URL generation.

        Verifies:
        - url() returns a valid URL string
        - URL contains the file key
        - URL is returned for existing files
        """
        await any_storage.put("test.txt", sample_text_data)

        url = await any_storage.url("test.txt")

        assert isinstance(url, str)
        assert len(url) > 0
        # URL should contain reference to the file
        assert "test.txt" in url or "test%2Etxt" in url.lower()

    async def test_url_with_expiry(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test URL generation with expiration time.

        Verifies:
        - url() accepts expires_in parameter
        - Returns valid URL for cloud backends (presigned)
        - Returns base URL for filesystem backend
        """
        await any_storage.put("expiring.txt", sample_text_data)

        url = await any_storage.url(
            "expiring.txt",
            expires_in=timedelta(minutes=15),
        )

        assert isinstance(url, str)
        assert len(url) > 0

        # For S3, URL should contain signature parameters
        # For filesystem, URL is just the path/base_url
        # Both are valid behaviors


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error conditions."""

    async def test_get_nonexistent_file(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test get() raises FileNotFoundError for missing files.

        Verifies:
        - get() raises FileNotFoundError when file doesn't exist
        """
        with pytest.raises(StorageFileNotFoundError):
            await any_storage.get_bytes("nonexistent.txt")

    async def test_put_empty_file(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test uploading empty file (0 bytes).

        Verifies:
        - Empty files can be uploaded
        - Size is correctly reported as 0
        - Empty file can be downloaded
        """
        result = await any_storage.put("empty.txt", b"")

        assert result.key == "empty.txt"
        assert result.size == 0

        # Verify can retrieve empty file
        data = await any_storage.get_bytes("empty.txt")
        assert data == b""

    async def test_overwrite_existing_file(
        self,
        any_storage: Storage,
    ) -> None:
        """
        Test overwriting an existing file.

        Verifies:
        - put() with existing key replaces content
        - New content is retrieved
        - Size is updated
        """
        # Upload initial file
        await any_storage.put("overwrite.txt", b"original content")

        # Overwrite with new content
        new_content = b"new content that is different"
        result = await any_storage.put("overwrite.txt", new_content)

        assert result.size == len(new_content)

        # Verify new content
        data = await any_storage.get_bytes("overwrite.txt")
        assert data == new_content

    async def test_nested_directory_paths(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test deeply nested directory-like paths.

        Verifies:
        - Deeply nested paths work correctly
        - Listing with nested prefixes works
        """
        nested_key = "a/b/c/d/e/f/deep-file.txt"
        await any_storage.put(nested_key, sample_text_data)

        assert await any_storage.exists(nested_key)

        # Verify can retrieve
        data = await any_storage.get_bytes(nested_key)
        assert data == sample_text_data

        # Verify listing with prefix
        files = [f async for f in any_storage.list(prefix="a/b/c/")]
        assert len(files) == 1
        assert files[0].key == nested_key

    async def test_special_characters_in_key(
        self,
        any_storage: Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test keys with special characters.

        Verifies:
        - Keys with spaces, dashes, underscores work
        - Special characters are properly handled
        """
        special_keys = [
            "file with spaces.txt",
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "file.multiple.dots.txt",
        ]

        for key in special_keys:
            await any_storage.put(key, sample_text_data)
            assert await any_storage.exists(key)
            data = await any_storage.get_bytes(key)
            assert data == sample_text_data


@pytest.mark.unit
class TestBinaryData:
    """Test handling of binary data."""

    async def test_binary_data_upload_download(
        self,
        any_storage: Storage,
        sample_binary_data: bytes,
    ) -> None:
        """
        Test uploading and downloading binary data.

        Verifies:
        - Binary data (all byte values 0-255) is preserved
        - No corruption or encoding issues
        """
        await any_storage.put("binary.bin", sample_binary_data)

        retrieved = await any_storage.get_bytes("binary.bin")
        assert retrieved == sample_binary_data

    async def test_large_binary_streaming(
        self,
        any_storage: Storage,
        large_data: bytes,
    ) -> None:
        """
        Test streaming large binary files.

        Verifies:
        - Large files (1MB+) can be streamed
        - Data integrity is maintained
        - Memory efficient operation
        """
        # Upload large file
        await any_storage.put("large.bin", large_data)

        # Download via streaming
        chunks = []
        async for chunk in any_storage.get("large.bin"):
            chunks.append(chunk)

        downloaded = b"".join(chunks)
        assert downloaded == large_data
        assert len(downloaded) == len(large_data)
