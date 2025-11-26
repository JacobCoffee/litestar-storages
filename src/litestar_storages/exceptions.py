"""Exception hierarchy for litestar-storages."""

from __future__ import annotations

__all__ = [
    "ConfigurationError",
    "StorageConnectionError",
    "StorageError",
    "StorageFileExistsError",
    "StorageFileNotFoundError",
    "StoragePermissionError",
]


class StorageError(Exception):
    """Base exception for all storage-related errors.

    All storage backends should raise exceptions derived from this class
    to allow for consistent error handling across different storage providers.
    """


class StorageFileNotFoundError(StorageError):
    """Raised when a requested file does not exist in storage.

    Attributes:
        key: The storage path/key that was not found
    """

    def __init__(self, key: str) -> None:
        """Initialize StorageFileNotFoundError.

        Args:
            key: The storage path/key that was not found
        """
        self.key = key
        super().__init__(f"File not found: {key}")


class StorageFileExistsError(StorageError):
    """Raised when attempting to create a file that already exists (when overwrite is disabled).

    Attributes:
        key: The storage path/key that already exists
    """

    def __init__(self, key: str) -> None:
        """Initialize StorageFileExistsError.

        Args:
            key: The storage path/key that already exists
        """
        self.key = key
        super().__init__(f"File already exists: {key}")


class StoragePermissionError(StorageError):
    """Raised when the operation fails due to insufficient permissions.

    This typically occurs when:
    - The storage backend credentials lack necessary permissions
    - File system permissions prevent the operation
    - Access control policies block the operation
    """


class StorageConnectionError(StorageError):
    """Raised when unable to connect to the storage backend.

    This typically occurs when:
    - Network connectivity issues prevent access
    - Storage service is unavailable
    - Authentication fails
    - Invalid endpoint configuration
    """


class ConfigurationError(StorageError):
    """Raised when storage backend configuration is invalid.

    This typically occurs when:
    - Required configuration parameters are missing
    - Configuration values are invalid or incompatible
    - Environment variables are malformed
    """
