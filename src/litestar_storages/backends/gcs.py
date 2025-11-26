"""Google Cloud Storage backend."""

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

__all__ = ("GCSConfig", "GCSStorage")


@dataclass
class GCSConfig:
    """Configuration for Google Cloud Storage.

    Supports authentication via:
    - Service account JSON file (service_file)
    - Application Default Credentials (ADC) - automatic when running on GCP
    - Explicit token (for testing/special cases)

    Attributes:
        bucket: GCS bucket name
        project: GCP project ID (required for some operations)
        service_file: Path to service account JSON file
        prefix: Key prefix for all operations (e.g., "uploads/")
        presigned_expiry: Default expiration time for signed URLs
        api_root: Custom API endpoint (for emulators)
    """

    bucket: str
    project: str | None = None
    service_file: str | None = None
    prefix: str = ""
    presigned_expiry: timedelta = field(default_factory=lambda: timedelta(hours=1))
    api_root: str | None = None


class GCSStorage(BaseStorage):
    """Google Cloud Storage backend.

    Uses gcloud-aio-storage for async GCS operations.

    Example:
        >>> # Using Application Default Credentials
        >>> storage = GCSStorage(
        ...     config=GCSConfig(
        ...         bucket="my-bucket",
        ...         project="my-project",
        ...     )
        ... )

        >>> # Using service account
        >>> storage = GCSStorage(
        ...     config=GCSConfig(
        ...         bucket="my-bucket",
        ...         service_file="/path/to/service-account.json",
        ...     )
        ... )

        >>> # Using emulator (fake-gcs-server)
        >>> storage = GCSStorage(
        ...     config=GCSConfig(
        ...         bucket="test-bucket",
        ...         api_root="http://localhost:4443",
        ...     )
        ... )

    Note:
        The client is lazily initialized on first use. When running on GCP
        (GCE, GKE, Cloud Run, etc.), credentials are automatically detected.
    """

    def __init__(self, config: GCSConfig) -> None:
        """Initialize GCSStorage.

        Args:
            config: Configuration for the GCS backend

        Raises:
            ConfigurationError: If required configuration is missing
        """
        self.config = config
        self._client: Any = None
        self._session: Any = None

        if not config.bucket:
            raise ConfigurationError("GCS bucket name is required")

    def _get_key(self, key: str) -> str:
        """Apply prefix to a key.

        Args:
            key: The raw key

        Returns:
            Key with prefix applied
        """
        if self.config.prefix:
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

    async def _get_client(self) -> Any:  # noqa: ANN401
        """Get or create GCS client.

        Returns:
            gcloud.aio.storage.Storage client

        Raises:
            ConfigurationError: If gcloud-aio-storage is not installed
            StorageConnectionError: If unable to create client
        """
        if self._client is not None:
            return self._client

        try:
            from gcloud.aio.storage import Storage
        except ImportError as e:
            raise ConfigurationError(
                "gcloud-aio-storage is required for GCSStorage. Install it with: pip install gcloud-aio-storage"
            ) from e

        try:
            # Build client kwargs
            kwargs: dict[str, Any] = {}

            if self.config.service_file:
                kwargs["service_file"] = self.config.service_file

            if self.config.api_root:
                kwargs["api_root"] = self.config.api_root

            self._client = Storage(**kwargs)
            return self._client

        except Exception as e:
            raise StorageConnectionError(f"Failed to create GCS client: {e}") from e

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
        gcs_key = self._get_key(key)

        # Collect data if it's an async iterator
        if isinstance(data, bytes):
            file_data = data
        else:
            chunks = []
            async for chunk in data:
                chunks.append(chunk)
            file_data = b"".join(chunks)

        # Build metadata dict for GCS
        gcs_metadata: dict[str, Any] | None = None
        if metadata:
            gcs_metadata = {"metadata": metadata}

        try:
            response = await client.upload(
                self.config.bucket,
                gcs_key,
                file_data,
                content_type=content_type,
                metadata=gcs_metadata,
            )

            return StoredFile(
                key=key,
                size=len(file_data),
                content_type=content_type,
                etag=response.get("etag", "").strip('"'),
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
        gcs_key = self._get_key(key)

        try:
            # gcloud-aio-storage download returns bytes directly
            # For streaming, we'd need to use download_stream, but it requires
            # more complex handling. For now, download and yield in chunks.
            data = await client.download(self.config.bucket, gcs_key)

            # Yield in chunks for consistency with streaming interface
            chunk_size = 64 * 1024  # 64KB
            for i in range(0, len(data), chunk_size):
                yield data[i : i + chunk_size]

        except Exception as e:
            error_message = str(e).lower()
            if "not found" in error_message or "404" in error_message:
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
        gcs_key = self._get_key(key)

        try:
            return await client.download(self.config.bucket, gcs_key)

        except Exception as e:
            error_message = str(e).lower()
            if "not found" in error_message or "404" in error_message:
                raise StorageFileNotFoundError(key) from e

            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to retrieve file {key}: {e}") from e

    async def delete(self, key: str) -> None:
        """Delete a file.

        Args:
            key: Storage path/key for the file

        Note:
            GCS delete is idempotent - deleting a non-existent key succeeds silently.
        """
        client = await self._get_client()
        gcs_key = self._get_key(key)

        try:
            await client.delete(self.config.bucket, gcs_key)

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
        gcs_key = self._get_key(key)

        try:
            from gcloud.aio.storage import Bucket

            bucket = Bucket(client, self.config.bucket)
            return await bucket.blob_exists(gcs_key)

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
        gcs_prefix = self._get_key(prefix)

        try:
            # Use list_objects to get full metadata
            params = {"prefix": gcs_prefix}
            response = await client.list_objects(self.config.bucket, params=params)

            items = response.get("items", [])

            for count, item in enumerate(items):
                gcs_key = item["name"]
                key = self._strip_prefix(gcs_key)

                # Parse last modified time
                last_modified = None
                if "updated" in item:
                    try:
                        last_modified = datetime.fromisoformat(item["updated"].replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        last_modified = None

                yield StoredFile(
                    key=key,
                    size=int(item.get("size", 0)),
                    content_type=item.get("contentType"),
                    etag=item.get("etag", "").strip('"'),
                    last_modified=last_modified,
                    metadata=item.get("metadata", {}),
                )

                if limit is not None and count + 1 >= limit:
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
        """Generate a signed URL for accessing the file.

        Args:
            key: Storage path/key for the file
            expires_in: Optional expiration time (defaults to config.presigned_expiry)

        Returns:
            Signed URL string

        Note:
            Signed URLs allow temporary access to private GCS objects without
            requiring GCP credentials. Requires service account credentials.
        """
        client = await self._get_client()
        gcs_key = self._get_key(key)

        expiry = expires_in or self.config.presigned_expiry
        expires_seconds = int(expiry.total_seconds())

        try:
            from gcloud.aio.storage import Bucket

            bucket = Bucket(client, self.config.bucket)
            blob = bucket.new_blob(gcs_key)

            return await blob.get_signed_url(expiration=expires_seconds)

        except Exception as e:
            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to generate URL for {key}: {e}") from e

    async def copy(
        self,
        source: str,
        destination: str,
    ) -> StoredFile:
        """Copy a file within the storage backend.

        Uses GCS's native copy operation for efficiency.

        Args:
            source: Source key to copy from
            destination: Destination key to copy to

        Returns:
            StoredFile metadata for the new copy

        Raises:
            StorageFileNotFoundError: If the source file does not exist
            StorageError: If the copy fails
        """
        client = await self._get_client()
        source_key = self._get_key(source)
        dest_key = self._get_key(destination)

        try:
            # Use GCS's native copy (rewriteTo API)
            await client.copy(
                self.config.bucket,
                source_key,
                self.config.bucket,
                new_name=dest_key,
            )

            # Get metadata for the new copy
            return await self.info(destination)

        except Exception as e:
            error_message = str(e).lower()
            if "not found" in error_message or "404" in error_message:
                raise StorageFileNotFoundError(source) from e

            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to copy {source} to {destination}: {e}") from e

    async def move(
        self,
        source: str,
        destination: str,
    ) -> StoredFile:
        """Move/rename a file within the storage backend.

        Uses GCS's copy + delete operations (no native move).

        Args:
            source: Source key to move from
            destination: Destination key to move to

        Returns:
            StoredFile metadata for the moved file

        Raises:
            StorageFileNotFoundError: If the source file does not exist
            StorageError: If the move fails
        """
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
        gcs_key = self._get_key(key)

        try:
            from gcloud.aio.storage import Bucket

            bucket = Bucket(client, self.config.bucket)
            blob = await bucket.get_blob(gcs_key)

            # Parse metadata from blob (use getattr for type safety)
            metadata_dict: dict[str, Any] = getattr(blob, "metadata", None) or {}

            # Parse last modified time
            last_modified = None
            if metadata_dict.get("updated"):
                try:
                    last_modified = datetime.fromisoformat(metadata_dict["updated"].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    last_modified = None

            return StoredFile(
                key=key,
                size=int(metadata_dict.get("size", 0)),
                content_type=metadata_dict.get("contentType"),
                etag=metadata_dict.get("etag", "").strip('"'),
                last_modified=last_modified,
                metadata=metadata_dict.get("metadata", {}),
            )

        except Exception as e:
            error_message = str(e).lower()
            if "not found" in error_message or "404" in error_message:
                raise StorageFileNotFoundError(key) from e

            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to get info for {key}: {e}") from e

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
        - Chunked uploads with progress tracking
        - Better handling of network failures
        - Memory-efficient streaming uploads

        Note:
            GCS doesn't have native multipart upload like S3. This implementation
            buffers parts in memory and uploads them when complete_multipart_upload
            is called. For true resumable uploads, consider using GCS's resumable
            upload API directly.

        Args:
            key: Storage path/key for the file
            content_type: MIME type of the content
            metadata: Additional metadata to store with the file
            part_size: Size of each part in bytes (default 5MB)

        Returns:
            MultipartUpload object to track the upload state

        Raises:
            StorageError: If initiating the upload fails
        """
        # Generate a unique upload ID (we'll store parts in the upload object)
        import uuid

        upload_id = str(uuid.uuid4())

        # Store metadata for later use in complete_multipart_upload
        upload = MultipartUpload(
            upload_id=upload_id,
            key=key,
            part_size=part_size,
        )

        # Store additional metadata in a hidden attribute for later
        upload._content_type = content_type  # type: ignore[attr-defined]  # noqa: SLF001
        upload._metadata = metadata or {}  # type: ignore[attr-defined]  # noqa: SLF001
        upload._part_data = []  # type: ignore[attr-defined]  # noqa: SLF001 - Buffer for part data

        return upload

    async def upload_part(
        self,
        upload: MultipartUpload,
        part_number: int,
        data: bytes,
    ) -> str:
        """Upload a single part of a multipart upload.

        Note:
            Parts are buffered in memory until complete_multipart_upload is called.

        Args:
            upload: The MultipartUpload object from start_multipart_upload
            part_number: Part number (1-indexed, must be sequential)
            data: The part data to upload

        Returns:
            ETag (placeholder) of the uploaded part

        Raises:
            StorageError: If the part upload fails
        """
        try:
            # Buffer the part data for later upload
            part_data_list: list[tuple[int, bytes]] = getattr(upload, "_part_data", [])
            part_data_list.append((part_number, data))

            # Generate a placeholder ETag (actual ETag will come from final upload)
            import hashlib

            etag = hashlib.md5(data).hexdigest()  # noqa: S324
            upload.add_part(part_number, etag)

            return etag

        except Exception as e:
            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to buffer part {part_number} for {upload.key}: {e}") from e

    async def complete_multipart_upload(
        self,
        upload: MultipartUpload,
    ) -> StoredFile:
        """Complete a multipart upload.

        Combines all buffered parts and uploads the complete file to GCS.

        Args:
            upload: The MultipartUpload object with all parts uploaded

        Returns:
            StoredFile metadata for the completed upload

        Raises:
            StorageError: If completing the upload fails
        """
        try:
            # Retrieve buffered parts
            part_data_list: list[tuple[int, bytes]] = getattr(upload, "_part_data", [])

            # Sort by part number and combine
            sorted_parts = sorted(part_data_list, key=lambda p: p[0])
            complete_data = b"".join(part[1] for part in sorted_parts)

            # Retrieve stored metadata
            content_type: str | None = getattr(upload, "_content_type", None)
            metadata: dict[str, str] = getattr(upload, "_metadata", {})

            # Upload the complete file
            result = await self.put(
                upload.key,
                complete_data,
                content_type=content_type,
                metadata=metadata,
            )

            # Clean up buffered data
            delattr(upload, "_part_data")
            delattr(upload, "_content_type")
            delattr(upload, "_metadata")

            return result

        except Exception as e:
            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to complete multipart upload for {upload.key}: {e}") from e

    async def abort_multipart_upload(
        self,
        upload: MultipartUpload,
    ) -> None:
        """Abort a multipart upload.

        This cancels an in-progress multipart upload and frees buffered data.
        Use this to clean up failed uploads.

        Args:
            upload: The MultipartUpload object to abort

        Raises:
            StorageError: If aborting the upload fails
        """
        try:
            # Clean up buffered data
            if hasattr(upload, "_part_data"):
                delattr(upload, "_part_data")
            if hasattr(upload, "_content_type"):
                delattr(upload, "_content_type")
            if hasattr(upload, "_metadata"):
                delattr(upload, "_metadata")

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

    async def close(self) -> None:
        """Close the GCS storage and release resources.

        This method closes the underlying aiohttp session.
        """
        if self._client is not None:
            await self._client.close()
            self._client = None
