"""Azure Blob Storage backend."""

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
from litestar_storages.types import StoredFile

__all__ = ("AzureConfig", "AzureStorage")


@dataclass
class AzureConfig:
    """Configuration for Azure Blob Storage.

    Supports authentication via:
    - Connection string (connection_string)
    - Account URL + credential (account_url + account_key or DefaultAzureCredential)
    - SAS token (account_url with SAS token embedded)

    Attributes:
        container: Azure Blob container name
        account_url: Azure storage account URL (e.g., https://<account>.blob.core.windows.net)
        account_key: Storage account access key (optional if using connection string or DefaultAzureCredential)
        connection_string: Full connection string (alternative to account_url + account_key)
        prefix: Key prefix for all operations (e.g., "uploads/")
        presigned_expiry: Default expiration time for SAS URLs
    """

    container: str
    account_url: str | None = None
    account_key: str | None = None
    connection_string: str | None = None
    prefix: str = ""
    presigned_expiry: timedelta = field(default_factory=lambda: timedelta(hours=1))


class AzureStorage(BaseStorage):
    """Azure Blob Storage backend.

    Uses azure-storage-blob async API for all operations.

    Example:
        >>> # Using connection string
        >>> storage = AzureStorage(
        ...     config=AzureConfig(
        ...         container="my-container",
        ...         connection_string="DefaultEndpointsProtocol=https;...",
        ...     )
        ... )

        >>> # Using account URL and key
        >>> storage = AzureStorage(
        ...     config=AzureConfig(
        ...         container="my-container",
        ...         account_url="https://myaccount.blob.core.windows.net",
        ...         account_key="my-access-key",
        ...     )
        ... )

        >>> # Using Azurite emulator
        >>> storage = AzureStorage(
        ...     config=AzureConfig(
        ...         container="test-container",
        ...         connection_string="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=...;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1",
        ...     )
        ... )

    Note:
        The client is lazily initialized on first use. When running on Azure
        (App Service, Functions, AKS, etc.), credentials can be automatically
        detected using DefaultAzureCredential.
    """

    def __init__(self, config: AzureConfig) -> None:
        """Initialize AzureStorage.

        Args:
            config: Configuration for the Azure Blob backend

        Raises:
            ConfigurationError: If required configuration is missing
        """
        self.config = config
        self._container_client: Any = None

        if not config.container:
            raise ConfigurationError("Azure container name is required")

        if not config.connection_string and not config.account_url:
            raise ConfigurationError("Either connection_string or account_url is required")

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

    async def _get_container_client(self) -> Any:  # noqa: ANN401
        """Get or create Azure Container client.

        Returns:
            azure.storage.blob.aio.ContainerClient

        Raises:
            ConfigurationError: If azure-storage-blob is not installed
            StorageConnectionError: If unable to create client
        """
        if self._container_client is not None:
            return self._container_client

        try:
            from azure.storage.blob.aio import BlobServiceClient, ContainerClient
        except ImportError as e:
            raise ConfigurationError(
                "azure-storage-blob is required for AzureStorage. Install it with: pip install azure-storage-blob"
            ) from e

        try:
            if self.config.connection_string:
                # Create from connection string
                self._container_client = ContainerClient.from_connection_string(
                    conn_str=self.config.connection_string,
                    container_name=self.config.container,
                )
            elif self.config.account_url:
                # Create from account URL
                if self.config.account_key:
                    # Use account key credential
                    blob_service_client = BlobServiceClient(
                        account_url=self.config.account_url,
                        credential=self.config.account_key,
                    )
                else:
                    # Use DefaultAzureCredential (for managed identity, etc.)
                    try:
                        from azure.identity.aio import DefaultAzureCredential

                        credential = DefaultAzureCredential()
                        blob_service_client = BlobServiceClient(
                            account_url=self.config.account_url,
                            credential=credential,
                        )
                    except ImportError as e:
                        raise ConfigurationError(
                            "azure-identity is required when using account_url without account_key. "
                            "Install it with: pip install azure-identity"
                        ) from e

                self._container_client = blob_service_client.get_container_client(self.config.container)

            return self._container_client

        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise StorageConnectionError(f"Failed to create Azure client: {e}") from e

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
        container_client = await self._get_container_client()
        azure_key = self._get_key(key)

        # Collect data if it's an async iterator
        if isinstance(data, bytes):
            file_data = data
        else:
            chunks = []
            async for chunk in data:
                chunks.append(chunk)
            file_data = b"".join(chunks)

        try:
            from azure.storage.blob import ContentSettings

            blob_client = container_client.get_blob_client(azure_key)

            # Build content settings
            content_settings = None
            if content_type:
                content_settings = ContentSettings(content_type=content_type)

            await blob_client.upload_blob(
                file_data,
                overwrite=True,
                content_settings=content_settings,
                metadata=metadata,
            )

            return StoredFile(
                key=key,
                size=len(file_data),
                content_type=content_type,
                etag="",  # Azure returns ETag but needs additional call
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
        container_client = await self._get_container_client()
        azure_key = self._get_key(key)

        try:
            blob_client = container_client.get_blob_client(azure_key)
            download_stream = await blob_client.download_blob()

            # Stream the data in chunks
            async for chunk in download_stream.chunks():
                yield chunk

        except Exception as e:
            error_message = str(e).lower()
            if "blobnotfound" in error_message or "not found" in error_message or "404" in error_message:
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
        container_client = await self._get_container_client()
        azure_key = self._get_key(key)

        try:
            blob_client = container_client.get_blob_client(azure_key)
            download_stream = await blob_client.download_blob()
            return await download_stream.readall()

        except Exception as e:
            error_message = str(e).lower()
            if "blobnotfound" in error_message or "not found" in error_message or "404" in error_message:
                raise StorageFileNotFoundError(key) from e

            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to retrieve file {key}: {e}") from e

    async def delete(self, key: str) -> None:
        """Delete a file.

        Args:
            key: Storage path/key for the file

        Note:
            Deleting a non-existent key will raise an error (unlike S3/GCS).
            Use exists() first if you need idempotent deletes.
        """
        container_client = await self._get_container_client()
        azure_key = self._get_key(key)

        try:
            blob_client = container_client.get_blob_client(azure_key)
            await blob_client.delete_blob()

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
        container_client = await self._get_container_client()
        azure_key = self._get_key(key)

        try:
            blob_client = container_client.get_blob_client(azure_key)
            return await blob_client.exists()

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
        container_client = await self._get_container_client()
        azure_prefix = self._get_key(prefix)

        try:
            count = 0
            async for blob in container_client.list_blobs(name_starts_with=azure_prefix):
                blob_key = self._strip_prefix(blob.name)

                yield StoredFile(
                    key=blob_key,
                    size=blob.size or 0,
                    content_type=blob.content_settings.content_type if blob.content_settings else None,
                    etag=blob.etag.strip('"') if blob.etag else "",
                    last_modified=blob.last_modified,
                    metadata=blob.metadata or {},
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
        """Generate a SAS URL for accessing the file.

        Args:
            key: Storage path/key for the file
            expires_in: Optional expiration time (defaults to config.presigned_expiry)

        Returns:
            SAS URL string

        Note:
            SAS URLs allow temporary access to private Azure blobs without
            requiring Azure credentials. Requires account key for signing.
        """
        container_client = await self._get_container_client()
        azure_key = self._get_key(key)

        expiry = expires_in or self.config.presigned_expiry

        # Get account name and key before try block to avoid TRY301
        if self.config.connection_string:
            # Parse from connection string
            parts = dict(item.split("=", 1) for item in self.config.connection_string.split(";") if "=" in item)
            account_name = parts.get("AccountName", "")
            account_key = parts.get("AccountKey", "")
        else:
            # Extract from account URL
            if self.config.account_url:
                url = self.config.account_url.replace("https://", "").replace("http://", "")
                account_name = url.split(".")[0]
            else:
                account_name = ""
            account_key = self.config.account_key or ""

        if not account_key:
            msg = "Account key is required to generate SAS URLs"
            raise ConfigurationError(msg)

        try:
            from azure.storage.blob import BlobSasPermissions, generate_blob_sas

            blob_client = container_client.get_blob_client(azure_key)

            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=self.config.container,
                blob_name=azure_key,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(tz=timezone.utc) + expiry,
            )

            return f"{blob_client.url}?{sas_token}"

        except Exception as e:
            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to generate URL for {key}: {e}") from e

    async def copy(
        self,
        source: str,
        destination: str,
    ) -> StoredFile:
        """Copy a file within the storage backend.

        Uses Azure's native copy operation for efficiency.

        Args:
            source: Source key to copy from
            destination: Destination key to copy to

        Returns:
            StoredFile metadata for the new copy

        Raises:
            StorageFileNotFoundError: If the source file does not exist
            StorageError: If the copy fails
        """
        container_client = await self._get_container_client()
        source_key = self._get_key(source)
        dest_key = self._get_key(destination)

        try:
            source_blob = container_client.get_blob_client(source_key)
            dest_blob = container_client.get_blob_client(dest_key)

            # Start copy from URL
            await dest_blob.start_copy_from_url(source_blob.url)

            # Get metadata for the new copy
            return await self.info(destination)

        except Exception as e:
            error_message = str(e).lower()
            if "blobnotfound" in error_message or "not found" in error_message or "404" in error_message:
                raise StorageFileNotFoundError(source) from e

            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to copy {source} to {destination}: {e}") from e

    async def move(
        self,
        source: str,
        destination: str,
    ) -> StoredFile:
        """Move/rename a file within the storage backend.

        Uses Azure's copy + delete operations (no native move).

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
        container_client = await self._get_container_client()
        azure_key = self._get_key(key)

        try:
            blob_client = container_client.get_blob_client(azure_key)
            properties = await blob_client.get_blob_properties()

            return StoredFile(
                key=key,
                size=properties.size or 0,
                content_type=properties.content_settings.content_type if properties.content_settings else None,
                etag=properties.etag.strip('"') if properties.etag else "",
                last_modified=properties.last_modified,
                metadata=properties.metadata or {},
            )

        except Exception as e:
            error_message = str(e).lower()
            if "blobnotfound" in error_message or "not found" in error_message or "404" in error_message:
                raise StorageFileNotFoundError(key) from e

            from litestar_storages.exceptions import StorageError

            raise StorageError(f"Failed to get info for {key}: {e}") from e

    async def close(self) -> None:
        """Close the Azure storage and release resources.

        This method closes the underlying aiohttp session.
        """
        if self._container_client is not None:
            await self._container_client.close()
            self._container_client = None
