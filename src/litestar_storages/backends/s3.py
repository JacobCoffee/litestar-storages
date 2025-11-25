"""Amazon S3 and S3-compatible storage backend."""

from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from litestar_storages.base import BaseStorage
from litestar_storages.exceptions import (
    ConfigurationError,
    StorageConnectionError,
    StorageFileNotFoundError,
)
from litestar_storages.types import MultipartUpload, ProgressCallback, ProgressInfo, StoredFile

__all__ = ("S3Config", "S3Storage")


@dataclass
class S3Config:
    """Configuration for S3-compatible storage.

    Supports AWS S3 and S3-compatible services like:
    - Cloudflare R2
    - DigitalOcean Spaces
    - MinIO
    - Backblaze B2

    Attributes:
        bucket: S3 bucket name
        region: AWS region (e.g., "us-east-1")
        endpoint_url: Custom endpoint for S3-compatible services
        access_key_id: AWS access key ID (falls back to environment/IAM)
        secret_access_key: AWS secret access key
        session_token: AWS session token for temporary credentials
        prefix: Key prefix for all operations (e.g., "uploads/")
        presigned_expiry: Default expiration time for presigned URLs
        use_ssl: Use SSL/TLS for connections
        verify_ssl: Verify SSL certificates
        max_pool_connections: Maximum connection pool size
    """

    bucket: str
    region: str | None = None
    endpoint_url: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    session_token: str | None = None
    prefix: str = ""
    presigned_expiry: timedelta = field(default_factory=lambda: timedelta(hours=1))
    use_ssl: bool = True
    verify_ssl: bool = True
    max_pool_connections: int = 10


class S3Storage(BaseStorage):
    """Amazon S3 and S3-compatible storage backend.

    Uses aioboto3 for async S3 operations with support for AWS S3 and
    S3-compatible services.

    Example:
        >>> # AWS S3
        >>> storage = S3Storage(
        ...     config=S3Config(
        ...         bucket="my-bucket",
        ...         region="us-east-1",
        ...     )
        ... )

        >>> # Cloudflare R2
        >>> storage = S3Storage(
        ...     config=S3Config(
        ...         bucket="my-bucket",
        ...         endpoint_url="https://account.r2.cloudflarestorage.com",
        ...         access_key_id="...",
        ...         secret_access_key="...",
        ...     )
        ... )

    Note:
        The client is lazily initialized on first use. Credentials can come from:
        1. Explicit configuration (access_key_id, secret_access_key)
        2. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
        3. IAM roles (when running on EC2/ECS/Lambda)
    """

    def __init__(self, config: S3Config) -> None:
        """Initialize S3Storage.

        Args:
            config: Configuration for the S3 backend

        Raises:
            ConfigurationError: If required configuration is missing
        """
        self.config = config
        self._client = None
        self._session = None

        if not config.bucket:
            raise ConfigurationError("S3 bucket name is required")

    def _get_key(self, key: str) -> str:
        """Apply prefix to a key.

        Args:
            key: The raw key

        Returns:
            Key with prefix applied
        """
        if self.config.prefix:
            # Ensure prefix ends with / and key doesn't start with /
            prefix = self.config.prefix.rstrip("/") + "/"
            key = key.lstrip("/")
            return f"{prefix}{key}"
        return key

    def _strip_prefix(self, key: str) -> str:
        """Remove prefix from a key.

        Args:
            key: The key with prefix

        Returns:
            Key without prefix
        """
        if self.config.prefix and key.startswith(self.config.prefix):
            return key[len(self.config.prefix) :].lstrip("/")
        return key

    async def _get_client(self) -> Any:
        """Get or create S3 client.

        Returns:
            aioboto3 S3 client

        Raises:
            ConfigurationError: If aioboto3 is not installed
            StorageConnectionError: If unable to create client
        """
        try:
            import aioboto3
        except ImportError as e:
            raise ConfigurationError("aioboto3 is required for S3Storage. Install it with: pip install aioboto3") from e

        try:
            from botocore.config import Config

            # Create session if not already created
            if self._session is None:
                self._session = aioboto3.Session(
                    aws_access_key_id=self.config.access_key_id,
                    aws_secret_access_key=self.config.secret_access_key,
                    aws_session_token=self.config.session_token,
                    region_name=self.config.region,
                )

            # Configure client options
            config = Config(
                max_pool_connections=self.config.max_pool_connections,
            )

            # Create a new client context manager each time
            # Note: aioboto3 clients are async context managers that can only be used once
            return self._session.client(
                "s3",
                endpoint_url=self.config.endpoint_url,
                use_ssl=self.config.use_ssl,
                verify=self.config.verify_ssl,
                config=config,
            )

        except Exception as e:
            raise StorageConnectionError(f"Failed to create S3 client: {e}") from e

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
            StorageError: If the upload fails
        """
        client = await self._get_client()
        s3_key = self._get_key(key)

        # Collect data if it's an async iterator
        if isinstance(data, bytes):
            file_data = data
        else:
            chunks = []
            async for chunk in data:
                chunks.append(chunk)
            file_data = b"".join(chunks)

        # Prepare upload parameters
        upload_params: dict[str, Any] = {
            "Bucket": self.config.bucket,
            "Key": s3_key,
            "Body": file_data,
        }

        if content_type:
            upload_params["ContentType"] = content_type

        if metadata:
            upload_params["Metadata"] = metadata

        try:
            async with client as s3:
                response = await s3.put_object(**upload_params)

                return StoredFile(
                    key=key,
                    size=len(file_data),
                    content_type=content_type,
                    etag=response.get("ETag", "").strip('"'),
                    last_modified=datetime.now(tz=timezone.utc),
                    metadata=metadata or {},
                )

        except Exception as e:
            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to upload file {key}: {e}") from e

    async def get(self, key: str) -> AsyncIterator[bytes]:
        """Retrieve file contents as an async byte stream.

        Args:
            key: Storage path/key for the file

        Yields:
            Chunks of file data as bytes

        Raises:
            StorageFileNotFoundError: If the file does not exist
            StorageError: If the retrieval fails
        """
        client = await self._get_client()
        s3_key = self._get_key(key)

        try:
            async with client as s3:
                response = await s3.get_object(
                    Bucket=self.config.bucket,
                    Key=s3_key,
                )

                # Stream the body
                async for chunk in response["Body"]:
                    yield chunk

        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code")
            if error_code == "NoSuchKey":
                raise StorageFileNotFoundError(key) from e

            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to retrieve file {key}: {e}") from e

    async def get_bytes(self, key: str) -> bytes:
        """Retrieve entire file contents as bytes.

        Args:
            key: Storage path/key for the file

        Returns:
            Complete file contents as bytes

        Raises:
            StorageFileNotFoundError: If the file does not exist
            StorageError: If the retrieval fails
        """
        client = await self._get_client()
        s3_key = self._get_key(key)

        try:
            async with client as s3:
                response = await s3.get_object(
                    Bucket=self.config.bucket,
                    Key=s3_key,
                )

                # Read the entire body
                return await response["Body"].read()

        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code")
            if error_code == "NoSuchKey":
                raise StorageFileNotFoundError(key) from e

            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to retrieve file {key}: {e}") from e

    async def delete(self, key: str) -> None:
        """Delete a file.

        Args:
            key: Storage path/key for the file

        Note:
            S3 delete is idempotent - deleting a non-existent key succeeds silently.
        """
        client = await self._get_client()
        s3_key = self._get_key(key)

        try:
            async with client as s3:
                await s3.delete_object(
                    Bucket=self.config.bucket,
                    Key=s3_key,
                )

        except Exception as e:
            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to delete file {key}: {e}") from e

    async def exists(self, key: str) -> bool:
        """Check if a file exists.

        Args:
            key: Storage path/key for the file

        Returns:
            True if the file exists, False otherwise
        """
        client = await self._get_client()
        s3_key = self._get_key(key)

        try:
            async with client as s3:
                await s3.head_object(
                    Bucket=self.config.bucket,
                    Key=s3_key,
                )
                return True

        except Exception:
            return False

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
        client = await self._get_client()
        s3_prefix = self._get_key(prefix)

        try:
            async with client as s3:
                paginator = s3.get_paginator("list_objects_v2")
                page_iterator = paginator.paginate(
                    Bucket=self.config.bucket,
                    Prefix=s3_prefix,
                )

                count = 0
                async for page in page_iterator:
                    if "Contents" not in page:
                        break

                    for obj in page["Contents"]:
                        s3_key = obj["Key"]
                        key = self._strip_prefix(s3_key)

                        yield StoredFile(
                            key=key,
                            size=obj["Size"],
                            content_type=None,
                            etag=obj.get("ETag", "").strip('"'),
                            last_modified=obj.get("LastModified"),
                            metadata={},
                        )

                        count += 1
                        if limit is not None and count >= limit:
                            return

        except Exception as e:
            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to list files: {e}") from e

    async def url(
        self,
        key: str,
        *,
        expires_in: timedelta | None = None,
    ) -> str:
        """Generate a presigned URL for accessing the file.

        Args:
            key: Storage path/key for the file
            expires_in: Optional expiration time (defaults to config.presigned_expiry)

        Returns:
            Presigned URL string

        Note:
            Presigned URLs allow temporary access to private S3 objects without
            requiring AWS credentials.
        """
        client = await self._get_client()
        s3_key = self._get_key(key)

        expiry = expires_in or self.config.presigned_expiry
        expires_seconds = int(expiry.total_seconds())

        try:
            async with client as s3:
                return await s3.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": self.config.bucket,
                        "Key": s3_key,
                    },
                    ExpiresIn=expires_seconds,
                )

        except Exception as e:
            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to generate URL for {key}: {e}") from e

    async def copy(
        self,
        source: str,
        destination: str,
    ) -> StoredFile:
        """Copy a file within the storage backend.

        Uses S3's native copy operation for efficiency.

        Args:
            source: Source key to copy from
            destination: Destination key to copy to

        Returns:
            StoredFile metadata for the new copy

        Raises:
            FileNotFoundError: If the source file does not exist
            StorageError: If the copy fails
        """
        client = await self._get_client()
        source_key = self._get_key(source)
        dest_key = self._get_key(destination)

        try:
            async with client as s3:
                # Use S3's native copy
                copy_source = {
                    "Bucket": self.config.bucket,
                    "Key": source_key,
                }

                await s3.copy_object(
                    CopySource=copy_source,
                    Bucket=self.config.bucket,
                    Key=dest_key,
                )

                # Get metadata for the new copy
                return await self.info(destination)

        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code")
            if error_code == "NoSuchKey":
                raise StorageFileNotFoundError(source) from e

            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to copy {source} to {destination}: {e}") from e

    async def move(
        self,
        source: str,
        destination: str,
    ) -> StoredFile:
        """Move/rename a file within the storage backend.

        Uses S3's copy + delete operations.

        Args:
            source: Source key to move from
            destination: Destination key to move to

        Returns:
            StoredFile metadata for the moved file

        Raises:
            FileNotFoundError: If the source file does not exist
            StorageError: If the move fails
        """
        # Copy then delete
        result = await self.copy(source, destination)
        await self.delete(source)
        return result

    async def info(self, key: str) -> StoredFile:
        """Get metadata about a file without downloading it.

        Args:
            key: Storage path/key for the file

        Returns:
            StoredFile with metadata

        Raises:
            StorageFileNotFoundError: If the file does not exist
            StorageError: If retrieving metadata fails
        """
        client = await self._get_client()
        s3_key = self._get_key(key)

        try:
            async with client as s3:
                response = await s3.head_object(
                    Bucket=self.config.bucket,
                    Key=s3_key,
                )

                return StoredFile(
                    key=key,
                    size=response["ContentLength"],
                    content_type=response.get("ContentType"),
                    etag=response.get("ETag", "").strip('"'),
                    last_modified=response.get("LastModified"),
                    metadata=response.get("Metadata", {}),
                )

        except Exception as e:
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code")
            if error_code in ("NoSuchKey", "404"):
                raise StorageFileNotFoundError(key) from e

            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to get info for {key}: {e}") from e

    async def close(self) -> None:
        """Close the S3 storage and release resources.

        This method clears the cached session. Note that aioboto3 sessions
        don't require explicit cleanup, but clearing the reference allows
        for garbage collection and prevents accidental reuse after close.
        """
        self._session = None

    # =========================================================================
    # Multipart Upload Support
    # =========================================================================

    async def start_multipart_upload(
        self,
        key: str,
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
        part_size: int = 5 * 1024 * 1024,
    ) -> MultipartUpload:
        """Start a multipart upload.

        Use this for large files (typically > 100MB) to enable:
        - Parallel part uploads
        - Resumable uploads
        - Better handling of network failures

        Args:
            key: Storage path/key for the file
            content_type: MIME type of the content
            metadata: Additional metadata to store with the file
            part_size: Size of each part in bytes (minimum 5MB for S3)

        Returns:
            MultipartUpload object to track the upload state

        Raises:
            StorageError: If initiating the upload fails
        """
        client = await self._get_client()
        s3_key = self._get_key(key)

        # Ensure minimum part size
        part_size = max(part_size, 5 * 1024 * 1024)

        params: dict[str, Any] = {
            "Bucket": self.config.bucket,
            "Key": s3_key,
        }

        if content_type:
            params["ContentType"] = content_type
        if metadata:
            params["Metadata"] = metadata

        try:
            async with client as s3:
                response = await s3.create_multipart_upload(**params)
                return MultipartUpload(
                    upload_id=response["UploadId"],
                    key=key,
                    part_size=part_size,
                )

        except Exception as e:
            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to start multipart upload for {key}: {e}") from e

    async def upload_part(
        self,
        upload: MultipartUpload,
        part_number: int,
        data: bytes,
    ) -> str:
        """Upload a single part of a multipart upload.

        Args:
            upload: The MultipartUpload object from start_multipart_upload
            part_number: Part number (1-indexed, must be sequential)
            data: The part data to upload

        Returns:
            ETag of the uploaded part

        Raises:
            StorageError: If the part upload fails
        """
        client = await self._get_client()
        s3_key = self._get_key(upload.key)

        try:
            async with client as s3:
                response = await s3.upload_part(
                    Bucket=self.config.bucket,
                    Key=s3_key,
                    UploadId=upload.upload_id,
                    PartNumber=part_number,
                    Body=data,
                )

                etag = response["ETag"].strip('"')
                upload.add_part(part_number, etag)
                return etag

        except Exception as e:
            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to upload part {part_number} for {upload.key}: {e}") from e

    async def complete_multipart_upload(
        self,
        upload: MultipartUpload,
    ) -> StoredFile:
        """Complete a multipart upload.

        Args:
            upload: The MultipartUpload object with all parts uploaded

        Returns:
            StoredFile metadata for the completed upload

        Raises:
            StorageError: If completing the upload fails
        """
        client = await self._get_client()
        s3_key = self._get_key(upload.key)

        # Sort parts by part number and format for S3
        sorted_parts = sorted(upload.parts, key=lambda p: p[0])
        parts = [{"PartNumber": num, "ETag": etag} for num, etag in sorted_parts]

        try:
            async with client as s3:
                await s3.complete_multipart_upload(
                    Bucket=self.config.bucket,
                    Key=s3_key,
                    UploadId=upload.upload_id,
                    MultipartUpload={"Parts": parts},
                )

                # Get the final file info
                return await self.info(upload.key)

        except Exception as e:
            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to complete multipart upload for {upload.key}: {e}") from e

    async def abort_multipart_upload(
        self,
        upload: MultipartUpload,
    ) -> None:
        """Abort a multipart upload.

        This cancels an in-progress multipart upload and deletes any
        uploaded parts. Use this to clean up failed uploads.

        Args:
            upload: The MultipartUpload object to abort

        Raises:
            StorageError: If aborting the upload fails
        """
        client = await self._get_client()
        s3_key = self._get_key(upload.key)

        try:
            async with client as s3:
                await s3.abort_multipart_upload(
                    Bucket=self.config.bucket,
                    Key=s3_key,
                    UploadId=upload.upload_id,
                )

        except Exception as e:
            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to abort multipart upload for {upload.key}: {e}") from e

    async def put_large(
        self,
        key: str,
        data: bytes | AsyncIterator[bytes],
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
        part_size: int = 10 * 1024 * 1024,
        progress_callback: ProgressCallback | None = None,
    ) -> StoredFile:
        """Upload a large file using multipart upload.

        This is a convenience method that handles the multipart upload process
        automatically. It splits the data into parts, uploads them, and
        completes the upload.

        Args:
            key: Storage path/key for the file
            data: File contents as bytes or async byte stream
            content_type: MIME type of the content
            metadata: Additional metadata to store with the file
            part_size: Size of each part in bytes (default 10MB)
            progress_callback: Optional callback for progress updates

        Returns:
            StoredFile with metadata about the stored file

        Raises:
            StorageError: If the upload fails
        """
        # Collect data if it's an async iterator
        if isinstance(data, bytes):
            file_data = data
        else:
            chunks = []
            async for chunk in data:
                chunks.append(chunk)
            file_data = b"".join(chunks)

        total_size = len(file_data)

        # For small files, use regular put
        if total_size < part_size:
            return await self.put(key, file_data, content_type=content_type, metadata=metadata)

        # Start multipart upload
        upload = await self.start_multipart_upload(
            key,
            content_type=content_type,
            metadata=metadata,
            part_size=part_size,
        )

        try:
            bytes_uploaded = 0
            part_number = 1

            # Upload parts
            for i in range(0, total_size, part_size):
                part_data = file_data[i : i + part_size]
                await self.upload_part(upload, part_number, part_data)

                bytes_uploaded += len(part_data)
                part_number += 1

                # Report progress
                if progress_callback:
                    progress_callback(
                        ProgressInfo(
                            bytes_transferred=bytes_uploaded,
                            total_bytes=total_size,
                            operation="upload",
                            key=key,
                        )
                    )

            # Complete the upload
            return await self.complete_multipart_upload(upload)

        except Exception:
            # Clean up on failure
            await self.abort_multipart_upload(upload)
            raise
