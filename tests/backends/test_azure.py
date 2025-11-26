"""AzureStorage-specific tests.

Tests for Azure Blob Storage backend using Azurite emulator for mocking.
Tests Azure-specific features like SAS URLs, prefix handling, and
container operations.

NOTE: Azure tests use Azurite emulator for testing without real Azure credentials.
These tests are marked as integration tests and can be skipped with
`pytest -m "not integration"`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from litestar_storages.backends.azure import AzureStorage

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.mark.unit
class TestAzureStorageBasics:
    """Test basic AzureStorage functionality."""

    async def test_azure_storage_creation(self) -> None:
        """
        Test creating AzureStorage instance.

        Verifies:
        - Can create instance with minimal config
        - Config values are stored correctly
        - Lazy client initialization
        """
        from litestar_storages.backends.azure import AzureConfig, AzureStorage

        config = AzureConfig(
            container="test-container",
            connection_string="DefaultEndpointsProtocol=http;AccountName=test;AccountKey=key;",
        )
        storage = AzureStorage(config=config)

        assert storage.config.container == "test-container"
        assert storage.config.connection_string is not None

    async def test_azure_with_account_url(self) -> None:
        """
        Test AzureStorage with account URL.

        Verifies:
        - Account URL can be provided
        - Config stores the values correctly
        """
        from litestar_storages.backends.azure import AzureConfig, AzureStorage

        config = AzureConfig(
            container="test-container",
            account_url="https://myaccount.blob.core.windows.net",
            account_key="test-key",
        )
        storage = AzureStorage(config=config)

        assert storage.config.account_url == "https://myaccount.blob.core.windows.net"
        assert storage.config.account_key == "test-key"

    async def test_azure_requires_container(self) -> None:
        """
        Test that AzureStorage requires container name.

        Verifies:
        - ConfigurationError raised when container is empty
        """
        from litestar_storages.backends.azure import AzureConfig, AzureStorage
        from litestar_storages.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError, match="container name is required"):
            AzureStorage(config=AzureConfig(container="", connection_string="test"))

    async def test_azure_requires_auth(self) -> None:
        """
        Test that AzureStorage requires authentication.

        Verifies:
        - ConfigurationError raised when neither connection_string nor account_url provided
        """
        from litestar_storages.backends.azure import AzureConfig, AzureStorage
        from litestar_storages.exceptions import ConfigurationError

        with pytest.raises(ConfigurationError, match="connection_string or account_url is required"):
            AzureStorage(config=AzureConfig(container="test"))


@pytest.mark.unit
class TestAzureKeyHandling:
    """Test key prefix handling."""

    async def test_key_prefix_applied(self) -> None:
        """
        Test that key prefix is correctly applied.

        Verifies:
        - Prefix is added to keys
        - Leading slashes are handled correctly
        """
        from litestar_storages.backends.azure import AzureConfig, AzureStorage

        storage = AzureStorage(
            config=AzureConfig(
                container="test-container",
                connection_string="DefaultEndpointsProtocol=http;AccountName=test;AccountKey=key;",
                prefix="uploads/",
            )
        )

        assert storage._get_key("test.txt") == "uploads/test.txt"
        assert storage._get_key("/test.txt") == "uploads/test.txt"
        assert storage._get_key("path/to/file.txt") == "uploads/path/to/file.txt"

    async def test_key_prefix_stripped(self) -> None:
        """
        Test that prefix is correctly stripped from keys.

        Verifies:
        - Prefix is removed from returned keys
        """
        from litestar_storages.backends.azure import AzureConfig, AzureStorage

        storage = AzureStorage(
            config=AzureConfig(
                container="test-container",
                connection_string="DefaultEndpointsProtocol=http;AccountName=test;AccountKey=key;",
                prefix="uploads/",
            )
        )

        assert storage._strip_prefix("uploads/test.txt") == "test.txt"
        assert storage._strip_prefix("uploads/path/to/file.txt") == "path/to/file.txt"

    async def test_no_prefix_handling(self) -> None:
        """
        Test key handling without prefix.

        Verifies:
        - Keys work correctly without prefix configured
        """
        from litestar_storages.backends.azure import AzureConfig, AzureStorage

        storage = AzureStorage(
            config=AzureConfig(
                container="test-container",
                connection_string="DefaultEndpointsProtocol=http;AccountName=test;AccountKey=key;",
            )
        )

        assert storage._get_key("test.txt") == "test.txt"
        assert storage._strip_prefix("test.txt") == "test.txt"


class TestAzureOperations:
    """Test Azure storage operations with emulator."""

    async def test_azure_basic_operations(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test basic Azure operations with emulator.

        Verifies:
        - Upload works
        - Download retrieves correct data
        """
        # Upload
        result = await azure_storage.put("test.txt", sample_text_data)
        assert result.key == "test.txt"
        assert result.size == len(sample_text_data)

        # Download
        data = await azure_storage.get_bytes("test.txt")
        assert data == sample_text_data

    async def test_azure_with_content_type(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test Azure upload with content type.

        Verifies:
        - Content type is stored correctly
        """
        result = await azure_storage.put(
            "test.txt",
            sample_text_data,
            content_type="text/plain",
        )
        assert result.content_type == "text/plain"

    async def test_azure_with_metadata(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
        sample_metadata: dict[str, str],
    ) -> None:
        """
        Test Azure upload with custom metadata.

        Verifies:
        - Metadata is stored and retrieved correctly
        """
        result = await azure_storage.put(
            "test.txt",
            sample_text_data,
            metadata=sample_metadata,
        )
        assert result.metadata == sample_metadata

    async def test_azure_exists(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test file existence check.

        Verifies:
        - exists() returns True for existing files
        - exists() returns False for non-existing files
        """
        # File doesn't exist yet
        assert await azure_storage.exists("test.txt") is False

        # Upload file
        await azure_storage.put("test.txt", sample_text_data)

        # File exists now
        assert await azure_storage.exists("test.txt") is True

    async def test_azure_delete(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test file deletion.

        Verifies:
        - Delete removes the file
        - File no longer exists after deletion
        """
        # Upload file
        await azure_storage.put("test.txt", sample_text_data)
        assert await azure_storage.exists("test.txt") is True

        # Delete file
        await azure_storage.delete("test.txt")
        assert await azure_storage.exists("test.txt") is False

    async def test_azure_list(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test file listing.

        Verifies:
        - List returns uploaded files
        - Prefix filtering works
        """
        # Upload multiple files
        await azure_storage.put("a/file1.txt", sample_text_data)
        await azure_storage.put("a/file2.txt", sample_text_data)
        await azure_storage.put("b/file3.txt", sample_text_data)

        # List all
        all_files = [f async for f in azure_storage.list()]
        assert len(all_files) == 3

        # List with prefix
        a_files = [f async for f in azure_storage.list(prefix="a/")]
        assert len(a_files) == 2
        assert all(f.key.startswith("a/") for f in a_files)

    async def test_azure_list_with_limit(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test file listing with limit.

        Verifies:
        - Limit parameter restricts results
        """
        # Upload multiple files
        for i in range(5):
            await azure_storage.put(f"file{i}.txt", sample_text_data)

        # List with limit
        limited_files = [f async for f in azure_storage.list(limit=3)]
        assert len(limited_files) == 3

    async def test_azure_copy(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test file copy operation.

        Verifies:
        - Copy creates new file
        - Original file remains
        - Content is identical
        """
        # Upload original
        await azure_storage.put("original.txt", sample_text_data)

        # Copy
        result = await azure_storage.copy("original.txt", "copy.txt")
        assert result.key == "copy.txt"

        # Both exist
        assert await azure_storage.exists("original.txt")
        assert await azure_storage.exists("copy.txt")

        # Content is identical
        original_data = await azure_storage.get_bytes("original.txt")
        copy_data = await azure_storage.get_bytes("copy.txt")
        assert original_data == copy_data

    async def test_azure_move(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test file move operation.

        Verifies:
        - Move creates new file
        - Original file is deleted
        - Content is preserved
        """
        # Upload original
        await azure_storage.put("original.txt", sample_text_data)

        # Move
        result = await azure_storage.move("original.txt", "moved.txt")
        assert result.key == "moved.txt"

        # Original doesn't exist, moved does
        assert not await azure_storage.exists("original.txt")
        assert await azure_storage.exists("moved.txt")

        # Content is preserved
        moved_data = await azure_storage.get_bytes("moved.txt")
        assert moved_data == sample_text_data

    async def test_azure_info(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test file info retrieval.

        Verifies:
        - Info returns file metadata
        - Size is correct
        """
        # Upload file
        await azure_storage.put(
            "test.txt",
            sample_text_data,
            content_type="text/plain",
        )

        # Get info
        info = await azure_storage.info("test.txt")
        assert info.key == "test.txt"
        assert info.size == len(sample_text_data)

    async def test_azure_streaming_get(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test streaming file retrieval.

        Verifies:
        - get() yields chunks
        - All data is retrieved
        """
        # Upload file
        await azure_storage.put("test.txt", sample_text_data)

        # Stream download
        chunks = []
        async for chunk in azure_storage.get("test.txt"):
            chunks.append(chunk)

        # Reconstruct data
        data = b"".join(chunks)
        assert data == sample_text_data

    async def test_azure_not_found_error(
        self,
        azure_storage: AzureStorage,
    ) -> None:
        """
        Test error handling for non-existent files.

        Verifies:
        - StorageFileNotFoundError is raised
        """
        from litestar_storages.exceptions import StorageFileNotFoundError

        with pytest.raises(StorageFileNotFoundError):
            await azure_storage.get_bytes("nonexistent.txt")


class TestAzureSASURLs:
    """Test SAS URL generation."""

    async def test_sas_url_generation(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test SAS URL generation.

        Verifies:
        - SAS URL is generated correctly
        - URL contains SAS token
        """
        # Upload file
        await azure_storage.put("test.txt", sample_text_data)

        # Generate URL
        url = await azure_storage.url("test.txt")
        assert isinstance(url, str)
        assert len(url) > 0
        # SAS tokens contain these parameters
        assert "sig=" in url or "sv=" in url

    async def test_sas_url_with_expiry(
        self,
        azure_storage: AzureStorage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test SAS URL with custom expiration.
        """
        await azure_storage.put("test.txt", sample_text_data)

        url = await azure_storage.url(
            "test.txt",
            expires_in=timedelta(minutes=30),
        )
        assert isinstance(url, str)


class TestAzureClose:
    """Test storage cleanup."""

    async def test_close_clears_client(self) -> None:
        """
        Test that close() clears the client.

        Verifies:
        - Client is set to None after close
        """
        from litestar_storages.backends.azure import AzureConfig, AzureStorage

        storage = AzureStorage(
            config=AzureConfig(
                container="test-container",
                connection_string="DefaultEndpointsProtocol=http;AccountName=test;AccountKey=key;",
            )
        )

        # Just verify close() doesn't raise
        await storage.close()
        assert storage._container_client is None
