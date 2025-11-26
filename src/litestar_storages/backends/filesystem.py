"""Local filesystem storage backend."""

from __future__ import annotations

import mimetypes
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from litestar_storages.base import BaseStorage
from litestar_storages.exceptions import StorageFileNotFoundError, StoragePermissionError
from litestar_storages.types import StoredFile


def _guess_content_type(key: str) -> str | None:
    """Guess content type from file extension."""
    content_type, _ = mimetypes.guess_type(key)
    return content_type


__all__ = ("FileSystemConfig", "FileSystemStorage")


@dataclass
class FileSystemConfig:
    """Configuration for filesystem storage.

    Attributes:
        path: Base directory for file storage
        base_url: Optional base URL for generating file URLs (e.g., "https://cdn.example.com/uploads")
        create_dirs: Automatically create directories as needed
        permissions: File permissions (octal, default 0o644)
    """

    path: Path
    base_url: str | None = None
    create_dirs: bool = True
    permissions: int = 0o644


class FileSystemStorage(BaseStorage):
    """Local filesystem storage backend.

    Uses aiofiles for async file I/O operations. Stores files in a local directory
    with support for URL generation via base_url configuration.

    Example:
        >>> storage = FileSystemStorage(
        ...     config=FileSystemConfig(
        ...         path=Path("/var/uploads"),
        ...         base_url="https://cdn.example.com/uploads",
        ...     )
        ... )
        >>> await storage.put("images/photo.jpg", image_data)
        >>> url = await storage.url("images/photo.jpg")
        # Returns: https://cdn.example.com/uploads/images/photo.jpg

    Security:
        Path traversal prevention is implemented via _sanitize_key() to prevent
        access to files outside the configured base path.
    """

    def __init__(self, config: FileSystemConfig) -> None:
        """Initialize FileSystemStorage.

        Args:
            config: Configuration for the storage backend

        Raises:
            ConfigurationError: If the path is invalid
        """
        self.config = config

        # Ensure base path exists if create_dirs is True
        if config.create_dirs:
            config.path.mkdir(parents=True, exist_ok=True)
        elif not config.path.exists():
            from litestar_storages.exceptions import ConfigurationError

            raise ConfigurationError(f"Storage path does not exist: {config.path}")

    def _sanitize_key(self, key: str) -> str:
        """Prevent directory traversal attacks.

        Args:
            key: The raw file key

        Returns:
            Sanitized key safe for filesystem use

        Note:
            This method:
            - Normalizes path separators to forward slashes
            - Removes leading slashes
            - Resolves .. and . components
            - Prevents access outside the base path
        """
        # Normalize path separators
        key = key.replace("\\", "/")
        # Remove leading slashes
        key = key.lstrip("/")
        # Resolve .. and . components
        parts = []
        for part in key.split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part and part != ".":
                parts.append(part)
        return "/".join(parts)

    def _get_path(self, key: str) -> Path:
        """Get the full filesystem path for a key.

        Args:
            key: Storage key

        Returns:
            Full filesystem path
        """
        sanitized = self._sanitize_key(key)
        return self.config.path / sanitized

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
            StoragePermissionError: If unable to write the file
        """
        try:
            import aiofiles
        except ImportError as e:
            from litestar_storages.exceptions import ConfigurationError

            raise ConfigurationError(
                "aiofiles is required for FileSystemStorage. Install it with: pip install aiofiles"
            ) from e

        file_path = self._get_path(key)

        # Create parent directories if needed
        if self.config.create_dirs:
            file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Write the file
            async with aiofiles.open(file_path, "wb") as f:
                if isinstance(data, bytes):
                    await f.write(data)
                    file_size = len(data)
                else:
                    file_size = 0
                    async for chunk in data:
                        await f.write(chunk)
                        file_size += len(chunk)

            # Set file permissions
            file_path.chmod(self.config.permissions)

            # Get file stats
            stat = file_path.stat()

            # Use provided content_type or detect from extension
            final_content_type = content_type or _guess_content_type(key)

            return StoredFile(
                key=key,
                size=file_size,
                content_type=final_content_type,
                etag=None,  # Could generate hash here
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                metadata={},  # Filesystem doesn't persist metadata
            )

        except OSError as e:
            raise StoragePermissionError(f"Failed to write file {key}: {e}") from e

    async def get(self, key: str) -> AsyncIterator[bytes]:
        """Retrieve file contents as an async byte stream.

        Args:
            key: Storage path/key for the file

        Yields:
            Chunks of file data as bytes

        Raises:
            StorageFileNotFoundError: If the file does not exist
        """
        try:
            import aiofiles
        except ImportError as e:
            from litestar_storages.exceptions import ConfigurationError

            raise ConfigurationError(
                "aiofiles is required for FileSystemStorage. Install it with: pip install aiofiles"
            ) from e

        file_path = self._get_path(key)

        if not file_path.exists():
            raise StorageFileNotFoundError(key)

        # Stream file in chunks
        chunk_size = 64 * 1024  # 64KB chunks
        async with aiofiles.open(file_path, "rb") as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async def get_bytes(self, key: str) -> bytes:
        """Retrieve entire file contents as bytes.

        Args:
            key: Storage path/key for the file

        Returns:
            Complete file contents as bytes

        Raises:
            StorageFileNotFoundError: If the file does not exist
        """
        try:
            import aiofiles
        except ImportError as e:
            from litestar_storages.exceptions import ConfigurationError

            raise ConfigurationError(
                "aiofiles is required for FileSystemStorage. Install it with: pip install aiofiles"
            ) from e

        file_path = self._get_path(key)

        if not file_path.exists():
            raise StorageFileNotFoundError(key)

        async with aiofiles.open(file_path, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> None:
        """Delete a file.

        Args:
            key: Storage path/key for the file

        Raises:
            StorageFileNotFoundError: If the file does not exist
        """
        file_path = self._get_path(key)

        if not file_path.exists():
            raise StorageFileNotFoundError(key)

        try:
            file_path.unlink()
        except OSError as e:
            raise StoragePermissionError(f"Failed to delete file {key}: {e}") from e

    async def exists(self, key: str) -> bool:
        """Check if a file exists.

        Args:
            key: Storage path/key for the file

        Returns:
            True if the file exists, False otherwise
        """
        file_path = self._get_path(key)
        return file_path.exists() and file_path.is_file()

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
        base_path = self.config.path
        search_path = base_path / self._sanitize_key(prefix) if prefix else base_path

        count = 0
        if search_path.exists():
            for file_path in search_path.rglob("*"):
                if file_path.is_file():
                    # Get relative path from base
                    rel_path = file_path.relative_to(base_path)
                    key = str(rel_path).replace("\\", "/")

                    # Check if it matches the prefix
                    if key.startswith(prefix):
                        stat = file_path.stat()
                        yield StoredFile(
                            key=key,
                            size=stat.st_size,
                            content_type=_guess_content_type(key),
                            etag=None,
                            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                            metadata={},
                        )
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
            expires_in: Optional expiration time (ignored for filesystem storage)

        Returns:
            URL string for accessing the file

        Note:
            If base_url is configured, returns base_url + key.
            Otherwise, returns file:// URL with absolute path.
        """
        if self.config.base_url:
            # Ensure base_url doesn't end with slash and key doesn't start with one
            base = self.config.base_url.rstrip("/")
            return f"{base}/{key}"
        # Return file:// URL
        file_path = self._get_path(key)
        return file_path.as_uri()

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
            FileNotFoundError: If the source file does not exist
        """
        import shutil

        source_path = self._get_path(source)
        dest_path = self._get_path(destination)

        if not source_path.exists():
            raise StorageFileNotFoundError(source)

        # Create parent directories if needed
        if self.config.create_dirs:
            dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Use shutil for efficient copy
            shutil.copy2(source_path, dest_path)

            # Set permissions
            dest_path.chmod(self.config.permissions)

            # Get file stats
            stat = dest_path.stat()

            return StoredFile(
                key=destination,
                size=stat.st_size,
                content_type=_guess_content_type(destination),
                etag=None,
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                metadata={},
            )

        except OSError as e:
            raise StoragePermissionError(f"Failed to copy file {source} to {destination}: {e}") from e

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
            FileNotFoundError: If the source file does not exist
        """
        import shutil

        source_path = self._get_path(source)
        dest_path = self._get_path(destination)

        if not source_path.exists():
            raise StorageFileNotFoundError(source)

        # Create parent directories if needed
        if self.config.create_dirs:
            dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Use shutil for efficient move
            shutil.move(str(source_path), str(dest_path))

            # Set permissions
            dest_path.chmod(self.config.permissions)

            # Get file stats
            stat = dest_path.stat()

            return StoredFile(
                key=destination,
                size=stat.st_size,
                content_type=_guess_content_type(destination),
                etag=None,
                last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                metadata={},
            )

        except OSError as e:
            raise StoragePermissionError(f"Failed to move file {source} to {destination}: {e}") from e

    async def info(self, key: str) -> StoredFile:
        """Get metadata about a file without downloading it.

        Args:
            key: Storage path/key for the file

        Returns:
            StoredFile with metadata

        Raises:
            StorageFileNotFoundError: If the file does not exist
        """
        file_path = self._get_path(key)

        if not file_path.exists():
            raise StorageFileNotFoundError(key)

        stat = file_path.stat()

        return StoredFile(
            key=key,
            size=stat.st_size,
            content_type=_guess_content_type(key),
            etag=None,
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            metadata={},
        )
