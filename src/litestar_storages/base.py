"""Base storage protocol and abstract implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import timedelta
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from litestar_storages.types import StoredFile

__all__ = ["BaseStorage", "Storage"]


@runtime_checkable
class Storage(Protocol):
    """Async storage protocol.

    All storage backends must implement this protocol to ensure
    consistent behavior across different storage providers.

    This protocol defines the core interface for async file storage operations,
    including uploading, downloading, deleting, and managing file metadata.
    """

    async def put(
        self,
        key: str,
        data: bytes | AsyncGenerator[bytes, None],
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredFile:
        """Store data at the given key.

        Args:
            key: Storage path/key for the file. This should be a forward-slash
                separated path (e.g., "images/photo.jpg").
            data: File contents as bytes or async byte stream. For large files,
                prefer using an async iterator to avoid loading the entire file
                into memory.
            content_type: MIME type of the content (e.g., 'image/jpeg', 'text/plain').
                If not provided, backends may attempt to infer it from the file extension.
            metadata: Additional metadata to store with the file. Keys and values
                must be strings. Backend-specific limits may apply.

        Returns:
            StoredFile containing metadata about the stored file, including
            the actual size, etag, and last modified timestamp.

        Raises:
            StorageError: If the upload fails for any reason
            StoragePermissionError: If lacking permissions to write to this location
            ConfigurationError: If storage backend is misconfigured
        """
        ...

    def get(self, key: str) -> AsyncIterator[bytes]:
        """Retrieve file contents as an async byte stream.

        This method returns an async iterator that yields chunks of the file,
        allowing for efficient streaming of large files without loading the
        entire content into memory.

        Args:
            key: Storage path/key for the file

        Yields:
            Chunks of file data as bytes. Chunk size is backend-dependent.

        Raises:
            StorageFileNotFoundError: If the file does not exist
            StorageError: If the retrieval fails
            StoragePermissionError: If lacking permissions to read this file
        """
        ...

    async def get_bytes(self, key: str) -> bytes:
        """Retrieve entire file contents as bytes.

        This is a convenience method that collects the stream from get()
        into memory. Use get() for large files to avoid memory pressure.

        Args:
            key: Storage path/key for the file

        Returns:
            Complete file contents as bytes

        Raises:
            StorageFileNotFoundError: If the file does not exist
            StorageError: If the retrieval fails
            StoragePermissionError: If lacking permissions to read this file
        """
        ...

    async def delete(self, key: str) -> None:
        """Delete a file.

        Args:
            key: Storage path/key for the file

        Raises:
            StorageFileNotFoundError: If the file does not exist (implementation-dependent;
                some backends may silently succeed for idempotency)
            StorageError: If the deletion fails
            StoragePermissionError: If lacking permissions to delete this file
        """
        ...

    async def exists(self, key: str) -> bool:
        """Check if a file exists.

        Args:
            key: Storage path/key for the file

        Returns:
            True if the file exists, False otherwise

        Raises:
            StorageError: If the check fails (rare; typically returns False)
        """
        ...

    async def list(
        self,
        prefix: str = "",
        *,
        limit: int | None = None,
    ) -> AsyncGenerator[StoredFile, None]:
        """List files with optional prefix filter.

        Args:
            prefix: Filter results to keys starting with this prefix.
                Use empty string to list all files. For hierarchical storage,
                use forward slashes (e.g., "images/2024/").
            limit: Maximum number of results to return. If None, returns all
                matching files. Note: backends may have their own internal limits.

        Yields:
            StoredFile metadata for each matching file, typically in
            lexicographical order by key.

        Raises:
            StorageError: If the listing operation fails
            StoragePermissionError: If lacking permissions to list files
        """
        ...

    async def url(
        self,
        key: str,
        *,
        expires_in: timedelta | None = None,
    ) -> str:
        """Generate a URL for accessing the file.

        For cloud backends, this typically generates a presigned URL that grants
        temporary access to the file. For filesystem backends, this returns a
        path or configured base URL.

        Args:
            key: Storage path/key for the file
            expires_in: Optional expiration time for signed URLs. If None,
                uses backend's default expiration (typically 1 hour). For
                filesystem backends, this parameter may be ignored.

        Returns:
            URL string for accessing the file. This may be:
            - A presigned URL with embedded credentials (cloud backends)
            - A public URL if the file is publicly accessible
            - A file:// URL or relative path (filesystem backend)

        Raises:
            StorageFileNotFoundError: If the file does not exist (implementation-dependent)
            StorageError: If URL generation fails
            StoragePermissionError: If lacking permissions to generate URLs

        Note:
            URLs may become invalid after the expiration time or if the file
            is deleted. Clients should handle 404/403 responses gracefully.
        """
        ...

    async def copy(
        self,
        source: str,
        destination: str,
    ) -> StoredFile:
        """Copy a file within the storage backend.

        This operation should be atomic where possible. Some backends can
        perform server-side copies without downloading and re-uploading data.

        Args:
            source: Source key to copy from
            destination: Destination key to copy to. If this key already exists,
                it will be overwritten.

        Returns:
            StoredFile metadata for the new copy at the destination

        Raises:
            StorageFileNotFoundError: If the source file does not exist
            StorageError: If the copy operation fails
            StoragePermissionError: If lacking permissions for the operation
        """
        ...

    async def move(
        self,
        source: str,
        destination: str,
    ) -> StoredFile:
        """Move/rename a file within the storage backend.

        This operation should be atomic where possible. Default implementation
        performs a copy followed by delete.

        Args:
            source: Source key to move from
            destination: Destination key to move to. If this key already exists,
                it will be overwritten.

        Returns:
            StoredFile metadata for the file at the new destination

        Raises:
            StorageFileNotFoundError: If the source file does not exist
            StorageError: If the move operation fails
            StoragePermissionError: If lacking permissions for the operation
        """
        ...

    async def info(self, key: str) -> StoredFile:
        """Get metadata about a file without downloading it.

        This is useful for checking file size, content type, and other
        metadata without incurring the cost of downloading the file.

        Args:
            key: Storage path/key for the file

        Returns:
            StoredFile with metadata including size, content_type, etag,
            last_modified, and any custom metadata

        Raises:
            StorageFileNotFoundError: If the file does not exist
            StorageError: If the metadata retrieval fails
            StoragePermissionError: If lacking permissions to access file metadata
        """
        ...

    async def close(self) -> None:
        """Close the storage backend and release resources.

        This method should be called when the storage is no longer needed,
        typically during application shutdown. It allows backends to clean up
        resources like HTTP sessions, connection pools, or file handles.

        For backends that don't require cleanup, this method is a no-op.

        Note:
            After calling close(), the storage instance should not be used.
            Some backends may raise errors if operations are attempted after close().
        """
        ...


class BaseStorage(ABC):
    """Abstract base class providing common functionality for storage backends.

    Backends can inherit from this to get default implementations of
    convenience methods while only implementing core abstract operations.

    Subclasses must implement:
    - put()
    - get()
    - delete()
    - exists()
    - list()
    - url()
    - info()

    This class provides default implementations for:
    - get_bytes() - collects stream into memory
    - copy() - downloads and re-uploads
    - move() - copies then deletes
    """

    @abstractmethod
    async def put(
        self,
        key: str,
        data: bytes | AsyncGenerator[bytes, None],
        *,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> StoredFile:
        """Store data at the given key. Must be implemented by subclasses."""

    @abstractmethod
    def get(self, key: str) -> AsyncIterator[bytes]:
        """Retrieve file as async byte stream. Must be implemented by subclasses."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a file. Must be implemented by subclasses."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if file exists. Must be implemented by subclasses."""

    @abstractmethod
    async def list(
        self,
        prefix: str = "",
        *,
        limit: int | None = None,
    ) -> AsyncGenerator[StoredFile, None]:
        """List files with prefix filter. Must be implemented by subclasses."""

    @abstractmethod
    async def url(
        self,
        key: str,
        *,
        expires_in: timedelta | None = None,
    ) -> str:
        """Generate URL for file access. Must be implemented by subclasses."""

    @abstractmethod
    async def info(self, key: str) -> StoredFile:
        """Get file metadata. Must be implemented by subclasses."""

    # Default implementations below

    async def get_bytes(self, key: str) -> bytes:
        """Default implementation: collect stream into bytes.

        This method gathers all chunks from get() and joins them into
        a single bytes object. For large files, prefer using get() directly
        to stream the content.

        Args:
            key: Storage path/key for the file

        Returns:
            Complete file contents as bytes

        Raises:
            StorageFileNotFoundError: If the file does not exist
            StorageError: If the retrieval fails
        """
        chunks = []
        async for chunk in self.get(key):
            chunks.append(chunk)
        return b"".join(chunks)

    async def copy(self, source: str, destination: str) -> StoredFile:
        """Default implementation: download and re-upload.

        This implementation downloads the source file completely into memory,
        then uploads it to the destination. Backends that support server-side
        copy should override this method for better performance.

        Args:
            source: Source key to copy from
            destination: Destination key to copy to

        Returns:
            StoredFile metadata for the new copy

        Raises:
            StorageFileNotFoundError: If source does not exist
            StorageError: If the operation fails
        """
        info = await self.info(source)
        data = await self.get_bytes(source)
        return await self.put(
            destination,
            data,
            content_type=info.content_type,
            metadata=info.metadata,
        )

    async def move(self, source: str, destination: str) -> StoredFile:
        """Default implementation: copy then delete.

        This implementation performs a copy operation followed by deletion
        of the source. Backends that support atomic move/rename should
        override this method.

        Args:
            source: Source key to move from
            destination: Destination key to move to

        Returns:
            StoredFile metadata for the moved file

        Raises:
            StorageFileNotFoundError: If source does not exist
            StorageError: If the operation fails

        Note:
            This operation is not atomic in the default implementation.
            If deletion fails after a successful copy, the source file
            will remain.
        """
        result = await self.copy(source, destination)
        await self.delete(source)
        return result

    async def close(self) -> None:  # noqa: B027
        """Default implementation: no-op.

        Subclasses that manage resources (HTTP sessions, connection pools, etc.)
        should override this method to properly release them.
        """
