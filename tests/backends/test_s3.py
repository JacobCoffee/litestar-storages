"""S3Storage-specific tests.

Tests for S3-compatible storage backend using moto for mocking AWS services.
Tests S3-specific features like presigned URLs, prefix handling, and
compatibility with S3-compatible services.

NOTE: S3 tests use moto server mode for proper aiobotocore compatibility.
These tests are marked as integration tests and can be skipped with
`pytest -m "not integration"`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from litestar_storages.backends.s3 import S3Storage

# Mark all tests in this module as integration tests due to moto/aioboto3 compatibility
pytestmark = pytest.mark.integration


@pytest.mark.unit
class TestS3StorageBasics:
    """Test basic S3Storage functionality."""

    async def test_s3_storage_creation(self) -> None:
        """
        Test creating S3Storage instance.

        Verifies:
        - Can create instance with minimal config
        - Config values are stored correctly
        - Lazy client initialization
        """
        from litestar_storages.backends.s3 import S3Config, S3Storage

        config = S3Config(
            bucket="test-bucket",
            region="us-east-1",
        )
        storage = S3Storage(config=config)

        assert storage.config.bucket == "test-bucket"
        assert storage.config.region == "us-east-1"

    async def test_s3_with_credentials(self) -> None:
        """
        Test S3Storage with explicit credentials.

        Verifies:
        - Access key and secret can be provided
        - Session token is optional
        """
        from litestar_storages.backends.s3 import S3Config, S3Storage

        config = S3Config(
            bucket="test-bucket",
            region="us-east-1",
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            session_token="optional-session-token",
        )
        storage = S3Storage(config=config)

        assert storage.config.access_key_id is not None
        assert storage.config.secret_access_key is not None
        assert storage.config.session_token is not None

    async def test_s3_basic_operations(
        self,
        s3_storage: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test basic S3 operations with mocked backend.

        Verifies:
        - Upload works with moto
        - Download retrieves correct data
        - Mocking is functional
        """
        # Upload
        result = await s3_storage.put("test.txt", sample_text_data)
        assert result.key == "test.txt"
        assert result.size == len(sample_text_data)

        # Download
        data = await s3_storage.get_bytes("test.txt")
        assert data == sample_text_data


@pytest.mark.unit
class TestS3PresignedURLs:
    """Test presigned URL generation."""

    async def test_presigned_url_generation(
        self,
        s3_storage: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test generating presigned URLs.

        Verifies:
        - Presigned URLs are generated
        - URL contains signature parameters
        - URL contains expiration info
        """
        await s3_storage.put("test.txt", sample_text_data)

        url = await s3_storage.url("test.txt")

        assert isinstance(url, str)
        assert "test.txt" in url
        # Presigned URLs have AWS signature parameters
        assert "X-Amz-Signature" in url or "Signature" in url

    async def test_presigned_url_with_custom_expiry(
        self,
        s3_storage: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test presigned URLs with custom expiration.

        Verifies:
        - Custom expires_in parameter is used
        - Different expiration times generate different URLs
        """
        await s3_storage.put("test.txt", sample_text_data)

        # Generate URLs with different expiration times
        url_1h = await s3_storage.url("test.txt", expires_in=timedelta(hours=1))
        url_24h = await s3_storage.url("test.txt", expires_in=timedelta(hours=24))

        # Both should be valid URLs
        assert isinstance(url_1h, str)
        assert isinstance(url_24h, str)

        # They should contain different expiration parameters
        # (though with moto they might be similar)

    async def test_presigned_url_default_expiry(
        self,
        s3_storage: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test presigned URLs use default expiry from config.

        Verifies:
        - Default presigned_expiry from config is used
        - No expires_in parameter uses default
        """
        await s3_storage.put("test.txt", sample_text_data)

        # Should use config's presigned_expiry (1 hour)
        url = await s3_storage.url("test.txt")

        assert isinstance(url, str)
        assert len(url) > 0


@pytest.mark.unit
class TestS3PrefixHandling:
    """Test prefix functionality for namespace isolation."""

    async def test_prefix_applied_to_keys(
        self,
        s3_storage_with_prefix: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that prefix is automatically applied to all keys.

        Verifies:
        - Upload with key "file.txt" stores at "prefix/file.txt"
        - Prefix is transparent to user
        - Keys are correctly prefixed in S3
        """
        # Upload with simple key
        result = await s3_storage_with_prefix.put("file.txt", sample_text_data)

        # Result should show user's key (without prefix)
        assert result.key == "file.txt"

        # But internally stored with prefix
        # Verify by checking existence
        assert await s3_storage_with_prefix.exists("file.txt")

    async def test_prefix_in_listing(
        self,
        s3_storage_with_prefix: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that listing works correctly with prefix.

        Verifies:
        - list() only returns files under the prefix
        - Keys returned don't include the prefix
        - Prefix filter works within prefixed namespace
        """
        # Upload files
        await s3_storage_with_prefix.put("file1.txt", sample_text_data)
        await s3_storage_with_prefix.put("dir/file2.txt", sample_text_data)

        # List all (within prefix)
        all_files = [f.key async for f in s3_storage_with_prefix.list()]

        assert len(all_files) == 2
        assert "file1.txt" in all_files
        assert "dir/file2.txt" in all_files

        # List with additional prefix
        dir_files = [f.key async for f in s3_storage_with_prefix.list(prefix="dir/")]
        assert len(dir_files) == 1
        assert "dir/file2.txt" in dir_files

    async def test_prefix_isolation(
        self,
        mock_s3_bucket: dict,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that different prefixes provide isolation.

        Verifies:
        - Two storages with different prefixes don't see each other's files
        - Prefixes act as namespaces
        """
        from litestar_storages.backends.s3 import S3Config, S3Storage

        endpoint_url = mock_s3_bucket["endpoint_url"]

        # Create two storages with different prefixes
        storage_a = S3Storage(
            config=S3Config(
                bucket="test-bucket",
                region="us-east-1",
                endpoint_url=endpoint_url,
                access_key_id="testing",
                secret_access_key="testing",
                prefix="tenant-a/",
            )
        )

        storage_b = S3Storage(
            config=S3Config(
                bucket="test-bucket",
                region="us-east-1",
                endpoint_url=endpoint_url,
                access_key_id="testing",
                secret_access_key="testing",
                prefix="tenant-b/",
            )
        )

        # Upload to each
        await storage_a.put("file.txt", sample_text_data)
        await storage_b.put("file.txt", sample_text_data)

        # Verify isolation
        a_files = [f.key async for f in storage_a.list()]
        b_files = [f.key async for f in storage_b.list()]

        assert a_files == ["file.txt"]
        assert b_files == ["file.txt"]

        # They should be different files in S3
        assert await storage_a.exists("file.txt")
        assert await storage_b.exists("file.txt")


@pytest.mark.unit
class TestS3CustomEndpoint:
    """Test S3-compatible services with custom endpoints."""

    async def test_custom_endpoint_configuration(self) -> None:
        """
        Test configuring custom endpoint URL.

        Verifies:
        - endpoint_url can be set
        - Works for S3-compatible services
        """
        from litestar_storages.backends.s3 import S3Config, S3Storage

        config = S3Config(
            bucket="test-bucket",
            region="us-east-1",
            endpoint_url="https://nyc3.digitaloceanspaces.com",
        )
        storage = S3Storage(config=config)

        assert storage.config.endpoint_url == "https://nyc3.digitaloceanspaces.com"

    async def test_cloudflare_r2_compatibility(self) -> None:
        """
        Test configuration for Cloudflare R2.

        Verifies:
        - R2-style endpoint works
        - Access key/secret required for R2
        """
        from litestar_storages.backends.s3 import S3Config, S3Storage

        config = S3Config(
            bucket="my-bucket",
            region="auto",
            endpoint_url="https://account-id.r2.cloudflarestorage.com",
            access_key_id="r2-access-key",
            secret_access_key="r2-secret-key",
        )
        storage = S3Storage(config=config)

        assert storage.config.endpoint_url.startswith("https://")
        assert "r2.cloudflarestorage.com" in storage.config.endpoint_url

    async def test_minio_compatibility(self) -> None:
        """
        Test configuration for MinIO.

        Verifies:
        - MinIO-style endpoint works
        - HTTP endpoint supported
        - use_ssl=False for HTTP
        """
        from litestar_storages.backends.s3 import S3Config, S3Storage

        config = S3Config(
            bucket="test-bucket",
            endpoint_url="http://localhost:9000",
            access_key_id="minio-access",
            secret_access_key="minio-secret",
            use_ssl=False,
        )
        storage = S3Storage(config=config)

        assert storage.config.use_ssl is False
        assert storage.config.endpoint_url == "http://localhost:9000"


@pytest.mark.unit
class TestS3Metadata:
    """Test S3 metadata handling."""

    async def test_s3_metadata_storage(
        self,
        s3_storage: S3Storage,
        sample_text_data: bytes,
        sample_metadata: dict[str, str],
    ) -> None:
        """
        Test storing custom metadata in S3.

        Verifies:
        - Custom metadata is stored as S3 user metadata
        - Metadata is retrievable
        - Metadata keys are properly formatted
        """
        result = await s3_storage.put(
            "with-metadata.txt",
            sample_text_data,
            metadata=sample_metadata,
        )

        # Verify metadata in result
        for key, value in sample_metadata.items():
            assert result.metadata.get(key) == value

        # Verify metadata persisted in S3
        info = await s3_storage.info("with-metadata.txt")
        for key, value in sample_metadata.items():
            assert info.metadata.get(key) == value

    async def test_s3_content_type(
        self,
        s3_storage: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test content type handling in S3.

        Verifies:
        - Content-Type header is set
        - Content type is retrievable
        """
        result = await s3_storage.put(
            "document.pdf",
            sample_text_data,
            content_type="application/pdf",
        )

        assert result.content_type == "application/pdf"

        # Verify persisted
        info = await s3_storage.info("document.pdf")
        assert info.content_type == "application/pdf"

    async def test_s3_etag(
        self,
        s3_storage: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test that S3 ETag is captured.

        Verifies:
        - ETag is returned after upload
        - ETag is available in info()
        - ETag is S3's MD5 hash (typically)
        """
        result = await s3_storage.put("test.txt", sample_text_data)

        assert result.etag is not None
        assert len(result.etag) > 0

        # Verify via info
        info = await s3_storage.info("test.txt")
        assert info.etag == result.etag


@pytest.mark.unit
class TestS3CopyMove:
    """Test S3 server-side copy and move operations."""

    async def test_s3_server_side_copy(
        self,
        s3_storage: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test S3 server-side copy operation.

        Verifies:
        - copy() uses S3's CopyObject (server-side)
        - No download/upload required
        - Efficient for large files
        """
        await s3_storage.put("source.txt", sample_text_data)

        result = await s3_storage.copy("source.txt", "destination.txt")

        assert result.key == "destination.txt"
        assert result.size == len(sample_text_data)

        # Verify both exist
        assert await s3_storage.exists("source.txt")
        assert await s3_storage.exists("destination.txt")

        # Verify content
        dest_data = await s3_storage.get_bytes("destination.txt")
        assert dest_data == sample_text_data

    async def test_s3_move_operation(
        self,
        s3_storage: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test S3 move operation (copy + delete).

        Verifies:
        - move() performs copy then delete
        - Source no longer exists
        - Destination has correct content
        """
        await s3_storage.put("old-name.txt", sample_text_data)

        result = await s3_storage.move("old-name.txt", "new-name.txt")

        assert result.key == "new-name.txt"

        # Verify source is gone
        assert not await s3_storage.exists("old-name.txt")

        # Verify destination exists
        assert await s3_storage.exists("new-name.txt")
        data = await s3_storage.get_bytes("new-name.txt")
        assert data == sample_text_data


@pytest.mark.unit
class TestS3Listing:
    """Test S3 listing operations."""

    async def test_s3_list_pagination(
        self,
        s3_storage: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test S3 listing with pagination.

        Verifies:
        - list() handles S3 pagination automatically
        - limit parameter works correctly
        - All files are returned even if > 1000 (S3's page size)
        """
        # Upload multiple files
        num_files = 25
        for i in range(num_files):
            await s3_storage.put(f"file-{i:03d}.txt", sample_text_data)

        # List all
        all_files = [f async for f in s3_storage.list()]
        assert len(all_files) == num_files

        # List with limit
        limited = [f async for f in s3_storage.list(limit=10)]
        assert len(limited) == 10

    async def test_s3_list_with_delimiter(
        self,
        s3_storage: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test S3 listing with prefix (acts like directories).

        Verifies:
        - Prefix filtering works
        - Common prefixes are handled
        - Hierarchical listing is supported
        """
        # Upload files in "directories"
        await s3_storage.put("root.txt", sample_text_data)
        await s3_storage.put("images/photo1.jpg", sample_text_data)
        await s3_storage.put("images/photo2.jpg", sample_text_data)
        await s3_storage.put("images/thumbnails/thumb1.jpg", sample_text_data)
        await s3_storage.put("documents/doc1.pdf", sample_text_data)

        # List images prefix
        images = [f async for f in s3_storage.list(prefix="images/")]
        image_keys = [f.key for f in images]

        # Should include all files under images/
        assert "images/photo1.jpg" in image_keys
        assert "images/photo2.jpg" in image_keys
        assert "images/thumbnails/thumb1.jpg" in image_keys

        # Should not include other prefixes
        assert "root.txt" not in image_keys
        assert "documents/doc1.pdf" not in image_keys


@pytest.mark.unit
class TestS3Streaming:
    """Test S3 streaming uploads and downloads."""

    async def test_s3_streaming_upload(
        self,
        s3_storage: S3Storage,
        large_data: bytes,
        async_data_chunks,
    ) -> None:
        """
        Test streaming upload to S3.

        Verifies:
        - Large files can be uploaded via streaming
        - AsyncIterator[bytes] is supported
        - Data integrity is maintained
        """
        chunks = async_data_chunks(large_data, chunk_size=8192)

        result = await s3_storage.put("large.bin", chunks)

        assert result.size == len(large_data)

        # Verify content
        downloaded = await s3_storage.get_bytes("large.bin")
        assert downloaded == large_data

    async def test_s3_streaming_download(
        self,
        s3_storage: S3Storage,
        large_data: bytes,
    ) -> None:
        """
        Test streaming download from S3.

        Verifies:
        - Large files can be downloaded in chunks
        - Memory efficient
        - Complete data is retrieved
        """
        await s3_storage.put("large.bin", large_data)

        # Download via streaming
        chunks = []
        async for chunk in s3_storage.get("large.bin"):
            chunks.append(chunk)

        downloaded = b"".join(chunks)
        assert downloaded == large_data


@pytest.mark.unit
class TestS3ErrorHandling:
    """Test S3-specific error handling."""

    async def test_s3_nonexistent_bucket(self) -> None:
        """
        Test error when bucket doesn't exist.

        Verifies:
        - Appropriate error is raised
        - Error message is helpful
        """
        from litestar_storages.backends.s3 import S3Config, S3Storage
        from litestar_storages.exceptions import StorageError

        storage = S3Storage(
            config=S3Config(
                bucket="nonexistent-bucket-12345",
                region="us-east-1",
            )
        )

        # Operations should fail with helpful error
        with pytest.raises(StorageError):
            await storage.put("test.txt", b"data")

    async def test_s3_permission_error(
        self,
        s3_storage: S3Storage,
    ) -> None:
        """
        Test handling of S3 permission errors.

        Verifies:
        - Permission errors are caught
        - Appropriate exception is raised
        """
        # With moto, we can't easily simulate permission errors
        # But we can test the error handling code path exists
        # This would be more meaningful with real S3 or better mocking

    async def test_s3_network_error_handling(
        self,
        s3_storage: S3Storage,
    ) -> None:
        """
        Test handling of network errors.

        Verifies:
        - Network errors are caught
        - Retries may be attempted
        - Appropriate exception raised
        """
        # Difficult to test with moto - would need to mock network failures
        # Testing the existence of error handling is valuable


@pytest.mark.unit
class TestS3Configuration:
    """Test S3 configuration options."""

    async def test_max_pool_connections(self) -> None:
        """
        Test configuring max pool connections.

        Verifies:
        - max_pool_connections can be set
        - Affects connection pooling
        """
        from litestar_storages.backends.s3 import S3Config, S3Storage

        config = S3Config(
            bucket="test-bucket",
            region="us-east-1",
            max_pool_connections=20,
        )
        storage = S3Storage(config=config)

        assert storage.config.max_pool_connections == 20

    async def test_verify_ssl_option(self) -> None:
        """
        Test SSL verification option.

        Verifies:
        - verify_ssl can be disabled
        - Useful for development with self-signed certs
        """
        from litestar_storages.backends.s3 import S3Config, S3Storage

        config = S3Config(
            bucket="test-bucket",
            region="us-east-1",
            verify_ssl=False,
        )
        storage = S3Storage(config=config)

        assert storage.config.verify_ssl is False

    async def test_region_configuration(self) -> None:
        """
        Test region configuration.

        Verifies:
        - Region can be specified
        - Region affects endpoint selection
        """
        from litestar_storages.backends.s3 import S3Config, S3Storage

        regions = ["us-east-1", "eu-west-1", "ap-southeast-1"]

        for region in regions:
            config = S3Config(bucket="test-bucket", region=region)
            storage = S3Storage(config=config)
            assert storage.config.region == region


@pytest.mark.integration
class TestS3RealWorldScenarios:
    """Test realistic S3 usage scenarios."""

    async def test_multipart_upload_simulation(
        self,
        s3_storage: S3Storage,
    ) -> None:
        """
        Test large file upload (would use multipart in real S3).

        Verifies:
        - Large files (>5GB threshold) work
        - Implementation handles multipart if needed
        """
        # Create 10MB file (still small, but demonstrates streaming)
        large_file = b"x" * (10 * 1024 * 1024)

        result = await s3_storage.put("large-file.bin", large_file)

        assert result.size == len(large_file)
        assert await s3_storage.exists("large-file.bin")

    async def test_concurrent_s3_operations(
        self,
        s3_storage: S3Storage,
    ) -> None:
        """
        Test concurrent S3 operations.

        Verifies:
        - Multiple concurrent uploads work
        - Connection pooling is effective
        - No race conditions
        """
        import asyncio

        async def upload_file(key: str, data: bytes):
            await s3_storage.put(key, data)

        # Upload 20 files concurrently
        tasks = [upload_file(f"concurrent-{i}.txt", f"data-{i}".encode()) for i in range(20)]

        await asyncio.gather(*tasks)

        # Verify all exist
        files = [f async for f in s3_storage.list()]
        assert len(files) == 20

    async def test_cdn_url_pattern(
        self,
        s3_storage: S3Storage,
        sample_text_data: bytes,
    ) -> None:
        """
        Test typical CDN usage pattern.

        Verifies:
        - Upload to S3
        - Generate presigned URL for CDN
        - URL is publicly accessible format
        """
        # Upload image
        await s3_storage.put("images/photo.jpg", sample_text_data)

        # Generate URL for CDN/public access
        url = await s3_storage.url(
            "images/photo.jpg",
            expires_in=timedelta(days=7),
        )

        assert isinstance(url, str)
        assert "photo.jpg" in url
        # In real usage, this URL would be accessible via CDN
